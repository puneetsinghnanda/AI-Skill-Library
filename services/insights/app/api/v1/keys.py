"""Signing keys: register, look up, revoke, list own (SDD-07 §5, wire SDD-08 §6.2)."""

from __future__ import annotations

import re
from datetime import timedelta
from typing import Any, Literal

import rfc8785
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

from app.api.deps import (
    require_engineer_app_role,
    tsl_or_ci,
    tsl_or_portal_read,
    tsl_or_portal_write,
    tsl_writer,
)
from app.auth.principal import Principal
from app.auth.users import audit
from app.config import Settings
from app.db import tx
from app.errors import ServiceError
from app.ingest.denylist import check_string
from app.keyreg import b64url_decode, facts, key_row, roles_at
from app.timeutil import iso, parse_iso, utcnow

router = APIRouter(tags=["keys"])
KEY_ID = r"^key_[0-9A-HJKMNP-TV-Z]{26}$"
DEV_ID = r"^dev_[0-9A-HJKMNP-TV-Z]{26}$"


class KeyRegistration(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key_id: str = Field(pattern=KEY_ID)
    algorithm: Literal["Ed25519"]
    public_key: str = Field(min_length=43, max_length=44)
    device_id: str = Field(pattern=DEV_ID)
    device_label: str | None = Field(default=None, max_length=40)
    iat: str
    proof: str = Field(min_length=86, max_length=88)


class KeyRegistered(BaseModel):
    key_id: str
    pseudonym: str
    roles: list[str]
    expires_at: str


@router.post(
    "/v1/keys",
    status_code=201,
    response_model=KeyRegistered,
    summary="Register a signing public key (SDD-07 §5.2)",
)
def register_key(
    body: KeyRegistration, request: Request, p: Principal = Depends(tsl_writer)
) -> Any:
    s: Settings = request.app.state.settings
    require_engineer_app_role(p)
    assert p.user is not None and p.claims is not None  # noqa: S101
    try:
        iat = parse_iso(body.iat)
        pub = b64url_decode(body.public_key)
        sig = b64url_decode(body.proof)
    except ValueError:
        raise ServiceError("E-KEY-02", "Malformed iat, public key or proof") from None
    if abs((utcnow() - iat).total_seconds()) > s.key_proof_window_s or len(pub) != 32:
        raise ServiceError("E-KEY-02", "iat older than 5 minutes or bad key length")
    proof_obj = {
        "key_id": body.key_id,
        "public_key": body.public_key,
        "device_id": body.device_id,
        "sub": p.claims.oid,
        "iat": body.iat,
    }
    try:
        Ed25519PublicKey.from_public_bytes(pub).verify(sig, rfc8785.dumps(proof_obj))
    except (InvalidSignature, ValueError):
        raise ServiceError("E-KEY-02", "Proof does not verify") from None
    roles = sorted({g.role for g in p.grants})
    with tx("app", s) as conn:
        existing = key_row(conn, body.key_id)
        if existing is not None:
            if bytes(existing.public_key) != pub or existing.user_id != p.user.id:
                raise ServiceError("E-KEY-03")
            if existing.revoked_at is not None:
                # A revoked key is never re-activated; tsl generates a new key id on E-KEY-03.
                raise ServiceError("E-KEY-03", "Key is revoked; generate a new key")
            out = {
                "key_id": body.key_id,
                "pseudonym": p.user.pseudonym,
                "roles": roles,
                "expires_at": iso(existing.expires_at),
            }
            return JSONResponse(out, status_code=200)
        old = (
            conn.execute(
                text(
                    "UPDATE keys SET revoked_at = now(), revoked_reason = 'replaced' "
                    "WHERE user_id = CAST(:u AS uuid) AND device_id = :d AND revoked_at IS NULL "
                    "RETURNING key_id"
                ),
                {"u": p.user.id, "d": body.device_id},
            )
            .scalars()
            .all()
        )
        expires = conn.execute(
            text(
                "INSERT INTO keys (key_id, user_id, device_id, device_label, public_key, "
                "created_at, expires_at) "
                "VALUES (:k, CAST(:u AS uuid), :d, :l, :pk, now(), now() + make_interval(days => "
                ":age)) "
                "RETURNING expires_at"
            ),
            {
                "k": body.key_id,
                "u": p.user.id,
                "d": body.device_id,
                "l": body.device_label,
                "pk": pub,
                "age": s.key_max_age_days,
            },
        ).scalar_one()
        audit(
            conn,
            p.user.id,
            "key_register",
            "key",
            body.key_id,
            after={"device_id": body.device_id, "replaced": list(old)},
        )
    return {
        "key_id": body.key_id,
        "pseudonym": p.user.pseudonym,
        "roles": roles,
        "expires_at": iso(expires),
    }


@router.get("/v1/keys/{key_id}", summary="Public key, status and roles_at (SDD-08 §6.2)")
def get_key(
    key_id: str,
    request: Request,
    at: str | None = Query(default=None),
    system: str | None = Query(default=None, pattern=r"^SYS-[0-9A-Z]{2,8}$"),
    p: Principal = Depends(tsl_or_ci),
) -> dict[str, Any]:
    s: Settings = request.app.state.settings
    if p.kind == "entra":
        require_engineer_app_role(p)
    if not re.match(KEY_ID, key_id):
        raise ServiceError("E-KEY-04")
    when = utcnow()
    if at:
        try:
            when = parse_iso(at)
        except ValueError:
            raise ServiceError("E-API-01", "at is not a date-time") from None
    with tx("app", s) as conn:
        row = key_row(conn, key_id)
        if row is None:
            raise ServiceError("E-KEY-04")
        out = facts(row)
        out["roles_at"] = roles_at(conn, row.user_id, when, system) if system else []
    return out


class RevokeBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: Literal[
        "user_request", "offboarded", "admin_other", "lost_device", "compromised", "replaced"
    ]
    compromised_since: str | None = None
    note: str | None = Field(default=None, max_length=200)


OWNER_REASONS = {"user_request", "lost_device", "compromised"}
ADMIN_REASONS = {"user_request", "offboarded", "admin_other", "lost_device", "compromised"}


@router.post("/v1/keys/{key_id}/revoke", summary="Revoke a key (SDD-07 §5.6)")
def revoke_key(
    key_id: str, body: RevokeBody, request: Request, p: Principal = Depends(tsl_or_portal_write)
) -> dict[str, Any]:
    s: Settings = request.app.state.settings
    assert p.user is not None  # noqa: S101
    if body.note and check_string("note", body.note):
        raise ServiceError("E-API-01", "note failed the deny-list")
    is_admin = p.has("admin")
    with tx("app", s) as conn:
        row = key_row(conn, key_id)
        if row is None or (row.user_id != p.user.id and not is_admin):
            raise ServiceError("E-KEY-04")
        allowed = ADMIN_REASONS if is_admin else set()
        if row.user_id == p.user.id:
            allowed = allowed | OWNER_REASONS
        if body.reason not in allowed:
            raise ServiceError("E-AUTH-08", f"Reason {body.reason} is not allowed for this caller")
        return revoke(conn, row, p.user.id, body.reason, body.compromised_since, body.note)


def revoke(
    conn: Any, row: Any, actor: str, reason: str, since_s: str | None, note: str | None
) -> dict[str, Any]:
    now = utcnow()
    since = None
    if reason in ("lost_device", "compromised"):
        try:
            since = parse_iso(since_s) if since_s else row.created_at
        except ValueError:
            raise ServiceError("E-KEY-06", "compromised_since is not a date-time") from None
        if since < row.created_at - timedelta(seconds=1) or since > now:
            raise ServiceError("E-KEY-06")
        if row.compromised_since is not None and since > row.compromised_since:
            raise ServiceError("E-KEY-06", "compromised_since may only move earlier")
    before = facts(row)
    upd = conn.execute(
        text(
            "UPDATE keys SET revoked_at = coalesce(revoked_at, now()), "
            "revoked_reason = CASE WHEN revoked_reason IN ('lost_device','compromised') AND :r NOT "
            "IN "
            "('lost_device','compromised') THEN revoked_reason ELSE :r END, "
            "compromised_since = coalesce(:cs, compromised_since), revoked_by = CAST(:a AS uuid), "
            "revoke_note = coalesce(:n, revoke_note) WHERE key_id = :k "
            "RETURNING revoked_at, revoked_reason, compromised_since"
        ),
        {"r": reason, "cs": since, "a": actor, "n": note, "k": row.key_id},
    ).one()
    after = {
        "revoked_at": iso(upd.revoked_at),
        "revoked_reason": upd.revoked_reason,
        "compromised_since": iso(upd.compromised_since),
    }
    audit(conn, actor, "key_revoke", "key", row.key_id, before=before, after=after, reason=note)
    return {"key_id": row.key_id, **after}


@router.get("/v1/me/keys", summary="Own keys (SDD-07 §5.5)")
def my_keys(request: Request, p: Principal = Depends(tsl_or_portal_read)) -> dict[str, Any]:
    s: Settings = request.app.state.settings
    assert p.user is not None  # noqa: S101
    with tx("app", s) as conn:
        rows = conn.execute(
            text(
                "SELECT key_id, device_id, device_label, created_at, expires_at, revoked_at, "
                "revoked_reason, "
                "compromised_since FROM keys WHERE user_id = CAST(:u AS uuid) ORDER BY created_at "
                "DESC"
            ),
            {"u": p.user.id},
        ).all()
    return {
        "keys": [
            {
                "key_id": r.key_id,
                "device_id": r.device_id,
                "device_label": r.device_label,
                "created_at": iso(r.created_at),
                "expires_at": iso(r.expires_at),
                "revoked_at": iso(r.revoked_at),
                "revoked_reason": r.revoked_reason,
                "compromised_since": iso(r.compromised_since),
            }
            for r in rows
        ]
    }
