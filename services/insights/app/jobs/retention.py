"""Retention (SDD-08 §8.2): rollup first, then delete. Periods are configuration (OQ-08, RD-4)."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from sqlalchemy import Connection, text

from app.config import Settings
from app.db import tx
from app.jobs.partitions import month_add
from app.timeutil import utcnow

NIL = "00000000-0000-0000-0000-000000000000"

ROLLUP = """
WITH old AS (SELECT id FROM runs WHERE coalesce(updated_at, started_at) < :cut)
INSERT INTO agg_monthly (month, project_id, system_id, skill_id, skill_version, workflow_id,
  pod_id, metric, value)
SELECT month, coalesce(project_id, CAST(:nil AS uuid)), coalesce(system_id, CAST(:nil AS uuid)),
  coalesce(skill_id, ''),
       coalesce(skill_version, ''), coalesce(workflow_id, ''), coalesce(pod_id, ''), metric, sum(v)
FROM (
  SELECT date_trunc('month', p.merged_at)::date AS month, r.project_id, r.system_id, NULL::text
    AS skill_id,
         NULL::text AS skill_version, r.workflow_id, r.pod_id, 'prs_merged' AS metric, 1 AS v
  FROM pull_requests p JOIN runs r ON r.id = p.run_id WHERE p.run_id IN (SELECT id FROM old) AND
    p.merged_at IS NOT NULL
  UNION ALL
  SELECT date_trunc('month', r.started_at)::date, r.project_id, r.system_id, NULL, NULL,
    r.workflow_id, r.pod_id,
         'runs_started', 1 FROM runs r WHERE r.id IN (SELECT id FROM old) AND r.started_at IS NOT
           NULL
  UNION ALL
  SELECT date_trunc('month', s.decided_at)::date, r.project_id, r.system_id, s.skill_id,
    s.skill_version, r.workflow_id,
         r.pod_id, 'first_attempts', 1 FROM steps s JOIN runs r ON r.id = s.run_id
  WHERE s.run_id IN (SELECT id FROM old) AND s.attempt = 1 AND s.decided_at IS NOT NULL
  UNION ALL
  SELECT date_trunc('month', s.decided_at)::date, r.project_id, r.system_id, s.skill_id,
    s.skill_version, r.workflow_id,
         r.pod_id, 'first_try_pass', 1 FROM steps s JOIN runs r ON r.id = s.run_id
  WHERE s.run_id IN (SELECT id FROM old) AND s.attempt = 1 AND s.outcome IN
    ('PASS','PASS-WITH-FINDINGS')
) x GROUP BY 1, 2, 3, 4, 5, 6, 7, 8
ON CONFLICT (month, project_id, system_id, skill_id, skill_version, workflow_id, pod_id, metric)
DO UPDATE SET value = agg_monthly.value + EXCLUDED.value
"""

USER_ROLLUP = """
INSERT INTO agg_user_month (month, user_id)
SELECT DISTINCT date_trunc('month', r.started_at)::date, r.user_id FROM runs r
WHERE coalesce(r.updated_at, r.started_at) < :cut AND r.user_id IS NOT NULL
  AND r.started_at IS NOT NULL
ON CONFLICT DO NOTHING
"""

DELETE_ORDER = [
    "check_records",
    "steps",
    "questions",
    "approvals",
    "run_sessions",
    "run_usage",
    "pull_requests",
]


def rollup_and_delete_runs(conn: Connection, months: int) -> int:
    cut = utcnow() - timedelta(days=round(months * 30.44))
    conn.execute(text(ROLLUP), {"cut": cut, "nil": NIL})
    conn.execute(text(USER_ROLLUP), {"cut": cut})
    old = "SELECT id FROM runs WHERE coalesce(updated_at, started_at) < :cut"
    for t in DELETE_ORDER:
        conn.execute(text(f"DELETE FROM {t} WHERE run_id IN ({old})"), {"cut": cut})
    return int(conn.execute(text(f"DELETE FROM runs WHERE id IN ({old})"), {"cut": cut}).rowcount)


def run(s: Settings) -> dict[str, Any]:
    out: dict[str, Any] = {}
    today = utcnow().date()
    with tx("app", s) as conn:
        ev_cut = month_add(today.replace(day=1), -s.retention_events_months)
        out["events_raw_partitions"] = conn.execute(
            text("SELECT insights_drop_partitions_before('events_raw', :d)"), {"d": ev_cut}
        ).scalar_one()
        out["event_ids"] = conn.execute(
            text("DELETE FROM event_ids WHERE received_at < :d"), {"d": ev_cut}
        ).rowcount
        ot_cut = today - timedelta(days=s.retention_otel_days)
        out["otel_partitions"] = conn.execute(
            text("SELECT insights_drop_partitions_before('otel_events', :d)"), {"d": ot_cut}
        ).scalar_one()
        out["webhook_deliveries"] = conn.execute(
            text(
                "DELETE FROM webhook_deliveries WHERE received_at < now() - make_interval(days "
                "=> "
                ":d)"
            ),
            {"d": s.retention_webhook_days},
        ).rowcount
        out["runs"] = rollup_and_delete_runs(conn, s.retention_runs_months)
        out["audit_log"] = conn.execute(
            text("SELECT insights_purge_audit_log(now() - make_interval(months => :m))"),
            {"m": max(24, s.audit_retention_months)},
        ).scalar_one()
    return out
