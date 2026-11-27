"""0007_step_metrics: run metrics per step attempt from `step.decided` (roadmap D1).

tsl 0.1.8 sends `metrics` on `step.decided` (schemas/events/step.decided.v1.json): the model
tokens read from the Claude Code transcript (counts only), the engineer's wait on IDE questions
and the AI time, which `duration_ms` now carries. `steps.tokens_in` / `tokens_out` already exist
(uncached input and output); this adds the cache, call, wait and model columns. All NULL for an
attempt decided by an older tsl or without a transcript.

Revision ID: 0007_step_metrics
Revises: 0006_pr_daily_merged
"""

from __future__ import annotations

from alembic import op

revision = "0007_step_metrics"
down_revision = "0006_pr_daily_merged"
branch_labels = None
depends_on = None


def _exec(sql: str) -> None:
    """Run raw SQL on the migration connection (no placeholder parsing; PL/pgSQL uses %)."""
    cur = op.get_bind().connection.dbapi_connection.cursor()  # type: ignore[union-attr]
    try:
        cur.execute(sql)
    finally:
        cur.close()


def upgrade() -> None:
    _exec(
        "ALTER TABLE steps "
        "ADD COLUMN cache_read bigint, ADD COLUMN cache_write bigint, "
        "ADD COLUMN calls int, ADD COLUMN subagent_calls int, "
        "ADD COLUMN wait_s int, ADD COLUMN models text[], "
        "ADD COLUMN metrics_source text CHECK (metrics_source IN ('transcript','none'))"
    )
    _exec("SELECT insights_apply_grants()")


def downgrade() -> None:
    raise RuntimeError("Migrations are forward-only (SDD-08 §11.1).")
