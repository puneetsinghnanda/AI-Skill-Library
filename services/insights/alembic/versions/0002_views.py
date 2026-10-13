"""0002_views: materialized views and plain views behind every portal number (SDD-08 §10.3).

Revision ID: 0002_views
Revises: 0001_initial
"""

from __future__ import annotations

from alembic import op

revision = "0002_views"
down_revision = "0001_initial"
branch_labels = None
depends_on = None

VIEWS = """
CREATE MATERIALIZED VIEW mv_skill_daily AS
SELECT s.decided_at::date AS day, r.project_id, r.system_id, coalesce(r.pod_id,'') AS pod_id, s.skill_id, s.skill_version,
  count(*)                                                     AS decisions,
  count(*) FILTER (WHERE s.attempt = 1)                        AS first_attempts,
  count(*) FILTER (WHERE s.attempt = 1 AND s.outcome IN ('PASS','PASS-WITH-FINDINGS')) AS first_try_pass,
  count(*) FILTER (WHERE s.outcome = 'PASS')                   AS o_pass,
  count(*) FILTER (WHERE s.outcome = 'PASS-WITH-FINDINGS')     AS o_findings,
  count(*) FILTER (WHERE s.outcome = 'RETRY')                  AS o_retry,
  count(*) FILTER (WHERE s.outcome = 'NEEDS-INPUT')            AS o_input,
  count(*) FILTER (WHERE s.outcome = 'ESCALATE')               AS o_escalate,
  count(*) FILTER (WHERE s.outcome = 'ABORT')                  AS o_abort,
  count(*) FILTER (WHERE s.band = 'High')                      AS b_high,
  count(*) FILTER (WHERE s.band = 'Medium')                    AS b_medium,
  count(*) FILTER (WHERE s.band = 'Low')                       AS b_low,
  count(DISTINCT (s.run_id, s.step_id))                        AS step_instances
FROM steps s JOIN runs r ON r.id = s.run_id
WHERE s.decided_at IS NOT NULL AND s.skill_id IS NOT NULL
GROUP BY 1,2,3,4,5,6;
CREATE UNIQUE INDEX ON mv_skill_daily (day, project_id, system_id, pod_id, skill_id, skill_version);

CREATE MATERIALIZED VIEW mv_cause_daily AS
SELECT s.decided_at::date AS day, r.project_id, r.system_id, s.skill_id, s.skill_version, c.code, count(*) AS n
FROM steps s JOIN runs r ON r.id = s.run_id CROSS JOIN LATERAL unnest(s.reasons) AS c(code)
WHERE s.attempt = 1 AND s.outcome NOT IN ('PASS','PASS-WITH-FINDINGS')
GROUP BY 1,2,3,4,5,6;
CREATE UNIQUE INDEX ON mv_cause_daily (day, project_id, system_id, skill_id, skill_version, code);

CREATE MATERIALIZED VIEW mv_override_daily AS
SELECT a.recorded_at::date AS day, r.project_id, r.system_id, s.skill_id, s.skill_version, count(*) AS overrides
FROM approvals a JOIN runs r ON r.id = a.run_id
JOIN LATERAL (SELECT * FROM steps x WHERE x.run_id = a.run_id AND x.step_id = a.step_id
              ORDER BY x.attempt DESC LIMIT 1) s ON true
WHERE a.recorded_at IS NOT NULL
  AND ((s.outcome = 'ESCALATE' AND a.decision = 'approve')
    OR (s.outcome IN ('PASS','PASS-WITH-FINDINGS') AND a.decision IN ('reject','changes')))
GROUP BY 1,2,3,4,5;
CREATE UNIQUE INDEX ON mv_override_daily (day, project_id, system_id, skill_id, skill_version);

CREATE MATERIALIZED VIEW mv_run_daily AS
SELECT r.started_at::date AS day, r.project_id, r.system_id, r.workflow_id,
  coalesce(r.pod_id,'') AS pod_id, count(*) AS runs_started,
  count(*) FILTER (WHERE r.end_reason IN ('pr_opened','completed')) AS runs_completed,
  count(*) FILTER (WHERE r.end_reason = 'aborted')   AS runs_aborted
FROM runs r WHERE r.started_at IS NOT NULL
GROUP BY 1,2,3,4,5;
CREATE UNIQUE INDEX ON mv_run_daily (day, project_id, system_id, workflow_id, pod_id);

CREATE MATERIALIZED VIEW mv_pr_daily AS
WITH t AS (
  SELECT p.opened_at::date AS day, p.run_id, 'opened' AS kind, p.changes_requested FROM pull_requests p WHERE p.opened_at IS NOT NULL
  UNION ALL SELECT p.merged_at::date, p.run_id, 'merged', p.changes_requested FROM pull_requests p WHERE p.merged_at IS NOT NULL
  UNION ALL SELECT p.closed_at::date, p.run_id, 'closed', p.changes_requested FROM pull_requests p WHERE p.closed_at IS NOT NULL)
SELECT t.day, r.project_id, r.system_id, coalesce(r.pod_id,'') AS pod_id,
  count(*) FILTER (WHERE kind = 'opened') AS opened,
  count(*) FILTER (WHERE kind = 'merged') AS merged,
  count(*) FILTER (WHERE kind = 'closed') AS closed_unmerged,
  count(*) FILTER (WHERE kind = 'opened' AND changes_requested) AS opened_with_changes_requested
FROM t JOIN runs r ON r.id = t.run_id
GROUP BY 1,2,3,4;
CREATE UNIQUE INDEX ON mv_pr_daily (day, project_id, system_id, pod_id);

CREATE MATERIALIZED VIEW mv_ci_daily AS
SELECT c.checked_at::date AS day, sr.system_id,
  count(*) FILTER (WHERE c.result = 'pass')            AS verified,
  count(*) FILTER (WHERE 'E-CI-01' = ANY (c.codes))   AS e_ci_01,
  count(*) FILTER (WHERE 'E-CI-02' = ANY (c.codes))   AS e_ci_02,
  count(*) FILTER (WHERE 'E-CI-03' = ANY (c.codes))   AS e_ci_03
FROM ci_checks c JOIN system_repos sr ON sr.id = c.repo_id
WHERE c.source = 'event' OR NOT EXISTS (SELECT 1 FROM ci_checks e WHERE e.repo_id = c.repo_id
                                        AND e.head_sha = c.head_sha AND e.source = 'event')
GROUP BY 1,2;
CREATE UNIQUE INDEX ON mv_ci_daily (day, system_id);

CREATE MATERIALIZED VIEW mv_pod_engagement AS
SELECT r.pod_id, r.system_id, r.project_id, min(r.started_at) AS first_run_at, max(r.updated_at) AS last_activity_at,
       count(*) AS runs
FROM runs r WHERE r.pod_id IS NOT NULL GROUP BY 1,2,3;
CREATE UNIQUE INDEX ON mv_pod_engagement (pod_id, system_id);

CREATE VIEW v_capability_map AS
SELECT k.agent_role, k.phase, k.id AS skill_id, k.title, v.status
FROM skills k JOIN skill_versions v ON v.skill_id = k.id AND v.version = k.current_version
WHERE v.status IN ('production','pilot');

CREATE VIEW v_run_waiting AS
SELECT r.id AS run_id, r.system_id, r.user_id, 'question' AS kind, q.question_id AS item, q.created_at AS since, q.ask_role AS needs_role
FROM runs r JOIN questions q ON q.run_id = r.id
WHERE r.status = 'PAUSED_INPUT' AND q.answered_at IS NULL AND q.blocking
UNION ALL
SELECT r.id, r.system_id, r.user_id, 'approval', a.gate, a.requested_at, 'tech_lead'
FROM runs r JOIN approvals a ON a.run_id = r.id
WHERE r.status = 'PAUSED_APPROVAL' AND a.recorded_at IS NULL;
"""


def _exec(sql: str) -> None:
    """Run raw SQL on the migration connection (no placeholder parsing; PL/pgSQL uses %)."""
    cur = op.get_bind().connection.dbapi_connection.cursor()  # type: ignore[union-attr]
    try:
        cur.execute(sql)
    finally:
        cur.close()


def upgrade() -> None:
    _exec(VIEWS)
    _exec("SELECT insights_apply_grants()")


def downgrade() -> None:
    raise RuntimeError("Migrations are forward-only (SDD-08 §11.1).")
