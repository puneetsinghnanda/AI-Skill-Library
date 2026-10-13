"""OTel and CI ingest tokens (SDD-08 §9.3). Only sha256(token) is stored; compared in constant time.

Format ``tsi_<kind>_<32 random bytes base64url>``. Issued and revoked only through
``python -m app.admin token ...``; there is no HTTP endpoint for this.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import Connection, text

Kind = Literal["otel", "ci"]


@dataclass(frozen=True)
class IngestToken:
    id: str
    kind: Kind
    label: str


def looks_like_ingest_token(token: str) -> bool:
    return token.startswith("tsi_")


def new_token(kind: Kind) -> str:
    raw = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode()
    return f"tsi_{kind}_{raw}"


def digest(token: str) -> bytes:
    return hashlib.sha256(token.encode("utf-8")).digest()


def check(conn: Connection, token: str) -> IngestToken | None:
    d = digest(token)
    row = conn.execute(
        text(
            "SELECT id::text, kind, label, token_sha256 FROM ingest_tokens "
            "WHERE token_sha256 = :d AND revoked_at IS NULL"
        ),
        {"d": d},
    ).first()
    if row is None or not hmac.compare_digest(bytes(row.token_sha256), d):
        return None
    conn.execute(
        text("UPDATE ingest_tokens SET last_used_at = now() WHERE id = CAST(:id AS uuid)"),
        {"id": row.id},
    )
    return IngestToken(row.id, row.kind, row.label)


def create(conn: Connection, kind: Kind, label: str) -> tuple[str, str]:
    tok = new_token(kind)
    row = conn.execute(
        text(
            "INSERT INTO ingest_tokens (kind, token_sha256, label) VALUES (:k, :d, :l) "
            "RETURNING id::text"
        ),
        {"k": kind, "d": digest(tok), "l": label},
    ).one()
    return str(row[0]), tok


def revoke(conn: Connection, token_id: str) -> bool:
    res = conn.execute(
        text(
            "UPDATE ingest_tokens SET revoked_at = now() "
            "WHERE id = CAST(:id AS uuid) AND revoked_at IS NULL"
        ),
        {"id": token_id},
    )
    return bool(res.rowcount)
