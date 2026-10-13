"""Entra ID access-token validation with PyJWT and JWKS (SDD-07 §9, ADR 0002).

No custom JWT parsing and no bypass. The JWKS comes from Microsoft's published endpoint, or from a
JWKS document on disk named by ``ENTRA_JWKS_FILE`` (used by tests with a locally generated key and
by hosts without outbound access). Either way every check below runs.
"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Literal

import jwt
from jwt import PyJWK, PyJWKClient, PyJWKSet

from app.config import Settings

ClientKind = Literal["tsl", "portal"]


class TokenInvalid(Exception):
    """Any validation failure; the message is a short reason label for metrics (never the token)."""


@dataclass(frozen=True)
class EntraClaims:
    oid: str
    tid: str
    client: ClientKind
    scopes: frozenset[str]
    roles: frozenset[str]
    name: str | None = None
    email: str | None = None
    raw: dict[str, Any] = field(default_factory=dict, compare=False, repr=False)


class EntraValidator:
    def __init__(self, settings: Settings) -> None:
        self.s = settings
        self._lock = threading.Lock()
        self._client: PyJWKClient | None = None
        self._set: PyJWKSet | None = None
        self.loaded_at: float | None = None
        if settings.entra_jwks_file:
            self._set = PyJWKSet.from_json(settings.entra_jwks_file.read_text(encoding="utf-8"))
            self.loaded_at = time.time()
        else:
            self._client = PyJWKClient(settings.jwks_url, cache_keys=True, lifespan=3600)

    def refresh(self) -> bool:
        """Fetch the JWKS (readiness check). True when keys are cached and younger than 24 h."""
        if self._set is not None:
            return True
        assert self._client is not None  # noqa: S101 - one of the two is always set
        try:
            with self._lock:
                self._client.get_jwk_set(refresh=True)
                self.loaded_at = time.time()
        except Exception:
            return self.loaded_at is not None and time.time() - self.loaded_at < 86400
        return True

    def _key(self, token: str) -> PyJWK:
        header = jwt.get_unverified_header(token)
        if header.get("alg") != "RS256":
            raise TokenInvalid("alg")
        kid = header.get("kid")
        if self._set is not None:
            for k in self._set.keys:
                if k.key_id == kid:
                    return k
            raise TokenInvalid("kid")
        assert self._client is not None  # noqa: S101
        try:
            key = self._client.get_signing_key_from_jwt(token)
            self.loaded_at = self.loaded_at or time.time()
            return key
        except jwt.PyJWKClientError as exc:
            raise TokenInvalid("jwks") from exc

    def validate(self, token: str) -> EntraClaims:
        try:
            key = self._key(token)
            claims: dict[str, Any] = jwt.decode(
                token,
                key=key.key,
                algorithms=["RS256"],
                audience=self.s.entra_api_audience,
                issuer=self.s.issuer,
                leeway=self.s.entra_leeway_s,
                options={"require": ["exp", "nbf", "iss", "aud", "tid", "oid"]},
            )
        except jwt.ExpiredSignatureError as exc:
            raise TokenInvalid("expired") from exc
        except jwt.InvalidAudienceError as exc:
            raise TokenInvalid("audience") from exc
        except jwt.InvalidIssuerError as exc:
            raise TokenInvalid("issuer") from exc
        except jwt.PyJWTError as exc:
            raise TokenInvalid("invalid") from exc
        if str(claims.get("tid")) != self.s.entra_tenant_id:
            raise TokenInvalid("tenant")
        azp = str(claims.get("azp") or "")
        scopes = frozenset(str(claims.get("scp") or "").split())
        client: ClientKind
        if azp and azp == self.s.entra_tsl_client_id:
            client = "tsl"
            if "Events.Write" not in scopes:
                raise TokenInvalid("scope")
        elif azp and azp == self.s.entra_portal_client_id:
            client = "portal"
            if not scopes & {"Portal.Read", "Portal.Write"}:
                raise TokenInvalid("scope")
        else:
            raise TokenInvalid("client")
        roles = claims.get("roles") or []
        return EntraClaims(
            oid=str(claims["oid"]),
            tid=str(claims["tid"]),
            client=client,
            scopes=scopes,
            roles=frozenset(str(r) for r in roles) if isinstance(roles, list) else frozenset(),
            name=str(claims["name"]) if claims.get("name") else None,
            email=str(claims.get("preferred_username") or claims.get("email") or "") or None,
            raw=claims,
        )


def jwks_from_public_key_json(jwk: dict[str, Any]) -> str:
    """Helper for tests and tooling: wrap one JWK into a JWKS document."""
    return json.dumps({"keys": [jwk]})
