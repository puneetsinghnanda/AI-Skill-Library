"""``POST /v1/events`` (SDD-08 §4, Doc 5 §5.2)."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from app.api.deps import events_writer, require_engineer_app_role
from app.auth.principal import Principal
from app.config import Settings
from app.db import tx
from app.errors import ServiceError
from app.ingest.service import ingest

router = APIRouter(tags=["ingest"])

BATCH_SCHEMA: dict[str, Any] = {
    "requestBody": {
        "required": True,
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "required": ["events"],
                    "properties": {
                        "events": {
                            "type": "array",
                            "maxItems": 500,
                            "items": {
                                "$ref": "https://schemas.truminds.internal/event-envelope.v1.json"
                            },
                        }
                    },
                }
            }
        },
    },
    "responses": {
        "202": {
            "description": "BatchResult {accepted, duplicates[], rejected[{event_id, code, "
            "reason}]}"
        },
        "400": {"description": "E-ING-06 batch is not JSON or events missing"},
        "401": {"description": "E-ING-07 token invalid"},
        "413": {"description": "More than 500 events or 1 MiB"},
        "429": {"description": "Rate limited; honour Retry-After"},
    },
}


@router.post(
    "/v1/events", status_code=202, summary="Ingest a batch of events", openapi_extra=BATCH_SCHEMA
)
async def post_events(request: Request, p: Principal = Depends(events_writer)) -> JSONResponse:
    s: Settings = request.app.state.settings
    if p.kind == "entra":
        require_engineer_app_role(p)
    raw = await request.body()
    if len(raw) > s.max_body_bytes:
        return JSONResponse(
            {"code": "E-ING-06", "detail": "Body larger than 1 MiB"}, status_code=413
        )
    try:
        payload = json.loads(raw)
    except ValueError:
        raise ServiceError("E-ING-06", "Batch is not JSON") from None
    if not isinstance(payload, dict) or not isinstance(payload.get("events"), list):
        raise ServiceError("E-ING-06", "events missing")
    events: list[Any] = payload["events"]
    if len(events) > s.max_batch_events:
        return JSONResponse({"code": "E-ING-06", "detail": "More than 500 events"}, status_code=413)
    source = "ci" if p.kind == "ci" else "tsl"
    user_id = p.user.id if p.user else None

    def work() -> dict[str, Any]:
        with tx("app", s) as conn:
            return ingest(conn, s, request.app.state.schemas, events, source, user_id).body()

    body = await run_in_threadpool(work)
    return JSONResponse(body, status_code=202)
