"""Refresh every materialized view CONCURRENTLY and log it (SDD-08 §10.3, OPS-02 SLO-4)."""

from __future__ import annotations

import time

from sqlalchemy import text

from app.config import Settings
from app.db import tx
from app.obs import metrics

VIEWS = [
    "mv_skill_daily",
    "mv_cause_daily",
    "mv_override_daily",
    "mv_run_daily",
    "mv_pr_daily",
    "mv_ci_daily",
    "mv_pod_engagement",
    "skill_window_stats",
]


def run(s: Settings, views: list[str] | None = None) -> dict[str, int]:
    out: dict[str, int] = {}
    for v in views or VIEWS:
        t0 = time.perf_counter()
        try:
            with tx("app", s) as conn:
                conn.execute(text("SELECT insights_refresh_view(:v)"), {"v": v})
                ms = int((time.perf_counter() - t0) * 1000)
                conn.execute(
                    text(
                        "INSERT INTO view_refresh_log (view_name, refreshed_at, duration_ms) "
                        "VALUES "
                        ""
                        "(:v, now(), :d) "
                        "ON CONFLICT (view_name) DO UPDATE SET refreshed_at = "
                        "EXCLUDED.refreshed_at, "
                        "duration_ms = EXCLUDED.duration_ms"
                    ),
                    {"v": v, "d": ms},
                )
            out[v] = ms
            metrics.VIEW_DURATION.labels(view=v).set(ms / 1000)
        except Exception:
            metrics.VIEW_FAILURES.labels(view=v).inc()
            raise
    sample_ages(s)
    return out


def sample_ages(s: Settings) -> None:
    with tx("app", s) as conn:
        for name, age in conn.execute(
            text("SELECT view_name, extract(epoch FROM now() - refreshed_at) FROM view_refresh_log")
        ):
            metrics.VIEW_AGE.labels(view=name).set(float(age))
