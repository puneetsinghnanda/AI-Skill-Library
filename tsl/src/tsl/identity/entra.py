"""Microsoft Entra ID device-code login and silent tokens through MSAL (SDD-07 §4).

The MSAL token cache is sealed with AES-256-GCM in ~/.truminds/msal-cache.bin;
the 32-byte cache key lives in the OS keychain (SDD-07 §4.3). Tests inject a
fake IdentityProvider; no test talks to a tenant.
"""

from __future__ import annotations

import os
import secrets
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

from tsl.core.errors import TslError
from tsl.identity.keystore import KeyStore
from tsl.identity.org import OrgConfig
from tsl.identity.signing import b64url, b64url_decode

CACHE_KEY_ITEM = "msal-cache-key"
VERSION = b"\x01"


class IdentityProvider(Protocol):
    def device_login(self, show: Callable[[str], None]) -> dict[str, Any]:
        """Run the device-code flow; return MSAL's result (access_token, id_token_claims)."""
        ...

    def silent_token(self, force_refresh: bool = False) -> str: ...

    def logout(self) -> None: ...


class SealedCache:
    def __init__(self, path: Path, keystore: KeyStore, device_id: str) -> None:
        self.path = path
        self.keystore = keystore
        self.aad = b"tsl-msal-cache-v1:" + device_id.encode()

    def _key(self, create: bool) -> bytes | None:
        v = self.keystore.get(CACHE_KEY_ITEM)
        if v is None and create:
            v = b64url(secrets.token_bytes(32))
            self.keystore.set(CACHE_KEY_ITEM, v)
        return None if v is None else b64url_decode(v)

    def load(self) -> str | None:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        if not self.path.exists():
            return None
        key = self._key(create=False)
        if key is None:
            return None
        raw = self.path.read_bytes()
        if not raw.startswith(VERSION) or len(raw) < 13:
            return None
        try:
            return AESGCM(key).decrypt(raw[1:13], raw[13:], self.aad).decode("utf-8")
        except Exception:  # tampered or wrong device: force a new login (K-01)
            return None

    def save(self, text: str) -> None:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        key = self._key(create=True)
        if key is None:
            raise TslError("E-KEY-01")
        nonce = secrets.token_bytes(12)
        data = VERSION + nonce + AESGCM(key).encrypt(nonce, text.encode("utf-8"), self.aad)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_bytes(data)
        os.replace(tmp, self.path)

    def clear(self) -> None:
        if self.path.exists():
            self.path.unlink()
        self.keystore.delete(CACHE_KEY_ITEM)


class MsalIdentity:
    def __init__(self, org: OrgConfig, cache: SealedCache) -> None:
        self.org = org
        self.cache = cache

    def _app(self) -> tuple[Any, Any]:
        if not self.org.configured:
            raise TslError(
                "E-AUTH-01",
                "This tsl build has no identity configuration.",
                next="Install the release wheel of tsl",
            )
        import msal

        tc = msal.SerializableTokenCache()
        text = self.cache.load()
        if text:
            tc.deserialize(text)
        app = msal.PublicClientApplication(
            self.org.tsl_client_id, authority=self.org.authority, token_cache=tc
        )
        return app, tc

    def _persist(self, tc: Any) -> None:
        if tc.has_state_changed:
            self.cache.save(tc.serialize())

    def device_login(self, show: Callable[[str], None]) -> dict[str, Any]:
        app, tc = self._app()
        flow = app.initiate_device_flow(scopes=[self.org.api_scope])
        if "user_code" not in flow:
            raise TslError("E-AUTH-01", "device flow failed")
        show(str(flow["message"]))
        res: dict[str, Any] = app.acquire_token_by_device_flow(flow)
        if "access_token" not in res:
            raise TslError("E-AUTH-01", "login failed")
        if res.get("id_token_claims", {}).get("tid") != self.org.tenant_id:
            self.cache.clear()
            raise TslError("E-AUTH-01", "wrong tenant")
        self._persist(tc)
        return res

    def silent_token(self, force_refresh: bool = False) -> str:
        app, tc = self._app()
        accounts = app.get_accounts()
        if not accounts:
            raise TslError("E-AUTH-01")
        res = app.acquire_token_silent(
            [self.org.api_scope], account=accounts[0], force_refresh=force_refresh
        )
        self._persist(tc)
        if not res or "access_token" not in res:
            raise TslError("E-AUTH-01")
        return str(res["access_token"])

    def logout(self) -> None:
        self.cache.clear()
