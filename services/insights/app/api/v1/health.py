"""``GET /v1/health`` (liveness, no DB call) and ``GET /v1/health/ready`` (OPS-02 §4).

``/healthz`` and ``/readyz`` are the same probes for a hosting platform's health check (the hosted
test environment, deploy/render). They are outside the OpenAPI file, and ``/readyz`` answers only
ok or fail: the per-check detail stays on the internal ``/v1/health/ready`` and in the log.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from app import __version__
from app.obs.probe import readiness

log = logging.getLogger("insights.api")
router = APIRouter(tags=["health"])


@router.get("/v1/health", summary="Liveness")
def health() -> dict[str, Any]:
    return {"status": "ok", "version": __version__}


@router.get("/v1/health/ready", summary="Readiness: DB, migration head, secrets, JWKS")
async def ready(request: Request) -> JSONResponse:
    ok, checks = await run_in_threadpool(
        readiness, request.app.state.settings, request.app.state.entra
    )
    return JSONResponse(
        {"status": "ok" if ok else "fail", "checks": checks}, status_code=200 if ok else 503
    )


@router.get("/healthz", include_in_schema=False)
def healthz() -> dict[str, Any]:
    return {"status": "ok"}


@router.get("/readyz", include_in_schema=False)
async def readyz(request: Request) -> JSONResponse:
    ok, checks = await run_in_threadpool(
        readiness, request.app.state.settings, request.app.state.entra
    )
    if not ok:
        failed = ",".join(k for k, v in checks.items() if v != "ok")
        log.warning("readyz failed", extra={"code": failed})
    return JSONResponse({"status": "ok" if ok else "fail"}, status_code=200 if ok else 503)
