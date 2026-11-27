"""0007_product_ci_checks: the product repo's own CI result per check name (roadmap D5).

`ci_checks` holds harness verifications (`tsl-ci-verify` and `ci.verified`) and feeds
mv_ci_daily's `verified` count. A product repo's own CI job (for example `build` in ci.yml) is
not a harness verification, so it gets its own table, keyed by check name: two checks on one
head never overwrite each other, and none of them is counted as verified. One row per check
suite (workflow run), so a run triggered by `push` and one by `pull_request` both count. A started
check is `pending` until it completes; a skipped or cancelled one is `none` (no result), which
also stops a late `created` from making it pending again.

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
        "check_name text NOT NULL, suite_id bigint NOT NULL DEFAULT 0, number int, "
        "result text NOT NULL CHECK (result IN ('pass','fail','pending','none')), "
        "checked_at timestamptz NOT NULL, "
        "PRIMARY KEY (repo_id, head_sha, check_name, suite_id))"
    )
    # When the PR's head was last moved (pull_request.updated_at): a late `synchronize` never
    # moves it back to an older commit.
    _exec("ALTER TABLE pull_requests ADD COLUMN head_updated_at timestamptz")
    _exec("SELECT insights_apply_grants()")


def downgrade() -> None:
    raise RuntimeError("Migrations are forward-only (SDD-08 §11.1).")
