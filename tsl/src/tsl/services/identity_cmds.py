"""tsl login | logout | whoami | keys (SDD-07 §4-§5, SDD-04 §6.1-§6.2)."""

from __future__ import annotations

import contextlib
import sys
from typing import Any

from tsl.core.errors import TslError
from tsl.core.runtime import Runtime
from tsl.identity import keys as keymod
from tsl.identity import me as memod
from tsl.insights.client import InsightsUnavailable
from tsl.telemetry.emit import flush

BANNER = (
    "Truminds Skill Library (tsl), published by Truminds, is asking you to sign in.\n"
    "Only continue if you typed `tsl login` yourself just now."
)


def _me_data(rt: Runtime, me: dict[str, Any], info: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "pseudonym": me.get("pseudonym"),
        "upn": me.get("upn"),
        "app_roles": me.get("app_roles", []),
        "grants": me.get("grants", []),
        "key_id": (info or {}).get("key_id"),
        "device_id": rt.device_id(),
        "grants_cached_at": me.get("cached_at"),
    }


def login(rt: Runtime, rotate_key: bool, interactive: bool | None = None) -> dict[str, Any]:
    if interactive is None:
        interactive = sys.stdin.isatty()
    rt.ensure_device()
    ident = rt.identity()
    token: str | None = None
    claims: dict[str, Any] = {}
    me: dict[str, Any] | None = None
    try:
        token = ident.silent_token()
    except TslError:
        token = None
    if token is not None:
        try:
            me = memod.fetch_me(rt, token)
        except InsightsUnavailable:
            raise TslError("E-NET-02") from None
        except TslError as exc:
            if exc.code != "E-AUTH-01":
                raise
            ident.logout()  # the stored token was rejected: start a new sign-in
            token = None
    if token is None:
        if not interactive:
            raise TslError(
                "E-USE-01", detail="tsl login must run in an interactive terminal", cmd="login"
            )
        rt.prompt(BANNER)  # shown now: the device code below must be seen while login waits
        res = ident.device_login(rt.prompt)
        token = str(res["access_token"])
        claims = dict(res.get("id_token_claims") or {})
        try:
            me = memod.fetch_me(rt, token)
        except InsightsUnavailable:
            raise TslError("E-NET-02") from None
    if me is None:  # unreachable: both paths above set it
        raise TslError("E-AUTH-01")
    if claims.get("oid"):
        me["oid"] = claims["oid"]
        from tsl.core.jsonio import write_json

        write_json(rt.home.me, me)
    if not set(me.get("app_roles", [])) & memod.APP_ROLES_ALLOWED:
        raise TslError("E-AUTH-08")
    sub = str(me.get("oid") or me.get("pseudonym"))
    info, new = keymod.ensure_key(rt, token, sub, force_new=rotate_key)
    with contextlib.suppress(TslError):
        flush(rt, max_seconds=5)
    data = _me_data(rt, me, info)
    data.update({"key_new": new, "key_status": "active"})
    return data


def logout(rt: Runtime, revoke_key: bool) -> dict[str, Any]:
    info = keymod.active_info(rt)
    revoked = None
    if revoke_key and info:
        keymod.revoke(rt, str(info["key_id"]), None)  # raises before anything is deleted
        revoked = info["key_id"]
    rt.identity().logout()
    if rt.home.me.exists():
        rt.home.me.unlink()
    return {"logged_out": True, "revoked_key": revoked}


def whoami(rt: Runtime, refresh: bool) -> dict[str, Any]:
    me = memod.current_me(rt, online=refresh)
    info = keymod.active_info(rt)
    status = "unknown"
    if info:
        try:
            keymod.load_signer(rt)
            status = "active"
        except TslError:
            status = "revoked"
    data = _me_data(rt, me, info)
    data["key_status"] = status
    return data


def keys_list(rt: Runtime) -> dict[str, Any]:
    try:
        res = rt.insights.my_keys(rt.token())
    except InsightsUnavailable:
        raise TslError("E-NET-02") from None
    if res.status != 200:
        raise TslError("E-AUTH-01" if res.status == 401 else "E-NET-02")
    info = keymod.active_info(rt) or {}
    body = res.body if isinstance(res.body, list) else (res.body or {}).get("keys", [])
    keys = []
    for k in body:
        item = {
            f: k.get(f)
            for f in (
                "key_id",
                "device_id",
                "device_label",
                "created_at",
                "expires_at",
                "revoked_at",
            )
        }
        item["reason"] = k.get("revoked_reason")
        item["local_active"] = k.get("key_id") == info.get("key_id")
        keys.append(item)
    return {"keys": keys}


def keys_rotate(rt: Runtime) -> dict[str, Any]:
    me = memod.current_me(rt)
    info = keymod.register_new_key(rt, rt.token(), str(me.get("oid") or me.get("pseudonym")))
    return {"key_id": info["key_id"], "previous": info.get("previous")}


def keys_revoke(rt: Runtime, key_id: str, compromised_since: str | None) -> dict[str, Any]:
    return keymod.revoke(rt, key_id, compromised_since)
