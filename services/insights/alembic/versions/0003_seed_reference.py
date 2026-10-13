"""0003_seed_reference: failure-cause labels (SDD-08 §6.3) and the system user svc-entra-sync.

Revision ID: 0003_seed_reference
Revises: 0002_views
"""

from __future__ import annotations

from alembic import op

revision = "0003_seed_reference"
down_revision = "0002_views"
branch_labels = None
depends_on = None

# Fixed id of the seeded system user `svc-entra-sync` (SDD-08 §10.5, SDD-07 §3.4). Its pseudonym
# must match the users.pseudonym CHECK, so it is eng-00000000; it can never sign in (nil tenant,
# inactive) and its agent_role names it.
SVC_ENTRA_SYNC_ID = "00000000-0000-0000-0000-000000000001"

CAUSES = [
    ("H1", "Schema invalid"),
    ("H2", "Required section missing"),
    ("H3", "Build or test failed"),
    ("H4", "Forbidden content"),
    ("H5", "Trace link or scope"),
    ("H6", "Stale input"),
    ("H7", "Tool not permitted"),
    ("S1", "Evidence below threshold"),
    ("S2", "Soft checks failed"),
    ("S3", "Reviewer score low"),
    ("S4", "Open blockers"),
    ("S5", "Context pack stale"),
    ("S6", "Change risk over limit"),
    ("REVIEW-MAJOR", "Reviewer major finding"),
    ("REVIEWER-ERROR", "Reviewer could not run"),
    ("CAP-PACK", "Band capped: pack not fresh"),
]


def _exec(sql: str) -> None:
    """Run raw SQL on the migration connection (no placeholder parsing; PL/pgSQL uses %)."""
    cur = op.get_bind().connection.dbapi_connection.cursor()  # type: ignore[union-attr]
    try:
        cur.execute(sql)
    finally:
        cur.close()


def upgrade() -> None:
    values = ", ".join(f"('{c}', '{label}')" for c, label in CAUSES)
    _exec(f"INSERT INTO cause_labels (code, label) VALUES {values}")
    _exec(
        "INSERT INTO users (id, tenant_id, sso_subject, pseudonym, agent_role, active) VALUES "
        f"('{SVC_ENTRA_SYNC_ID}', '00000000-0000-0000-0000-000000000000', "
        "'00000000-0000-0000-0000-000000000000', 'eng-00000000', 'system:svc-entra-sync', false)"
    )


def downgrade() -> None:
    raise RuntimeError("Migrations are forward-only (SDD-08 §11.1).")
