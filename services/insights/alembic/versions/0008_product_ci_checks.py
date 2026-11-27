"""0008_product_ci_checks: the product repo's own CI runs and a PR's CI status (roadmap D5).

`ci_checks` holds harness verifications (`tsl-ci-verify` and `ci.verified`) and feeds
mv_ci_daily's `verified` count. A product repo's own CI job (for example `build` in ci.yml) is
not a harness verification, so its runs get their own table, one row per GitHub check run
(`check_run.id`). A check run only moves forward (created, then completed once; a re-run is a
new check run), so the order webhooks arrive in does not matter: `created` never overwrites a
row and `completed` always finishes it. The PR's CI status is worked out when it is read, in
insights_pr_ci_result().

pull_requests.pr_updated_at keeps the newest `pull_request.updated_at` applied, so a late
delivery never moves the head back or changes the state.

Revision ID: 0008_product_ci_checks
Revises: 0007_step_metrics
"""

from __future__ import annotations

from alembic import op

revision = "0008_product_ci_checks"
down_revision = "0007_step_metrics"
branch_labels = None
depends_on = None

RESULT_FN = """
CREATE FUNCTION insights_pr_ci_result(p_repo uuid, p_head text) RETURNS text
LANGUAGE sql STABLE SET search_path = public, pg_temp AS $$
  -- A PR's CI status at its head: 'fail', 'pass', or NULL ("CI pending").
  -- Per product check name, the newest run (highest check_run_id) decides: a newer run still
  -- running (and started within 6 hours, the longest a GitHub Actions job can run) makes the
  -- name pending; else the newest run that finished with a result gives pass or fail. Runs
  -- that finished without a result (skipped, neutral, cancelled, stale, action_required) are
  -- ignored. Any failure, from the harness or any name, fails the PR; else any pending name
  -- keeps it pending; else a harness or product pass passes it.
  WITH runs AS (
    SELECT check_name, check_run_id, status, conclusion, started_at
    FROM product_ci_runs WHERE repo_id = p_repo AND head_sha = p_head
  ), finished AS (
    SELECT check_name, max(check_run_id) AS last_id FROM runs
    WHERE status = 'completed' GROUP BY check_name
  ), pending AS (
    SELECT DISTINCT r.check_name FROM runs r LEFT JOIN finished f USING (check_name)
    WHERE r.status = 'pending' AND r.started_at > now() - interval '6 hours'
      AND (f.last_id IS NULL OR r.check_run_id > f.last_id)
  ), decided AS (
    SELECT DISTINCT ON (check_name) check_name, conclusion FROM runs
    WHERE status = 'completed'
      AND conclusion NOT IN ('skipped', 'neutral', 'cancelled', 'stale', 'action_required')
      AND check_name NOT IN (SELECT check_name FROM pending)
    ORDER BY check_name, check_run_id DESC
  ), harness AS (
    SELECT c.result FROM ci_checks c WHERE c.repo_id = p_repo AND c.head_sha = p_head
    ORDER BY (c.source = 'event') DESC, c.checked_at DESC LIMIT 1
  )
  SELECT CASE
    WHEN (SELECT result FROM harness) = 'fail'
      OR EXISTS (SELECT 1 FROM decided WHERE conclusion <> 'success') THEN 'fail'
    WHEN EXISTS (SELECT 1 FROM pending) THEN NULL
    WHEN (SELECT result FROM harness) = 'pass' OR EXISTS (SELECT 1 FROM decided) THEN 'pass'
  END
$$;
GRANT EXECUTE ON FUNCTION insights_pr_ci_result(uuid, text) TO insights_app, insights_read;
"""


def _exec(sql: str) -> None:
    """Run raw SQL on the migration connection (no placeholder parsing; PL/pgSQL uses %)."""
    cur = op.get_bind().connection.dbapi_connection.cursor()  # type: ignore[union-attr]
    try:
        cur.execute(sql)
    finally:
        cur.close()


def upgrade() -> None:
    _exec(
        "CREATE TABLE product_ci_runs ("
        "repo_id uuid NOT NULL REFERENCES system_repos, check_run_id bigint NOT NULL, "
        "head_sha text NOT NULL, check_name text NOT NULL, "
        "status text NOT NULL CHECK (status IN ('pending', 'completed')), "
        "conclusion text, started_at timestamptz, completed_at timestamptz, "
        "seen_at timestamptz NOT NULL DEFAULT now(), "
        "PRIMARY KEY (repo_id, check_run_id))"
    )
    _exec("CREATE INDEX ON product_ci_runs (repo_id, head_sha)")
    _exec("CREATE INDEX ON product_ci_runs (seen_at)")  # retention
    _exec("ALTER TABLE pull_requests ADD COLUMN pr_updated_at timestamptz")
    _exec(RESULT_FN)
    _exec("SELECT insights_apply_grants()")


def downgrade() -> None:
    raise RuntimeError("Migrations are forward-only (SDD-08 §11.1).")
