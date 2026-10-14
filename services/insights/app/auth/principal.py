"""Authenticated caller and the FastAPI dependencies that build it (SDD-08 §9.1, SDD-07 §9)."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Literal

from fastapi import Request
from sqlalchemy import Connection

from app.auth import ingest_tokens
from app.auth.entra import ClientKind, EntraClaims, EntraValidator, TokenInvalid
from app.auth.github import GITHUB_TENANT, GitHubUnavailable, GitHubValidator
from app.auth.scope import Scope, resolve_scope
from app.auth.session import require_csrf, session_of, session_token
from app.auth.users import (
    APP_ROLES,
    Grant,
    User,
    effective_grants,
    resolve_github_user,
    resolve_user,
)
from app.config import Settings
from app.db import tx
from app.errors import ServiceError
from app.obs import metrics

# "entra" is an interactive user's token: Microsoft Entra ID, or GitHub while IDENTITY_PROVIDER is
# "github" (ADR 0006; Principal.provider says which). "ci" and "otel" are ingest tokens.
Kind = Literal["entra", "ci", "otel"]
RouteKind = Literal["ingest", "read", "write", "otel"]


@dataclass
class Principal:
    kind: Kind
    claims: EntraClaims | None = None
    user: User | None = None
    grants: list[Grant] = field(default_factory=list)
    token_id: str | None = None
    token_label: str | None = None
    provider: Literal["entra", "github"] = "entra"
    via_cookie: bool = False
    _scope: Scope | None = None

    @property
    def caller(self) -> str:
        if self.user is not None:
            return self.user.pseudonym
        if self.kind == "ci":
            return f"ci:{self.token_label}"
        return self.kind

    @property
    def is_admin_app_role(self) -> bool:
        return self.claims is not None and "Admin" in self.claims.roles

    def has(self, role: str) -> bool:
        return any(g.role == role for g in self.grants)

    def scope(self, conn: Connection, s: Settings) -> Scope:
        if self._scope is None:
            self._scope = resolve_scope(conn, s, self.grants)
        return self._scope


class RateLimiter:
    """Token bucket per caller and route group (SDD-08 §4.1, SDD-09 §5.1.1). Per process."""

    def __init__(self) -> None:
        self._b: dict[tuple[str, str], tuple[float, float]] = {}
        self._lock = threading.Lock()

    def take(self, key: str, group: str, rate: float, burst: int) -> float | None:
        now = time.monotonic()
        with self._lock:
            tokens, last = self._b.get((key, group), (float(burst), now))
            tokens = min(float(burst), tokens + (now - last) * rate)
            if tokens < 1.0:
                self._b[(key, group)] = (tokens, now)
                return (1.0 - tokens) / rate
            self._b[(key, group)] = (tokens - 1.0, now)
            return None


def bearer(request: Request) -> str | None:
    h = request.headers.get("authorization", "")
    if h[:7].lower() == "bearer " and h[7:].strip():
        return h[7:].strip()
    return None


def _unauth(route: RouteKind) -> str:
    return "E-API-02" if route in ("read",) else "E-ING-07"


def authenticate(
    request: Request,
    *,
    route: RouteKind,
    scopes: set[str],
    allow: set[Kind],
    clients: set[str] | None = None,
) -> Principal:
    """Validate the caller for one route. No bypass: every credential is checked here."""
    s: Settings = request.app.state.settings
    tok = bearer(request)
    code = _unauth(route)
    via_cookie = False
    if tok is None and s.identity_provider == "github":
        tok = session_token(request, s)  # portal session cookie (SDD-09 §3.4.1)
        via_cookie = tok is not None
    if tok is None:
        metrics.AUTH_FAILURES.labels(kind="none", reason="missing").inc()
        raise ServiceError(code, "Missing bearer token")
    if not via_cookie and ingest_tokens.looks_like_ingest_token(tok):
        with tx("app", s) as conn:
            it = ingest_tokens.check(conn, tok)
        if it is None or it.kind not in allow:
            metrics.AUTH_FAILURES.labels(kind="ingest_token", reason="invalid").inc()
            raise ServiceError(code, "Ingest token invalid or not allowed here")
        return Principal(kind=it.kind, token_id=it.id, token_label=it.label)
    if "entra" not in allow:
        metrics.AUTH_FAILURES.labels(kind="entra", reason="not_allowed").inc()
        raise ServiceError(code, "User tokens are not accepted on this route")
    if s.identity_provider == "github":
        p = _github_principal(request, s, tok, route, scopes, clients, via_cookie, code)
    else:
        validator: EntraValidator = request.app.state.entra
        try:
            claims = validator.validate(tok)
        except TokenInvalid as exc:
            metrics.AUTH_FAILURES.labels(kind="entra", reason=str(exc)).inc()
            raise ServiceError(code, "Token invalid, expired, wrong audience or tenant") from None
        if not (claims.scopes & scopes) or (clients is not None and claims.client not in clients):
            metrics.AUTH_FAILURES.labels(kind="entra", reason="scope").inc()
            raise ServiceError(code, "Token scope does not allow this route")
        with tx("app", s) as conn:
            user = resolve_user(conn, s, claims)
            grants = effective_grants(conn, user, claims.roles)
        p = Principal(kind="entra", claims=claims, user=user, grants=grants)
    assert p.user is not None  # noqa: S101 - both branches set the user
    rl: RateLimiter = request.app.state.rate_limiter
    group = "ingest" if route in ("ingest", "otel") else "read"
    rate, burst = (
        (s.ingest_rate_per_s, s.ingest_burst)
        if group == "ingest"
        else (s.read_rate_per_s, s.read_burst)
    )
    wait = rl.take(p.user.id, group, rate, burst)
    if wait is not None:
        metrics.RATE_LIMITED.labels(route_group=group).inc()
        raise ServiceError(
            "E-API-05",
            "Rate limited",
            status=429,
            headers={"Retry-After": str(max(1, int(wait + 0.999)))},
        )
    request.state.caller = p.caller
    return p


# GitHub tokens carry no scope or client id (ADR 0006). The pairing is by credential and route:
# - bearer token (tsl, or a script): Events.Write and Portal.Read; client "tsl" on ingest and write
#   routes, "portal" on read routes. Never Portal.Write.
# - portal session cookie: Portal.Read and Portal.Write, client "portal"; writes need the CSRF
#   header and same-origin Origin (E-API-07).
BEARER_SCOPES = frozenset({"Events.Write", "Portal.Read"})
COOKIE_SCOPES = frozenset({"Portal.Read", "Portal.Write"})


def _github_principal(
    request: Request,
    s: Settings,
    tok: str,
    route: RouteKind,
    scopes: set[str],
    clients: set[str] | None,
    via_cookie: bool,
    code: str,
) -> Principal:
    client: ClientKind
    if via_cookie:
        require_csrf(request, s)
        client, granted = "portal", COOKIE_SCOPES
    else:
        client, granted = ("portal" if route == "read" else "tsl"), BEARER_SCOPES
    validator: GitHubValidator = request.app.state.github
    try:
        gh = validator.validate(tok)
    except TokenInvalid as exc:
        metrics.AUTH_FAILURES.labels(kind="github", reason=str(exc)).inc()
        if via_cookie:
            sess = session_of(request)
            if sess is not None:
                sess.clear()
        raise ServiceError(code, "GitHub token invalid or revoked") from None
    except GitHubUnavailable:
        metrics.AUTH_FAILURES.labels(kind="github", reason="unavailable").inc()
        raise ServiceError("E-AUTH-10", "GitHub could not be reached; try again") from None
    if not (granted & scopes) or (clients is not None and client not in clients):
        metrics.AUTH_FAILURES.labels(kind="github", reason="scope").inc()
        raise ServiceError(code, "This credential does not allow this route")
    with tx("app", s) as conn:
        user, roles, grants = resolve_github_user(conn, s, gh)
    # Checked after the commit: the user row stays, so an admin can find it and grant roles.
    if not user.active:
        raise ServiceError("E-AUTH-08", "Account deactivated")
    if not roles & APP_ROLES:
        raise ServiceError(
            "E-AUTH-08",
            f"No Truminds role yet. Ask an admin to grant a role to {user.pseudonym} "
            f"(GitHub @{gh.login}).",
        )
    claims = EntraClaims(
        oid=gh.subject,
        tid=GITHUB_TENANT,
        client=client,
        scopes=frozenset(granted),
        roles=roles,
        name=gh.name,
    )
    return Principal(
        kind="entra",
        claims=claims,
        user=user,
        grants=grants,
        provider="github",
        via_cookie=via_cookie,
    )
