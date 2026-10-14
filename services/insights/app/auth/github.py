"""GitHub as the interim identity provider (ADR 0006, SDD-07 §1.4).

Only active when ``IDENTITY_PROVIDER=github``. Two jobs, both plain OAuth 2.0 against GitHub through
``httpx``; nothing here signs or parses tokens itself:

- ``GitHubValidator.validate``: a bearer token is valid when ``GET {GITHUB_API_URL}/user`` answers
  200. The answer (numeric ``id``, ``login``, ``name``) is cached for ``GITHUB_TOKEN_CACHE_S``
  (5 minutes) under the SHA-256 of the token; the token itself is never stored or logged.
- ``GitHubWebFlow``: the portal's backend-for-frontend sign-in (authorization code with ``state``
  and PKCE S256, code exchanged server-side with the client secret).

Tests inject an ``httpx.MockTransport``; no test talks to GitHub.
"""

from __future__ import annotations

import base64
import hashlib
import secrets
import threading
import time
import uuid
from collections import OrderedDict
from dataclasses import dataclass
from urllib.parse import urlencode

import httpx

from app.auth.entra import TokenInvalid
from app.config import Settings

# users.tenant_id / users.sso_subject are uuid columns (Entra tid / oid). GitHub users get a fixed
# namespace tenant and a name-based UUID of "github:<id>", so they never collide with Entra rows.
GITHUB_TENANT = str(uuid.uuid5(uuid.NAMESPACE_URL, "https://github.com"))
SCOPE = "read:user"
CACHE_MAX = 1024


class GitHubUnavailable(Exception):
    """GitHub could not be asked (network error or 5xx). The caller answers 503, not 401."""


@dataclass(frozen=True)
class GitHubUser:
    id: int
    login: str
    name: str | None = None

    @property
    def subject(self) -> str:
        """The user identity, the ``oid`` equivalent: ``github:<numeric id>``."""
        return f"github:{self.id}"

    @property
    def sso_subject(self) -> str:
        return str(uuid.uuid5(uuid.NAMESPACE_URL, self.subject))


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class GitHubValidator:
    def __init__(self, settings: Settings, transport: httpx.BaseTransport | None = None) -> None:
        self.s = settings
        self.transport = transport
        self.ttl = float(settings.github_token_cache_s)
        self._cache: OrderedDict[str, tuple[float, GitHubUser]] = OrderedDict()
        self._lock = threading.Lock()
        self.clock = time.monotonic

    def _client(self) -> httpx.Client:
        return httpx.Client(
            transport=self.transport,
            timeout=5.0,
            headers={"Accept": "application/vnd.github+json", "User-Agent": "truminds-insights"},
        )

    def validate(self, token: str) -> GitHubUser:
        key = token_digest(token)
        now = self.clock()
        with self._lock:
            hit = self._cache.get(key)
            if hit is not None and now - hit[0] < self.ttl:
                return hit[1]
            self._cache.pop(key, None)
        try:
            with self._client() as c:
                r = c.get(
                    self.s.github_api_url.rstrip("/") + "/user",
                    headers={"Authorization": f"Bearer {token}"},
                )
        except httpx.HTTPError as exc:
            raise GitHubUnavailable(type(exc).__name__) from None
        if r.status_code in (401, 403):
            raise TokenInvalid("github")
        if r.status_code != 200:
            raise GitHubUnavailable(f"HTTP {r.status_code}")
        body = r.json()
        if (
            not isinstance(body, dict)
            or not isinstance(body.get("id"), int)
            or not body.get("login")
        ):
            raise TokenInvalid("github_user")
        user = GitHubUser(
            int(body["id"]), str(body["login"]), str(body["name"]) if body.get("name") else None
        )
        with self._lock:
            self._cache[key] = (now, user)
            while len(self._cache) > CACHE_MAX:
                self._cache.popitem(last=False)
        return user

    def forget(self, token: str) -> None:
        with self._lock:
            self._cache.pop(token_digest(token), None)


def pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


class GitHubWebFlow:
    """Authorization-code flow for the portal (backend-for-frontend)."""

    def __init__(self, settings: Settings, transport: httpx.BaseTransport | None = None) -> None:
        self.s = settings
        self.transport = transport

    @property
    def redirect_uri(self) -> str:
        return self.s.public_base_url.rstrip("/") + "/auth/github/callback"

    def authorize_url(self, state: str, challenge: str) -> str:
        q = urlencode(
            {
                "client_id": self.s.github_client_id,
                "redirect_uri": self.redirect_uri,
                "scope": SCOPE,
                "state": state,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "allow_signup": "false",
            }
        )
        return f"{self.s.github_oauth_url.rstrip('/')}/login/oauth/authorize?{q}"

    def exchange(self, code: str, verifier: str) -> str:
        """Code -> user access token, with the client secret, server-side only."""
        try:
            with httpx.Client(
                transport=self.transport, timeout=10.0, headers={"Accept": "application/json"}
            ) as c:
                r = c.post(
                    self.s.github_oauth_url.rstrip("/") + "/login/oauth/access_token",
                    data={
                        "client_id": self.s.github_client_id,
                        "client_secret": self.s.github_secret(),
                        "code": code,
                        "redirect_uri": self.redirect_uri,
                        "code_verifier": verifier,
                    },
                )
        except httpx.HTTPError as exc:
            raise GitHubUnavailable(type(exc).__name__) from None
        try:
            body = r.json()
        except ValueError:
            body = None
        if r.status_code != 200 or not isinstance(body, dict) or not body.get("access_token"):
            err = body.get("error") if isinstance(body, dict) else None
            raise TokenInvalid(str(err or f"exchange_http_{r.status_code}"))
        return str(body["access_token"])
