"""``create_app()``: routers, middleware, error handling (SDD-08 §3.1).

Every route is in the published OpenAPI file except the OTLP paths (protocol-defined) and
``/metrics`` on the internal port. There are no admin, debug or bypass routes.
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
from app.auth.principal import RateLimiter
from app.config import Settings, get_settings
from app.errors import ServiceError
from app.ingest.schemas import load as load_schemas
from app.obs import logging as obslog
from app.obs import metrics

log = logging.getLogger("insights.api")
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
    app.state.settings = s
    app.state.entra = EntraValidator(s)
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
        response = await call_next(request)
        dt = time.perf_counter() - t0
        route = request.scope.get("route")
        template = getattr(route, "path", "unmatched")
        metrics.observe(template, request.method, response.status_code, dt)
        response.headers["X-Request-ID"] = rid
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
            if (
                s.serve_portal
                and request.method == "GET"
                and not request.url.path.startswith(("/v1/", "/otel/"))
            ):
                index = s.portal_dist_dir / "index.html"
                if index.exists():
                    return FileResponse(index, headers={"Cache-Control": "no-cache"})
            return _problem(request, ServiceError("E-API-04", "Not found"))
        if exc.status_code == 405:
            return JSONResponse({"detail": "Method not allowed"}, status_code=405)
        return JSONResponse({"detail": str(exc.detail)}, status_code=exc.status_code)

    for module in (
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

    if s.serve_portal and s.portal_dist_dir.exists():
        from fastapi.staticfiles import StaticFiles

        app.mount(
            "/assets",
            StaticFiles(directory=s.portal_dist_dir / "assets", check_dir=False),
            name="assets",
        )
    return app


def _lazy_app() -> FastAPI:
    obslog.setup("api")
    return create_app()


def __getattr__(name: str) -> FastAPI:
    # `uvicorn app.main:app` builds the app on first access, so importing this module (tests,
    # OpenAPI generation) never needs environment configuration.
    if name == "app":
        return _lazy_app()
    raise AttributeError(name)
