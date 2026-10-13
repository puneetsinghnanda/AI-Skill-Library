"""Signature accept rule, the same code on the laptop and in CI (SDD-07 §7.3)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from tsl.core.clock import parse_iso
from tsl.identity.signing import b64url_decode, signature_ok

SKEW = timedelta(minutes=5)


@dataclass
class KeyFacts:
    known: bool
    public_key: bytes = b""
    created_at: datetime | None = None
    expires_at: datetime | None = None
    revoked_at: datetime | None = None
    revoked_reason: str | None = None
    compromised_since: datetime | None = None
    roles_at: list[str] = field(default_factory=list)
    anchored_at: datetime | None = None


def _t(v: Any) -> datetime | None:
    return parse_iso(str(v)) if v else None


def facts_from(d: dict[str, Any] | None) -> KeyFacts:
    if not d or d.get("known") is False or not d.get("public_key"):
        return KeyFacts(known=False)
    return KeyFacts(
        True,
        b64url_decode(str(d["public_key"])),
        _t(d.get("created_at")),
        _t(d.get("expires_at")),
        _t(d.get("revoked_at")),
        d.get("revoked_reason"),
        _t(d.get("compromised_since")),
        list(d.get("roles_at") or []),
        _t(d.get("anchored_at")),
    )


def accept(
    obj: dict[str, Any],
    signed_at: datetime,
    roles_needed: list[str],
    f: KeyFacts,
    require_anchor: bool = False,
    check_roles: bool = True,
) -> tuple[str, str | None]:
    if not f.known:
        return "bad", "unknown_key"
    if not signature_ok(obj, f.public_key):
        return "bad", "bad_signature"
    if f.created_at and signed_at < f.created_at - SKEW:
        return "bad", "signed_before_key"
    if f.expires_at and signed_at > f.expires_at:
        return "bad", "key_expired"
    if f.revoked_reason in ("compromised", "lost_device"):
        if f.compromised_since and signed_at >= f.compromised_since:
            return "bad", "compromised"
        if f.anchored_at is None or (f.compromised_since and f.anchored_at >= f.compromised_since):
            return "bad", "not_anchored_before_compromise"
    elif f.revoked_at and signed_at >= f.revoked_at:
        return "bad", "revoked"
    if check_roles and roles_needed and not set(roles_needed) & set(f.roles_at):
        return "bad", "role_missing"
    if f.anchored_at is None:
        return ("bad", "not_anchored") if require_anchor else ("unanchored", None)
    return "ok", None
