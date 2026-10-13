"""0004_improvement: SDD-11 §4.5 tables and the skill_window_stats view (SDD-08 §10.5).

Revision ID: 0004_improvement
Revises: 0003_seed_reference
"""

from __future__ import annotations

from alembic import op

revision = "0004_improvement"
down_revision = "0003_seed_reference"
branch_labels = None
depends_on = None

DDL = """
-- Inputs for IS-1..IS-10 per skill version over the rolling 28-day window (SDD-11 §3.1).
CREATE MATERIALIZED VIEW skill_window_stats AS
WITH w AS (
  SELECT s.*, r.system_id FROM steps s JOIN runs r ON r.id = s.run_id
  WHERE s.decided_at >= now() - interval '28 days' AND s.skill_id IS NOT NULL
),
ov AS (
  SELECT x.skill_id, x.skill_version, count(*) AS overrides
  FROM approvals a
  JOIN LATERAL (SELECT * FROM steps y WHERE y.run_id = a.run_id AND y.step_id = a.step_id
                ORDER BY y.attempt DESC LIMIT 1) x ON true
  WHERE a.recorded_at >= now() - interval '28 days'
    AND ((x.outcome = 'ESCALATE' AND a.decision = 'approve')
      OR (x.outcome IN ('PASS','PASS-WITH-FINDINGS') AND x.band = 'High' AND a.decision IN ('reject','changes')))
  GROUP BY 1, 2
)
SELECT w.skill_id, w.skill_version,
  current_date AS window_end, 28 AS window_days,
  count(DISTINCT (w.run_id, w.step_id))                                              AS steps,
  count(*) FILTER (WHERE w.attempt = 1)                                              AS first_attempts,
  count(*) FILTER (WHERE w.attempt = 1 AND w.outcome IN ('PASS','PASS-WITH-FINDINGS')) AS first_try_pass,
  count(*) FILTER (WHERE w.attempt_cause IN ('retry_checks','retry_review','retry_verifier')) AS retries,
  count(DISTINCT (w.run_id, w.step_id)) FILTER (WHERE w.outcome = 'ESCALATE')        AS escalated_steps,
  count(DISTINCT (w.run_id, w.step_id)) FILTER (WHERE w.outcome = 'NEEDS-INPUT')     AS input_steps,
  avg((w.signals->>'S1')::numeric) FILTER (WHERE w.outcome IN ('PASS','PASS-WITH-FINDINGS')
                                           AND jsonb_typeof(w.signals->'S1') = 'number') AS s1_mean,
  count(*) FILTER (WHERE w.outcome IN ('PASS','PASS-WITH-FINDINGS'))                  AS pass_path_attempts,
  count(*) FILTER (WHERE w.outcome NOT IN ('PASS','PASS-WITH-FINDINGS'))              AS failed_attempts,
  coalesce(max(ov.overrides), 0)                                                      AS overrides
FROM w LEFT JOIN ov ON ov.skill_id = w.skill_id AND ov.skill_version = w.skill_version
GROUP BY w.skill_id, w.skill_version;
CREATE UNIQUE INDEX ON skill_window_stats (skill_id, skill_version);

CREATE TABLE skill_flags (
  id text PRIMARY KEY CHECK (id ~ '^flg_[0-9A-HJKMNP-TV-Z]{26}$'),
  skill_id text NOT NULL, skill_version text NOT NULL,
  signal text NOT NULL CHECK (signal ~ '^IS-[0-9]+$'),
  value numeric NOT NULL, threshold numeric NOT NULL, sample int NOT NULL,
  status text NOT NULL CHECK (status IN ('OPEN','IN_PROGRESS','PROPOSED','RELEASED','VERIFIED','REOPENED','DISMISSED')),
  dismissed_reason text CHECK (char_length(dismissed_reason) <= 200),
  opened_at timestamptz NOT NULL, updated_at timestamptz NOT NULL,
  FOREIGN KEY (skill_id, skill_version) REFERENCES skill_versions);
CREATE UNIQUE INDEX skill_flags_live ON skill_flags (skill_id, skill_version, signal)
  WHERE status NOT IN ('VERIFIED','DISMISSED');

CREATE TABLE improvement_reports (
  skill_id text, skill_version text, window_end date, body jsonb NOT NULL,
  PRIMARY KEY (skill_id, skill_version, window_end));

CREATE TABLE improvements (
  id text PRIMARY KEY CHECK (id ~ '^imp_[0-9A-HJKMNP-TV-Z]{26}$'),
  skill_id text NOT NULL, from_version text NOT NULL, to_version text,
  flag_ids text[] NOT NULL, owner_id uuid REFERENCES users,
  before_pass_rate numeric, after_pass_rate numeric, cases_added int,
  pr_repo text, pr_number int, state text NOT NULL CHECK (state IN ('planned','proposed','merged','released','abandoned')),
  created_at timestamptz NOT NULL, updated_at timestamptz NOT NULL);
"""


def _exec(sql: str) -> None:
    """Run raw SQL on the migration connection (no placeholder parsing; PL/pgSQL uses %)."""
    cur = op.get_bind().connection.dbapi_connection.cursor()  # type: ignore[union-attr]
    try:
        cur.execute(sql)
    finally:
        cur.close()


def upgrade() -> None:
    _exec(DDL)
    _exec("SELECT insights_apply_grants()")


def downgrade() -> None:
    raise RuntimeError("Migrations are forward-only (SDD-08 §11.1).")
