"""0008_product_ci_checks: the product repo's own CI runs and a PR's CI status (roadmap D5).

`ci_checks` holds harness verifications (`tsl-ci-verify` and `ci.verified`) and feeds
mv_ci_daily's `verified` count. A product repo's own CI job (for example `build` in ci.yml) is
not a harness verification, so its runs get their own table, one row per GitHub check run
(`check_run.id`). A check run only moves forward (created, then completed once; a re-run is a
new check run), so the order webhooks arrive in does not matter: `created` never overwrites a
row and `completed` always finishes it. The PR's CI status is worked out when it is read, in
insights_pr_ci_result().

pull_requests.pr_updated_at keeps the newest `pull_request.updated_at` applied and
pr_last_action the action that applied it (pr_tie_pushes: same-second pushes waiting for their
predecessor), so a late delivery never moves the head back or
changes the state, also when two events share a second (webhooks_github._pr_applies).

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
CREATE FUNCTION insights_pr_ci_result(p_repo uuid, p_head text, p_pending_hours int DEFAULT 30)
RETURNS text LANGUAGE sql STABLE SET search_path = public, pg_temp AS $$
  -- A PR's CI status at its head: 'fail', 'pass', or NULL ("CI pending").
  -- A check is one job of one workflow run: (app, check suite, name). Its newest run (highest
  -- check_run_id) decides, so re-running a job replaces its earlier result. A newer run still
  -- running, and started (queued) within p_pending_hours, keeps the check pending; else the
  -- newest run that finished with a result gives pass or fail. Runs that finished without a
  -- result (no conclusion, skipped, neutral, cancelled, stale, action_required) are ignored, so a
  -- cancelled re-run keeps the earlier failure. Any failure, from the harness or any check,
  -- fails the PR (a failed workflow run is cleared by re-running it or by a new push); else any
  -- pending check keeps it pending; else a harness or product pass passes it.
  WITH runs AS (
    SELECT app_id, suite_id, check_name, check_run_id, status, conclusion, started_at
    FROM product_ci_runs WHERE repo_id = p_repo AND head_sha = p_head
  ), finished AS (
    SELECT app_id, suite_id, check_name, max(check_run_id) AS last_id FROM runs
    WHERE status = 'completed' GROUP BY app_id, suite_id, check_name
  ), pending AS (
    SELECT DISTINCT r.app_id, r.suite_id, r.check_name
    FROM runs r LEFT JOIN finished f USING (app_id, suite_id, check_name)
    WHERE r.status = 'pending'
      AND r.started_at > now() - make_interval(hours => p_pending_hours)
      AND (f.last_id IS NULL OR r.check_run_id > f.last_id)
  ), decided AS (
    SELECT DISTINCT ON (r.app_id, r.suite_id, r.check_name) r.conclusion
    FROM runs r
    WHERE r.status = 'completed' AND r.conclusion IS NOT NULL
      -- the same list as NO_RESULT in app/api/v1/webhooks_github.py
      AND r.conclusion NOT IN ('skipped', 'neutral', 'cancelled', 'stale', 'action_required')
      AND NOT EXISTS (SELECT 1 FROM pending p WHERE p.app_id = r.app_id
                      AND p.suite_id = r.suite_id AND p.check_name = r.check_name)
    ORDER BY r.app_id, r.suite_id, r.check_name, r.check_run_id DESC
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
GRANT EXECUTE ON FUNCTION insights_pr_ci_result(uuid, text, int) TO insights_app, insights_read;
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
        "suite_id bigint NOT NULL DEFAULT 0, app_id bigint NOT NULL DEFAULT 0, "
        "status text NOT NULL CHECK (status IN ('pending', 'completed')), "
        "conclusion text, started_at timestamptz, completed_at timestamptz, "
        "seen_at timestamptz NOT NULL DEFAULT now(), "
        "PRIMARY KEY (repo_id, check_run_id))"
    )
    _exec("CREATE INDEX ON product_ci_runs (repo_id, head_sha)")
    _exec("CREATE INDEX ON product_ci_runs (seen_at)")  # retention
    _exec("ALTER TABLE pull_requests ADD COLUMN pr_updated_at timestamptz")
    _exec("ALTER TABLE pull_requests ADD COLUMN pr_last_action text")
    # Same-second pushes that arrived before their predecessor: {before_sha: after_sha}.
    _exec("ALTER TABLE pull_requests ADD COLUMN pr_tie_pushes jsonb NOT NULL DEFAULT '{}'")
    _exec(RESULT_FN)
    _exec("SELECT insights_apply_grants()")


def downgrade() -> None:
    raise RuntimeError("Migrations are forward-only (SDD-08 §11.1).")
