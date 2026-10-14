"""``create_app()``: routers, middleware, error handling (SDD-08 §3.1).

Every route is in the published OpenAPI file except the OTLP paths (protocol-defined),
``/metrics`` on the internal port, the platform probes ``/healthz`` and ``/readyz``, and the built
portal when this service serves it. There are no admin, debug or bypass routes.
"""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.exc import OperationalError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import __version__
from app.api import auth_github
from app.api.v1 import (
    admin,
    admin_lists,
    events,
    health,
    improvement,
    keys,
    me,
    otel,
    policy,
    signatures,
    systems,
    webhooks_github,
)
from app.api.v1.read import catalogue, insights, pods, runs, status
from app.auth.entra import EntraValidator
from app.auth.github import GitHubValidator, GitHubWebFlow
from app.auth.principal import RateLimiter
from app.config import Settings, get_settings
from app.errors import ServiceError
from app.ingest.schemas import load as load_schemas
from app.obs import logging as obslog
from app.obs import metrics

log = logging.getLogger("insights.api")
# Security headers for the portal when this service serves it itself (SERVE_PORTAL_DIR; the hosted
# and one-machine test environments). The same set as portal/nginx.conf; the CSP drops the Entra
# login host when the portal signs in with GitHub.
PORTAL_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "X-Frame-Options": "DENY",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
}
ENTRA_LOGIN = "https://login.microsoftonline.com"
# Paths the SPA fallback never answers: the API, sign-in, OTLP, metrics and the probes.
NOT_PORTAL = ("/v1", "/auth", "/otel", "/metrics", "/healthz", "/readyz")
PORTAL_ROUTES_UNDER_AUTH = frozenset({"/auth/callback"})  # MSAL redirect, a portal route


def portal_csp(provider: str) -> str:
    login = f" {ENTRA_LOGIN}" if provider == "entra" else ""
    frame = f"frame-src {ENTRA_LOGIN}; " if provider == "entra" else ""
    return (
        "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
        f"font-src 'self'; connect-src 'self'{login}; {frame}frame-ancestors 'none'; "
        "base-uri 'self'; form-action 'self'"
    )


def is_portal_path(path: str) -> bool:
    """True for paths the portal owns; False for API, sign-in, OTLP, metrics and probe paths."""
    if path in PORTAL_ROUTES_UNDER_AUTH:
        return True
    return not any(path == p or path.startswith(p + "/") for p in NOT_PORTAL)


def portal_cache_control(path: str) -> str:
    if path.startswith("/assets/"):
        return "public, max-age=31536000, immutable"
    if path.startswith("/brand/"):
        return "public, max-age=3600"
    return "no-cache"


def _blocked_static(path: str) -> bool:
    """No dotfiles, source maps or the demo-only MSW worker (as portal/nginx.conf)."""
    return "/." in path or path.endswith(".map") or path == "/mockServiceWorker.js"


READ_PREFIXES = metrics.READ_PREFIXES


def _request_id(request: Request) -> str:
    rid = request.headers.get("x-request-id", "")
    try:
        return str(uuid.UUID(rid))
    except ValueError:
        return str(uuid.uuid4())


def create_app(settings: Settings | None = None) -> FastAPI:
    s = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        yield

    app = FastAPI(
        title="Truminds insights service",
        version=__version__,
        description="Telemetry ingest, keys and read API (SDD-08, SDD-09, SDD-07, SDD-10, SDD-11, "
        "SDD-13).",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
    )
    s.check_identity()
    s.check_hosting()
    portal_dir = s.portal_dir
    csp = portal_csp(s.identity_provider)
    hsts = s.public_base_url.lower().startswith("https://")
    app.state.settings = s
    app.state.entra = EntraValidator(s)
    app.state.github = GitHubValidator(s)
    app.state.github_flow = GitHubWebFlow(s)
    app.state.rate_limiter = RateLimiter()
    app.state.schemas = load_schemas(s.schemas_dir)

    @app.middleware("http")
    async def _mw(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        rid = _request_id(request)
        request.state.request_id = rid
        request.state.caller = "anonymous"
        t0 = time.perf_counter()
        path = request.url.path
        if portal_dir is not None and is_portal_path(path) and _blocked_static(path):
            response: Response = _problem(request, ServiceError("E-API-04", "Not found"))
        else:
            response = await call_next(request)
        dt = time.perf_counter() - t0
        route = request.scope.get("route")
        template = getattr(route, "path", "unmatched")
        metrics.observe(template, request.method, response.status_code, dt)
        response.headers["X-Request-ID"] = rid
        if portal_dir is not None:
            if is_portal_path(path):
                response.headers.update(PORTAL_HEADERS)
                response.headers["Content-Security-Policy"] = csp
                response.headers["Cache-Control"] = portal_cache_control(path)
            else:
                response.headers.setdefault("X-Content-Type-Options", "nosniff")
                response.headers.setdefault("Referrer-Policy", "no-referrer")
            if hsts:
                response.headers["Strict-Transport-Security"] = "max-age=31536000"
        if template.startswith(READ_PREFIXES) and request.method == "GET":
            response.headers.setdefault("Cache-Control", "private, max-age=60")
        log.info(
            "request",
            extra={
                "request_id": rid,
                "route": template,
                "method": request.method,
                "status": response.status_code,
                "duration_ms": int(dt * 1000),
                "caller": getattr(request.state, "caller", "anonymous"),
            },
        )
        return response

    def _problem(request: Request, err: ServiceError) -> JSONResponse:
        rid = getattr(request.state, "request_id", str(uuid.uuid4()))
        return JSONResponse(
            err.problem(rid, s.public_base_url),
            status_code=err.status,
            headers=err.headers,
            media_type="application/problem+json",
        )

    @app.exception_handler(ServiceError)
    async def _svc(request: Request, exc: ServiceError) -> JSONResponse:
        if exc.code in ("E-API-03", "E-API-04"):
            route = getattr(request.scope.get("route"), "path", "unmatched")
            metrics.READ_SCOPE_DENIED.labels(route=route, code=exc.code).inc()
        return _problem(request, exc)

    @app.exception_handler(RequestValidationError)
    async def _val(request: Request, exc: RequestValidationError) -> JSONResponse:
        path = request.url.path
        code = "E-ING-06" if path.startswith("/v1/events") else "E-API-01"
        first = exc.errors()[0] if exc.errors() else {}
        detail = f"{'.'.join(str(x) for x in first.get('loc', []))}: {first.get('msg', 'invalid')}"
        return _problem(request, ServiceError(code, detail[:200], status=400))

    @app.exception_handler(OperationalError)
    async def _db(request: Request, exc: OperationalError) -> JSONResponse:
        log.error("database unavailable", extra={"code": "E-API-06"})
        return _problem(
            request, ServiceError("E-API-06", "Database unavailable or statement timeout")
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException) -> Response:
        if exc.status_code == 404:
            path = request.url.path
            if (
                portal_dir is not None
                and request.method in ("GET", "HEAD")
                and is_portal_path(path)
                and not _blocked_static(path)
                and not path.startswith(("/assets/", "/brand/"))
            ):
                index = portal_dir / "index.html"
                if index.exists():
                    return FileResponse(index)
            return _problem(request, ServiceError("E-API-04", "Not found"))
        if exc.status_code == 405:
            return JSONResponse({"detail": "Method not allowed"}, status_code=405)
        return JSONResponse({"detail": str(exc.detail)}, status_code=exc.status_code)

    if s.identity_provider == "github":
        _github_session(app, s)

    for module in (
        auth_github,
        health,
        events,
        keys,
        signatures,
        me,
        systems,
        policy,
        webhooks_github,
        status,
        catalogue,
        pods,
        insights,
        runs,
        improvement,
        admin,
        admin_lists,
    ):
        app.include_router(module.router)
    # OTLP/HTTP paths are protocol-defined and not in the OpenAPI file (SDD-08 §9.1).
    app.include_router(otel.router, include_in_schema=False)

    if portal_dir is not None and portal_dir.exists():
        from fastapi.staticfiles import StaticFiles

        app.mount(
            "/assets",
            StaticFiles(directory=portal_dir / "assets", check_dir=False),
            name="assets",
        )
        app.mount(
            "/brand",
            StaticFiles(directory=portal_dir / "brand", check_dir=False),
            name="brand",
        )
    return app


def _github_session(app: FastAPI, s: Settings) -> None:
    """GitHub interim provider (ADR 0006): signed session cookie, visible startup record."""
    from starlette.middleware.sessions import SessionMiddleware

    from app.auth.session import COOKIE, cookie_secure, is_local, signing_key

    app.add_middleware(
        SessionMiddleware,
        secret_key=signing_key(s),
        session_cookie=COOKIE,
        max_age=s.session_max_age_s,
        same_site="lax",
        https_only=cookie_secure(s),
    )
    admins = ",".join(s.bootstrap_admin_github_logins) or "(none)"
    log.warning(
        f"identity provider github (interim, ADR 0006); environment={s.env}; "
        f"BOOTSTRAP_ADMIN_GITHUB_LOGINS={admins}; cookie_secure={cookie_secure(s)}"
    )
    if not cookie_secure(s) and not is_local(s):
        log.warning(
            "PUBLIC_BASE_URL is plain http on a non-local host: session cookie and tokens travel "
            "unencrypted on the network; put the test host behind HTTPS when possible"
        )


def _lazy_app() -> FastAPI:
    obslog.setup("api")
    return create_app()


def __getattr__(name: str) -> FastAPI:
    # `uvicorn app.main:app` builds the app on first access, so importing this module (tests,
    # OpenAPI generation) never needs environment configuration.
    if name == "app":
        return _lazy_app()
    raise AttributeError(name)
