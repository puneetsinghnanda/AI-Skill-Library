"""0006_pr_daily_merged: a PR that ends merged is not counted as closed unmerged.

A PR closed without merge and later reopened and merged keeps both closed_at and merged_at
(the pr.closed projection and the webhook never clear a timestamp). mv_pr_daily counted every
row with closed_at as closed_unmerged, so that PR counted as merged and as closed unmerged and
lowered pr_merge_rate. The closed branch now requires merged_at IS NULL.

Revision ID: 0006_pr_daily_merged
Revises: 0005_denylist
"""

from __future__ import annotations

from alembic import op

revision = "0006_pr_daily_merged"
down_revision = "0005_denylist"
branch_labels = None
depends_on = None

VIEW = """
DROP MATERIALIZED VIEW mv_pr_daily;
CREATE MATERIALIZED VIEW mv_pr_daily AS
WITH t AS (
  SELECT p.opened_at::date AS day, p.run_id, 'opened' AS kind, p.changes_requested FROM pull_requests p WHERE p.opened_at IS NOT NULL
  UNION ALL SELECT p.merged_at::date, p.run_id, 'merged', p.changes_requested FROM pull_requests p WHERE p.merged_at IS NOT NULL
  UNION ALL SELECT p.closed_at::date, p.run_id, 'closed', p.changes_requested FROM pull_requests p
    WHERE p.closed_at IS NOT NULL AND p.merged_at IS NULL)
SELECT t.day, r.project_id, r.system_id, coalesce(r.pod_id,'') AS pod_id,
  count(*) FILTER (WHERE kind = 'opened') AS opened,
  count(*) FILTER (WHERE kind = 'merged') AS merged,
  count(*) FILTER (WHERE kind = 'closed') AS closed_unmerged,
  count(*) FILTER (WHERE kind = 'opened' AND changes_requested) AS opened_with_changes_requested
FROM t JOIN runs r ON r.id = t.run_id
GROUP BY 1,2,3,4;
CREATE UNIQUE INDEX ON mv_pr_daily (day, project_id, system_id, pod_id);
"""


def _exec(sql: str) -> None:
    """Run raw SQL on the migration connection (no placeholder parsing; PL/pgSQL uses %)."""
    cur = op.get_bind().connection.dbapi_connection.cursor()  # type: ignore[union-attr]
    try:
        cur.execute(sql)
    finally:
        cur.close()


def upgrade() -> None:
    _exec(VIEW)
    _exec("SELECT insights_apply_grants()")


def downgrade() -> None:
    raise RuntimeError("Migrations are forward-only (SDD-08 §11.1).")
