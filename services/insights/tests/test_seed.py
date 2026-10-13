"""Seed data (SDD-08 §11.3): loads through the normal ingest path; refuses ENV=prod."""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.config import Settings
from tests.conftest import ROOT


def test_seed_refuses_prod(migrated: Settings) -> None:
    from seed.generate import main

    prod = Settings(**{**migrated.model_dump(), "env": "prod"})
    assert main(["--catalogue", str(ROOT), "--runs", "1"], prod) == 2


def test_seed_loads(migrated: Settings, owner_db: Engine, app: Any) -> None:
    from seed.generate import main

    with owner_db.connect() as c:
        before = c.execute(
            text("SELECT count(*) FROM runs WHERE ticket_ref LIKE 'DEMO-%'")
        ).scalar_one()
    assert main(["--catalogue", str(ROOT), "--runs", "24"], migrated) == 0
    with owner_db.connect() as c:
        after = c.execute(
            text("SELECT count(*) FROM runs WHERE ticket_ref LIKE 'DEMO-%' AND NOT is_partial")
        ).scalar_one()
        assert (
            c.execute(
                text(
                    "SELECT count(*) FROM events_raw WHERE projected_at IS NULL "
                    "AND body->>'ticket_ref' LIKE 'DEMO-%'"
                )
            ).scalar_one()
            == 0
        )
    assert after - before == 24
