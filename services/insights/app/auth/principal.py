"""Authenticated caller and the FastAPI dependencies that build it (SDD-08 §9.1, SDD-07 §9)."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Literal

from fastapi import Request
from sqlalchemy import Connection

from app.auth import ingest_tokens
from app.auth.entra import EntraClaims, EntraValidator, TokenInvalid
from app.auth.scope import Scope, resolve_scope
from app.auth.users import Grant, User, effective_grants, resolve_user
from app.config import Settings
from app.db import tx
from app.errors import ServiceError
from app.obs import metrics

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
    if tok is None:
        metrics.AUTH_FAILURES.labels(kind="none", reason="missing").inc()
        raise ServiceError(code, "Missing bearer token")
    if ingest_tokens.looks_like_ingest_token(tok):
        with tx("app", s) as conn:
            it = ingest_tokens.check(conn, tok)
        if it is None or it.kind not in allow:
            metrics.AUTH_FAILURES.labels(kind="ingest_token", reason="invalid").inc()
            raise ServiceError(code, "Ingest token invalid or not allowed here")
        return Principal(kind=it.kind, token_id=it.id, token_label=it.label)
    if "entra" not in allow:
        metrics.AUTH_FAILURES.labels(kind="entra", reason="not_allowed").inc()
        raise ServiceError(code, "Entra tokens are not accepted on this route")
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
    rl: RateLimiter = request.app.state.rate_limiter
    group = "ingest" if route in ("ingest", "otel") else "read"
    rate, burst = (
        (s.ingest_rate_per_s, s.ingest_burst)
        if group == "ingest"
        else (s.read_rate_per_s, s.read_burst)
    )
    wait = rl.take(user.id, group, rate, burst)
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
