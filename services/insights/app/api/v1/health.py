"""``GET /v1/health`` (liveness, no DB call) and ``GET /v1/health/ready`` (OPS-02 §4)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from app import __version__
from app.obs.probe import readiness

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
