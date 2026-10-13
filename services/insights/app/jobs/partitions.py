"""Monthly partitions: keep the current and next 2 months of events_raw and otel_events (SDD-08 "
"§11.1)."""

from __future__ import annotations

from datetime import date

from sqlalchemy import text

from app.config import Settings
from app.db import Role, tx
from app.obs import metrics
from app.timeutil import utcnow

TABLES = ("events_raw", "otel_events")


def month_add(d: date, n: int) -> date:
    m = d.month - 1 + n
    return date(d.year + m // 12, m % 12 + 1, 1)


def run(s: Settings, ahead: int = 2, role: Role = "app") -> int:
    created = 0
    first = utcnow().date().replace(day=1)
    with tx(role, s) as conn:
        for t in TABLES:
            for i in range(0, ahead + 1):
                if conn.execute(
                    text("SELECT insights_ensure_partition(:t, :m)"),
                    {"t": t, "m": month_add(first, i)},
                ).scalar():
                    created += 1
            metrics.PARTITIONS_AHEAD.labels(table=t).set(
                conn.execute(text("SELECT insights_partitions_ahead(:t)"), {"t": t}).scalar_one()
            )
    return created
