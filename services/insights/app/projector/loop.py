"""Projector loop (SDD-08 §7.1): claims unprojected events and applies handlers. Worker process "
"only."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from sqlalchemy import Connection, text

from app.config import Settings
from app.db import tx
from app.obs import metrics
from app.projector.handlers import HANDLERS, Ev, Parked
from app.timeutil import utcnow

log = logging.getLogger("insights.projector")
BATCH = 500

CLAIM = text(
    "SELECT event_id, received_at, occurred_at, clock_skew, type, schema_version, run_id, "
    "user_id::text AS user_id, "
    "source, body FROM events_raw WHERE projected_at IS NULL AND (retry_after IS NULL OR "
    "retry_after < now()) "
    "ORDER BY occurred_at LIMIT :n FOR UPDATE SKIP LOCKED"
)
MARK = text(
    "UPDATE events_raw SET projected_at = :pa, projection_error = :pe, retry_after = :ra "
    "WHERE event_id = :id AND received_at = :rcv"
)


def _ev(r: Any) -> Ev:
    return Ev(
        r.event_id,
        r.received_at,
        r.occurred_at,
        r.clock_skew,
        r.type,
        r.schema_version,
        r.run_id,
        r.user_id,
        r.source,
        dict(r.body),
    )


def _count_ingest(conn: Connection, ev: Ev) -> None:
    conn.execute(
        text(
            "INSERT INTO ingest_daily (day, type, source, n) VALUES (:d, :t, :s, 1) "
            "ON CONFLICT (day, type, source) DO UPDATE SET n = ingest_daily.n + 1"
        ),
        {"d": ev.received_at.date(), "t": ev.type, "s": ev.source},
    )


def project_batch(s: Settings, limit: int = BATCH) -> tuple[int, int]:
    """Project one batch. Returns (projected, parked)."""
    projected = parked = 0
    with tx("app", s) as conn:
        rows = conn.execute(CLAIM, {"n": limit}).all()
        for r in rows:
            ev = _ev(r)
            handler = HANDLERS.get((ev.type, ev.schema_version))
            sp = conn.begin_nested()
            mark: dict[str, Any]
            try:
                if handler is not None:
                    handler(conn, ev)
                _count_ingest(conn, ev)
                sp.commit()
                mark = {"pa": utcnow(), "pe": None if handler else "no_handler", "ra": None}
                projected += 1
                metrics.PROJECTED.labels(type=ev.type).inc()
            except Parked as p:
                sp.rollback()
                mark = {"pa": None, "pe": p.code, "ra": utcnow() + timedelta(seconds=p.backoff_s)}
                parked += 1
                metrics.PROJECTION_ERRORS.labels(type=ev.type, code=p.code).inc()
            except Exception as exc:
                sp.rollback()
                code = f"handler_error:{type(exc).__name__}"[:60]
                log.error("projection failed", extra={"code": code})
                mark = {"pa": None, "pe": code, "ra": utcnow() + timedelta(minutes=10)}
                parked += 1
                metrics.PROJECTION_ERRORS.labels(type=ev.type, code="handler_error").inc()
            conn.execute(MARK, {**mark, "id": ev.event_id, "rcv": ev.received_at})
    return projected, parked


def project_all(s: Settings, max_batches: int = 1000) -> int:
    total = 0
    for _ in range(max_batches):
        n, p = project_batch(s)
        total += n
        if n + p == 0:
            break
    return total


def sample_lag(s: Settings) -> None:
    """OPS-02 §8.2 gauges, every 15 s."""
    with tx("app", s) as conn:
        row = conn.execute(
            text(
                "SELECT count(*) AS backlog, count(*) FILTER (WHERE projection_error IS NOT NULL) "
                "AS parked, "
                "extract(epoch FROM now() - min(received_at) FILTER (WHERE projection_error IS "
                "NULL)) AS lag_s "
                "FROM events_raw WHERE projected_at IS NULL"
            )
        ).one()
        by_code = conn.execute(
            text(
                "SELECT projection_error, count(*) FROM events_raw WHERE projected_at IS NULL "
                "AND projection_error IS NOT NULL GROUP BY 1"
            )
        ).all()
    metrics.PROJECTION_BACKLOG.set(row.backlog)
    metrics.PROJECTION_LAG.set(float(row.lag_s or 0))
    for code, n in by_code:
        metrics.PROJECTION_PARKED.labels(code=str(code).split(":")[0]).set(n)
