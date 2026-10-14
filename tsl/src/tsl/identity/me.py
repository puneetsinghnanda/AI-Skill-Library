"""Role grants from GET /v1/me, cached 24 h (SDD-04 §6.1, SDD-07 §4.4, Doc 2 §2)."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from tsl.core.clock import iso, parse_iso
from tsl.core.errors import TslError
from tsl.core.jsonio import read_json, write_json
from tsl.core.runtime import Runtime
from tsl.insights.client import InsightsUnavailable

TTL = timedelta(hours=24)
APP_ROLES_ALLOWED = {"Engineer", "TechLead", "Admin"}


def cached_me(rt: Runtime) -> dict[str, Any] | None:
    p = rt.home.me
    if not p.exists():
        return None
    try:
        data = read_json(p)
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def _fresh(rt: Runtime, me: dict[str, Any]) -> bool:
    try:
        return rt.clock() - parse_iso(str(me["cached_at"])) <= TTL
    except (KeyError, ValueError):
        return False


def fetch_me(rt: Runtime, token: str | None = None) -> dict[str, Any]:
    tok = token or rt.token()
    res = rt.insights.get_me(tok)
    if res.status == 401:
        tok = rt.identity().silent_token(force_refresh=True)
        res = rt.insights.get_me(tok)
    if res.status == 401:
        raise TslError("E-AUTH-01")
    if res.status == 403:
        # The service names the pseudonym and GitHub login an admin needs to grant a role to.
        detail = res.body.get("detail") if isinstance(res.body, dict) else None
        if isinstance(detail, str) and detail.strip():
            raise TslError(
                "E-AUTH-08", detail.strip()[:300], next="Ask an admin to grant you a role"
            )
        raise TslError("E-AUTH-08")
    if res.status >= 500:
        raise InsightsUnavailable(f"HTTP {res.status}")
    if res.status != 200 or not isinstance(res.body, dict):
        raise TslError("E-NET-02")
    me = dict(res.body)
    prev = cached_me(rt) or {}
    if prev.get("oid") and not me.get("oid"):
        me["oid"] = prev["oid"]
    me["cached_at"] = iso(rt.clock())
    write_json(rt.home.me, me)
    return me


def current_me(rt: Runtime, online: bool = False) -> dict[str, Any]:
    c = cached_me(rt)
    if c is not None and _fresh(rt, c) and not online:
        return c
    try:
        return fetch_me(rt)
    except InsightsUnavailable:
        if c is None:
            raise TslError("E-NET-02") from None
        if _fresh(rt, c):
            return c
        raise TslError("E-AUTH-07") from None


def has_grant(me: dict[str, Any], roles: set[str], system: str | None) -> bool:
    for g in me.get("grants", []):
        if g.get("role") not in roles:
            continue
        scope = str(g.get("scope", ""))
        if scope == "org" or (system is not None and scope == f"system:{system}"):
            return True
    return False


def require_grant(
    rt: Runtime, roles: set[str], system: str, code: str, **fmt: Any
) -> dict[str, Any]:
    me = current_me(rt)
    if not has_grant(me, roles, system):
        raise TslError(code, system=system, **fmt)
    return me


SYSTEM_TTL = timedelta(hours=24)


def system_record(rt: Runtime, code: str) -> dict[str, Any]:
    """GET /v1/systems/{code}, cached 24 h (SDD-12 §5.3)."""
    p = rt.home.system_cache(code)
    cached: dict[str, Any] | None = None
    if p.exists():
        try:
            cached = read_json(p)
        except ValueError:
            cached = None
    if cached and rt.clock() - parse_iso(str(cached.get("cached_at"))) <= SYSTEM_TTL:
        return cached
    try:
        res = rt.insights.get_system(rt.token(), code)
    except InsightsUnavailable:
        if cached:
            return cached
        raise TslError("E-NET-02") from None
    if res.status == 404:
        raise TslError("E-INIT-01", system=code)
    if res.status == 403:
        raise TslError("E-AUTH-03", system=code)
    if res.status != 200 or not isinstance(res.body, dict):
        raise TslError("E-NET-02")
    data = dict(res.body)
    data["cached_at"] = iso(rt.clock())
    write_json(p, data)
    return data


def require_consent(
    rt: Runtime, system: str, scopes: tuple[str, ...], code: str = "E-CONS-01"
) -> dict[str, Any]:
    rec = system_record(rt, system)
    state = rec.get("lifecycle_state")
    if state == "ARCHIVED":
        raise TslError("E-COMP-07", system=system)
    consent = rec.get("consent") or {}
    if state == "SUSPENDED" or not consent.get("recorded"):
        raise TslError(code, client=rec.get("client", "?"), scope="consent")
    have = set(consent.get("scope") or [])
    for s in scopes:
        if s not in have:
            raise TslError(code, client=rec.get("client", "?"), scope=s)
    return rec
