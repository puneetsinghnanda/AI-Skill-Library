"""0005_denylist: hashed client-name denylist (SEC-01 §7.4, SDD-08 §10.5).

Revision ID: 0005_denylist
Revises: 0004_improvement
"""

from __future__ import annotations

from alembic import op

revision = "0005_denylist"
down_revision = "0004_improvement"
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
        "CREATE TABLE client_denylist (version int PRIMARY KEY, salt bytea NOT NULL, "
        "hashes text[] NOT NULL, created_at timestamptz NOT NULL)"
    )
    _exec("SELECT insights_apply_grants()")


def downgrade() -> None:
    raise RuntimeError("Migrations are forward-only (SDD-08 §11.1).")
