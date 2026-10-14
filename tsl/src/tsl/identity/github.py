"""GitHub sign-in through the OAuth 2.0 Device Authorization Grant (ADR 0006, SDD-07 §"Identity
providers"). Interim provider for the test phase; production uses Entra (identity/entra.py).

Same interface as ``MsalIdentity``: ``device_login``, ``silent_token``, ``logout``.

- ``POST {github_oauth_url}/login/device/code`` with ``client_id`` and ``scope=read:user``.
- The user opens ``verification_uri`` and types ``user_code``.
- ``POST {github_oauth_url}/login/oauth/access_token`` with the device-code grant type, polled at
  ``interval`` seconds; ``slow_down`` adds 5 seconds (RFC 8628 §3.5); ``expired_token`` and
  ``access_denied`` end the flow.

The token is kept in a sealed file (AES-256-GCM, key in the OS keychain), the same mechanism as the
MSAL cache (SDD-07 §4.3). It is never written in clear and never logged. Only a public OAuth App
client id is used; tsl holds no client secret. Tests pass an ``httpx.MockTransport`` and a fake
sleep; no test talks to GitHub.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx

from tsl.core.errors import TslError
from tsl.identity.entra import SealedCache
from tsl.identity.keystore import KeyStore
from tsl.identity.org import OrgConfig

TOKEN_KEY_ITEM = "github-token-key"  # noqa: S105 - keychain item name, not a secret
TOKEN_LABEL = b"tsl-github-token-v1"
SCOPE = "read:user"
GRANT = "urn:ietf:params:oauth:grant-type:device_code"
NEXT = "tsl login"


class GitHubIdentity:
    def __init__(
        self,
        org: OrgConfig,
        cache: SealedCache,
        *,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
        timeout_s: float = 10.0,
    ) -> None:
        self.org = org
        self.cache = cache
        self._transport = transport
        self._sleep = sleep
        self._now = monotonic
        self._timeout = timeout_s

    # ------------------------------------------------------------------ helpers
    def _client(self) -> httpx.Client:
        return httpx.Client(
            transport=self._transport,
            timeout=self._timeout,
            headers={"Accept": "application/json", "User-Agent": "truminds-tsl"},
        )

    def _require_config(self) -> None:
        if not self.org.configured or not self.org.github_client_id:
            raise TslError(
                "E-AUTH-01",
                "This tsl build has no GitHub sign-in configuration.",
                next="Install the tsl build made with the test org file (deploy/README.md)",
            )

    def _post(self, client: httpx.Client, path: str, data: dict[str, str]) -> dict[str, Any]:
        url = self.org.github_oauth_url.rstrip("/") + path
        try:
            r = client.post(url, data=data)
        except httpx.HTTPError:
            raise TslError("E-NET-02") from None
        try:
            body = r.json()
        except ValueError:
            body = None
        if not isinstance(body, dict):
            raise TslError("E-AUTH-01", f"GitHub answered HTTP {r.status_code}", next=NEXT)
        return body

    def _user(self, client: httpx.Client, token: str) -> dict[str, Any] | None:
        """``GET {github_api_url}/user``: None when GitHub rejects the token (401)."""
        try:
            r = client.get(
                self.org.github_api_url.rstrip("/") + "/user",
                headers={"Authorization": f"Bearer {token}"},
            )
        except httpx.HTTPError:
            raise TslError("E-NET-02") from None
        if r.status_code == 401:
            return None
        if r.status_code != 200:
            raise TslError("E-NET-02")
        body = r.json()
        return body if isinstance(body, dict) else None

    def _load(self) -> dict[str, Any] | None:
        text = self.cache.load()
        if not text:
            return None
        try:
            data = json.loads(text)
        except ValueError:
            return None
        if not isinstance(data, dict) or not data.get("access_token"):
            return None
        return data

    # ------------------------------------------------------------------ IdentityProvider
    def device_login(self, show: Callable[[str], None]) -> dict[str, Any]:
        self._require_config()
        cid = self.org.github_client_id
        with self._client() as client:
            start = self._post(client, "/login/device/code", {"client_id": cid, "scope": SCOPE})
            if "device_code" not in start or "user_code" not in start:
                raise TslError(
                    "E-AUTH-01",
                    f"GitHub device flow refused: {start.get('error', 'unknown')}",
                    next="Check that Device Flow is enabled on the GitHub OAuth App",
                )
            show(
                f"To sign in, open {start.get('verification_uri', 'https://github.com/login/device')}"
                f" and enter the code {start['user_code']}."
            )
            interval = float(start.get("interval") or 5)
            deadline = self._now() + float(start.get("expires_in") or 900)
            token: str | None = None
            while token is None:
                if self._now() >= deadline:
                    raise TslError("E-AUTH-01", "The sign-in code expired.", next=NEXT)
                self._sleep(interval)
                res = self._post(
                    client,
                    "/login/oauth/access_token",
                    {
                        "client_id": cid,
                        "device_code": str(start["device_code"]),
                        "grant_type": GRANT,
                    },
                )
                err = res.get("error")
                if res.get("access_token"):
                    token = str(res["access_token"])
                elif err == "authorization_pending":
                    continue
                elif err == "slow_down":
                    interval = max(interval + 5, float(res.get("interval") or 0))
                elif err == "expired_token":
                    raise TslError("E-AUTH-01", "The sign-in code expired.", next=NEXT)
                elif err == "access_denied":
                    raise TslError("E-AUTH-01", "Sign-in was cancelled on GitHub.", next=NEXT)
                else:
                    raise TslError("E-AUTH-01", f"GitHub sign-in failed: {err}", next=NEXT)
            user = self._user(client, token) or {}
        # No "oid" claim: the service's GET /v1/me (github:<id>) is the authoritative subject.
        claims: dict[str, Any] = {"login": user.get("login")} if user.get("login") else {}
        self.cache.save(json.dumps({"access_token": token, "login": user.get("login")}))
        return {"access_token": token, "id_token_claims": claims}

    def silent_token(self, force_refresh: bool = False) -> str:
        """The stored token. GitHub OAuth App tokens do not expire and cannot be refreshed: with
        ``force_refresh`` (the service said 401) the token is checked against GitHub and, when
        GitHub rejects it, deleted so the next ``tsl login`` starts a new device flow."""
        self._require_config()
        data = self._load()
        if data is None:
            raise TslError("E-AUTH-01", next=NEXT)
        token = str(data["access_token"])
        if force_refresh:
            with self._client() as client:
                if self._user(client, token) is None:
                    self.cache.clear()
                    raise TslError("E-AUTH-01", "GitHub rejected the stored token.", next=NEXT)
        return token

    def logout(self) -> None:
        self.cache.clear()


def github_cache(path: Path, keystore: KeyStore, device_id: str) -> SealedCache:
    """The sealed file for the GitHub token: its own keychain item and AAD label."""
    return SealedCache(path, keystore, device_id, key_item=TOKEN_KEY_ITEM, label=TOKEN_LABEL)
