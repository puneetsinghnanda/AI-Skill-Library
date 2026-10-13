"""E02 ``GET /v1/status`` (SDD-09 §5.6.2)."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy import text

from app import __version__
from app.api.deps import portal_read
from app.auth.principal import Principal
from app.config import Settings
from app.db import tx
from app.read.common import envelope
from app.timeutil import iso, utcnow

router = APIRouter(tags=["read"])
MVIEWS = [
    "mv_skill_daily",
    "mv_cause_daily",
    "mv_override_daily",
    "mv_run_daily",
    "mv_pr_daily",
    "mv_ci_daily",
    "mv_pod_engagement",
]


@router.get("/v1/status", summary="E02 freshness of the data behind the portal")
def status(request: Request, p: Principal = Depends(portal_read)) -> dict[str, Any]:
    s: Settings = request.app.state.settings
    with tx("read", s) as conn:
        last_event = conn.execute(text("SELECT max(received_at) FROM event_ids")).scalar()
        refreshed = conn.execute(
            text(
                "SELECT min(refreshed_at), count(*) FROM view_refresh_log WHERE view_name = ANY(:v)"
            ),
            {"v": MVIEWS},
        ).one()
        release = conn.execute(
            text("SELECT tag FROM catalogue_releases ORDER BY released_at DESC, tag LIMIT 1")
        ).scalar()
        devices_active = conn.execute(
            text("SELECT count(*) FROM devices WHERE last_seen_at > now() - interval '1 day'")
        ).scalar_one()
    now = utcnow()
    views_old = (
        refreshed[1] < len(MVIEWS)
        or refreshed[0] is None
        or now - refreshed[0] > timedelta(minutes=20)
    )
    silent = devices_active > 0 and (last_event is None or now - last_event > timedelta(hours=2))
    return envelope(
        {
            "last_event_received_at": iso(last_event),
            "views_refreshed_at": iso(refreshed[0]),
            "catalogue_release": release,
            "service_version": __version__,
            "behind": bool(views_old or silent),
        }
    )
