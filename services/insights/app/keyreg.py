"""Key registry facts shared by ``GET /v1/keys/{key_id}`` and ``POST /v1/signatures/verify`` "
"(SDD-07)."""

from __future__ import annotations

import base64
from datetime import datetime
from typing import Any

from sqlalchemy import Connection, text

from app.timeutil import iso

ROLE_ORDER = (
    "engineer",
    "tech_lead",
    "skill_owner",
    "stage_approver",
    "eng_lead",
    "admin",
    "viewer",
)


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def b64url_decode(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def key_row(conn: Connection, key_id: str) -> Any:
    return conn.execute(
        text(
            "SELECT k.key_id, k.user_id::text AS user_id, k.device_id, k.device_label, "
            "k.public_key, "
            "k.created_at, k.expires_at, k.revoked_at, k.revoked_reason, k.compromised_since, "
            "u.pseudonym FROM keys k JOIN users u ON u.id = k.user_id WHERE k.key_id = :k"
        ),
        {"k": key_id},
    ).first()


def roles_at(conn: Connection, user_id: str, at: datetime, system_code: str | None) -> list[str]:
    """Roles the user held on the system at ``at``, from ``role_grants`` history (SDD-08 §6.2)."""
    rows = conn.execute(
        text(
            "SELECT DISTINCT g.role FROM role_grants g "
            "LEFT JOIN systems s ON g.scope_type = 'system' AND s.id::text = g.scope_id "
            "WHERE g.user_id = CAST(:u AS uuid) AND g.granted_at <= :at "
            "AND (g.revoked_at IS NULL OR g.revoked_at > :at) AND ("
            "  (g.scope_type = 'system' AND s.code = :sys) "
            "  OR (g.scope_type = 'org' AND g.role IN ('eng_lead', 'admin')) "
            "  OR (g.scope_type = 'project' AND g.role = 'eng_lead' AND EXISTS ("
            "       SELECT 1 FROM systems s2 WHERE s2.code = :sys AND s2.project_id::text = "
            "g.scope_id)) "
            "  OR (g.scope_type = 'client' AND g.role = 'eng_lead' AND EXISTS ("
            "       SELECT 1 FROM systems s3 JOIN projects p3 ON p3.id = s3.project_id "
            "       WHERE s3.code = :sys AND p3.client_id::text = g.scope_id)))"
        ),
        {"u": user_id, "at": at, "sys": system_code or ""},
    ).scalars()
    have = set(rows)
    return [r for r in ROLE_ORDER if r in have]


def facts(row: Any) -> dict[str, Any]:
    return {
        "key_id": row.key_id,
        "public_key": b64url(bytes(row.public_key)),
        "user_pseudonym": row.pseudonym,
        "created_at": iso(row.created_at),
        "expires_at": iso(row.expires_at),
        "revoked_at": iso(row.revoked_at),
        "revoked_reason": row.revoked_reason,
        "compromised_since": iso(row.compromised_since),
    }
