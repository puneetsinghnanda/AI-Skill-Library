"""0007_product_ci_checks: the product repo's own CI result per check name (roadmap D5).

`ci_checks` holds harness verifications (`tsl-ci-verify` and `ci.verified`) and feeds
mv_ci_daily's `verified` count. A product repo's own CI job (for example `build` in ci.yml) is
not a harness verification, so it gets its own table, keyed by check name: two checks on one
head never overwrite each other, and none of them is counted as verified. A started check is
`pending` until it completes, so one passing job doesn't read as "CI passed" while another runs.

Revision ID: 0007_product_ci_checks
Revises: 0006_pr_daily_merged
"""

from __future__ import annotations

from alembic import op

revision = "0007_product_ci_checks"
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
        "CREATE TABLE product_ci_checks ("
        "repo_id uuid NOT NULL REFERENCES system_repos, head_sha text NOT NULL, "
        "check_name text NOT NULL, number int, "
        "result text NOT NULL CHECK (result IN ('pass','fail','pending')), "
        "checked_at timestamptz NOT NULL, "
        "PRIMARY KEY (repo_id, head_sha, check_name))"
    )
    _exec("SELECT insights_apply_grants()")


def downgrade() -> None:
    raise RuntimeError("Migrations are forward-only (SDD-08 §11.1).")
