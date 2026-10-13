"""Device outbox gauges and database size (OPS-02 §8.3, §5.2)."""

from __future__ import annotations

from sqlalchemy import text

from app.config import Settings
from app.db import tx
from app.obs import metrics

TABLES = ["events_raw", "otel_events", "steps", "runs", "event_ids", "audit_log"]


def run(s: Settings) -> dict[str, float]:
    with tx("app", s) as conn:
        r = conn.execute(
            text(
                "SELECT count(*) FILTER (WHERE outbox_depth > 0) AS nonempty, "
                "coalesce(sum(outbox_depth) FILTER (WHERE outbox_depth > 0), 0) AS events, "
                "count(*) FILTER (WHERE outbox_oldest_at < now() - interval '24 hours') AS gt_24h, "
                "count(*) FILTER (WHERE outbox_oldest_at < now() - interval '72 hours') AS gt_72h, "
                "count(*) FILTER (WHERE outbox_oldest_at < now() - interval '7 days') AS gt_7d, "
                "coalesce(extract(epoch FROM now() - min(outbox_oldest_at)), 0) AS oldest_age_s "
                "FROM devices WHERE last_seen_at > now() - interval '14 days'"
            )
        ).one()
        seen1 = conn.execute(
            text("SELECT count(*) FROM devices WHERE last_seen_at > now() - interval '1 day'")
        ).scalar_one()
        seen14 = conn.execute(
            text("SELECT count(*) FROM devices WHERE last_seen_at > now() - interval '14 days'")
        ).scalar_one()
        size = conn.execute(text("SELECT pg_database_size(current_database())")).scalar_one()
        tsizes = conn.execute(
            text(
                "SELECT relname, pg_total_relation_size(c.oid) FROM pg_class c JOIN "
                "pg_namespace n ON n.oid = c.relnamespace "
                "WHERE n.nspname = 'public' AND relname = ANY(:t)"
            ),
            {"t": TABLES},
        ).all()
        tokens = conn.execute(
            text(
                "SELECT kind, extract(epoch FROM now() - max(last_used_at)) FROM ingest_tokens "
                "WHERE revoked_at IS NULL "
                "GROUP BY 1"
            )
        ).all()
    metrics.DEVICES_OUTBOX_NONEMPTY.set(r.nonempty)
    metrics.DEVICES_OUTBOX_EVENTS.set(r.events)
    for age in ("gt_24h", "gt_72h", "gt_7d"):
        metrics.DEVICES_OUTBOX_STALE.labels(age=age).set(getattr(r, age))
    metrics.DEVICES_OUTBOX_OLDEST.set(float(r.oldest_age_s))
    metrics.DEVICES_SEEN.labels(window="1d").set(seen1)
    metrics.DEVICES_SEEN.labels(window="14d").set(seen14)
    metrics.DB_SIZE.set(size)
    for name, b in tsizes:
        metrics.DB_TABLE_BYTES.labels(table=name).set(b)
    for kind, age in tokens:
        if age is not None:
            metrics.INGEST_TOKEN_AGE.labels(kind=kind).set(float(age))
    return {"nonempty": float(r.nonempty), "gt_72h": float(r.gt_72h), "gt_7d": float(r.gt_7d)}
