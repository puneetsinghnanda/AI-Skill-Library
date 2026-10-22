"""Ed25519 signing keys: generate, register, rotate, revoke, load (SDD-07 §5)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat

from tsl.core.clock import iso, parse_iso
from tsl.core.errors import TslError
from tsl.core.jsonio import read_json, write_json
from tsl.core.runtime import Runtime
from tsl.identity.signing import b64url, b64url_decode, canonical, public_key_b64
from tsl.insights.client import InsightsUnavailable

MAX_AGE = timedelta(days=180)


def _sign_item(key_id: str) -> str:
    return f"signing-key:{key_id}"


def _active_item(device_id: str) -> str:
    return f"active-key:{device_id}"


def active_info(rt: Runtime) -> dict[str, Any] | None:
    p = rt.home.active_key
    if not p.exists():
        return None
    data = read_json(p)
    return data if isinstance(data, dict) else None


@dataclass
class Signer:
    key_id: str
    private: Ed25519PrivateKey
    public_b64: str


def load_signer(rt: Runtime) -> Signer:
    """The active key of this device, or E-AUTH-02 / E-KEY-05 / E-KEY-01 (SDD-07 §6.3)."""
    dev = rt.device_id()
    if not dev:
        raise TslError("E-AUTH-02")
    key_id = rt.keystore.get(_active_item(dev))
    if not key_id:
        raise TslError("E-AUTH-02")
    seed = rt.keystore.get(_sign_item(key_id))
    if not seed:
        raise TslError("E-AUTH-02")
    info = active_info(rt) or {}
    if info.get("key_id") != key_id:
        raise TslError("E-AUTH-02")
    if info.get("expires_at") and rt.clock() > parse_iso(str(info["expires_at"])):
        raise TslError("E-KEY-05")
    cached = cached_key(rt, key_id)
    if cached and cached.get("revoked_at"):
        raise TslError("E-AUTH-02")
    priv = Ed25519PrivateKey.from_private_bytes(b64url_decode(seed))
    return Signer(key_id, priv, public_key_b64(priv))


def cached_key(rt: Runtime, key_id: str) -> dict[str, Any] | None:
    p = rt.home.key_cache(key_id)
    if not p.exists():
        return None
    data = read_json(p)
    return data if isinstance(data, dict) else None


def cache_key(rt: Runtime, facts: dict[str, Any]) -> None:
    facts = dict(facts)
    facts["fetched_at"] = iso(rt.clock())
    write_json(rt.home.key_cache(str(facts["key_id"])), facts)


# Seconds to wait for a sleeping insights service to wake before a strict key lookup gives up.
WAKE_SECONDS = 60.0


def wake_service(rt: Runtime, max_seconds: float | None = None) -> bool:
    """Poll the service's health until it answers: a free hosted service sleeps when idle."""
    import time

    deadline = time.monotonic() + (WAKE_SECONDS if max_seconds is None else max_seconds)
    while True:
        if rt.insights.health():
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(2)


def public_key_strict(rt: Runtime, key_id: str) -> dict[str, Any] | None:
    """Like public_key(online=True), but says why a lookup failed instead of returning None.

    Returns None only when the service answers that the key does not exist. Raises E-AUTH-01 when
    the service refuses our own sign-in, and E-NET-02 when it stays unreachable after a wake-up.
    """
    found = public_key(rt, key_id, online=False)
    if found is not None:
        return found
    for attempt in range(2):
        try:
            res = rt.insights.get_key(rt.token(), key_id)
        except InsightsUnavailable:
            if attempt == 0:
                wake_service(rt)
                continue
            raise TslError("E-NET-02") from None
        if res.status in (401, 403):
            raise TslError(
                "E-AUTH-01",
                "Your Truminds sign-in is no longer valid (the service refused it).",
                next="tsl login, then repeat the command",
            )
        if res.status == 200 and isinstance(res.body, dict):
            cache_key(rt, res.body)
            return dict(res.body)
        return None
    return None


def public_key(rt: Runtime, key_id: str, online: bool = True) -> dict[str, Any] | None:
    """Key facts for local verification: cache first, then GET /v1/keys/{id} (SDD-07 §5.3)."""
    info = active_info(rt)
    c = cached_key(rt, key_id)
    if c is not None:
        return c
    if info and info.get("key_id") == key_id:
        return {
            "key_id": key_id,
            "public_key": info["public_key"],
            "created_at": info["created_at"],
            "expires_at": info["expires_at"],
            "revoked_at": None,
            "revoked_reason": None,
            "compromised_since": None,
        }
    if not online:
        return None
    try:
        res = rt.insights.get_key(rt.token(), key_id)
    except (InsightsUnavailable, TslError):
        return None
    if res.status != 200 or not isinstance(res.body, dict):
        return None
    cache_key(rt, res.body)
    return dict(res.body)


def _new_key(rt: Runtime) -> tuple[str, Ed25519PrivateKey]:
    return rt.ids.new("key"), Ed25519PrivateKey.generate()


def _seed(priv: Ed25519PrivateKey) -> str:
    return b64url(priv.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption()))


def register_new_key(rt: Runtime, token: str, sub: str) -> dict[str, Any]:
    """Generate, store, POST /v1/keys with proof; on failure delete the new key (SDD-07 §5.4)."""
    dev = rt.ensure_device()
    label = str(rt.user_config().get("device", {}).get("label", "laptop"))
    key_id, priv = _new_key(rt)
    pub = public_key_b64(priv)
    iat = iso(rt.clock())
    rt.keystore.set(_sign_item(key_id), _seed(priv))
    proof_body = {"key_id": key_id, "public_key": pub, "device_id": dev, "sub": sub, "iat": iat}
    body = {
        "key_id": key_id,
        "algorithm": "Ed25519",
        "public_key": pub,
        "device_id": dev,
        "device_label": label,
        "iat": iat,
        "proof": b64url(priv.sign(canonical(proof_body))),
    }
    try:
        res = rt.insights.register_key(token, body)
    except InsightsUnavailable:
        rt.keystore.delete(_sign_item(key_id))
        raise TslError("E-NET-02") from None
    if res.status not in (200, 201):
        rt.keystore.delete(_sign_item(key_id))
        code = {400: "E-KEY-02", 409: "E-KEY-03", 403: "E-AUTH-08", 401: "E-AUTH-01"}.get(
            res.status, "E-NET-02"
        )
        raise TslError(code)
    old = rt.keystore.get(_active_item(dev))
    rt.keystore.set(_active_item(dev), key_id)
    if old and old != key_id:
        rt.keystore.delete(_sign_item(old))
    created = iso(rt.clock())
    expires = str((res.body or {}).get("expires_at") or iso(rt.clock() + MAX_AGE))
    info = {
        "key_id": key_id,
        "public_key": pub,
        "device_id": dev,
        "created_at": created,
        "expires_at": expires,
    }
    write_json(rt.home.active_key, info)
    return {**info, "previous": old}


def ensure_key(rt: Runtime, token: str, sub: str, force_new: bool) -> tuple[dict[str, Any], bool]:
    info = active_info(rt)
    usable = False
    if info and not force_new:
        try:
            load_signer(rt)
            usable = True
        except TslError:
            usable = False
    if usable and info is not None:
        return info, False
    return register_new_key(rt, token, sub), True


def revoke(rt: Runtime, key_id: str, compromised_since: str | None) -> dict[str, Any]:
    body: dict[str, Any] = {"reason": "compromised" if compromised_since else "user_request"}
    if compromised_since:
        body["compromised_since"] = compromised_since
    try:
        res = rt.insights.revoke_key(rt.token(), key_id, body)
    except InsightsUnavailable:
        raise TslError("E-NET-02") from None
    if res.status != 200:
        code = {404: "E-KEY-04", 422: "E-KEY-06", 403: "E-AUTH-08", 401: "E-AUTH-01"}.get(
            res.status, "E-NET-02"
        )
        raise TslError(code)
    dev = rt.device_id()
    if dev and rt.keystore.get(_active_item(dev)) == key_id:
        rt.keystore.delete(_sign_item(key_id))
        rt.keystore.delete(_active_item(dev))
        if rt.home.active_key.exists():
            rt.home.active_key.unlink()
    return dict(res.body or {"key_id": key_id})
