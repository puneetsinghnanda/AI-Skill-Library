"""``GET /v1/policy/denylist``: hashed client-name denylist (SEC-01 §7.4)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request

from app.api.deps import tsl_or_ci
from app.auth.principal import Principal
from app.config import Settings
from app.db import tx
from app.ingest.service import load_client_denylist

router = APIRouter(tags=["policy"])


@router.get("/v1/policy/denylist", summary="Client-name denylist hashes")
def denylist(request: Request, p: Principal = Depends(tsl_or_ci)) -> dict[str, Any]:
    s: Settings = request.app.state.settings
    with tx("app", s) as conn:
        d = load_client_denylist(conn)
    return {"version": d.version, "salt": d.salt.hex(), "hashes": sorted(d.hashes)}
