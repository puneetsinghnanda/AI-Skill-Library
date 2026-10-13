"""Worker jobs: view refresh, partitions, retention with rollup, outbox gauges, worker tick."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.engine import Engine

from tests.conftest import (
    Person,
    TokenFactory,
    bearer,
    event,
    new_run,
    now_iso,
    post,
    project,
    run_started,
    step_decided,
)


def test_view_refresh(
    client: TestClient,
    token: TokenFactory,
    people: dict[str, Person],
    world: Any,
    keys_of: dict[str, str],
    migrated: Any,
    owner_db: Engine,
) -> None:
    from app.jobs import refresh_views

    run_id = new_run()
    post(
        client,
        token(people["eng"].oid, people["eng"].roles),
        [
            event(
                "run.started",
                run_started(world.system, workflow="defect-fix"),
                run_id,
                now_iso(-20),
            ),
            event(
                "step.decided",
                step_decided(
                    "triage", "defect-triage", "1.0.0", 1, "PASS", "High", keys_of["eng"], 1
                ),
                run_id,
                now_iso(-10),
            ),
        ],
        strict=True,
    )
    project(migrated)
    with owner_db.connect() as c:
        before = c.execute(
            text(
                "SELECT coalesce(sum(decisions), 0) FROM mv_skill_daily WHERE skill_id = 'defect-triage'"
            )
        ).scalar_one()
    out = refresh_views.run(migrated)
    assert set(out) == set(refresh_views.VIEWS)
    with owner_db.connect() as c:
        after = c.execute(
            text("SELECT sum(decisions) FROM mv_skill_daily WHERE skill_id = 'defect-triage'")
        ).scalar_one()
        logged = c.execute(
            text(
                "SELECT count(*) FROM view_refresh_log WHERE refreshed_at > now() - interval '1 minute'"
            )
        ).scalar_one()
    assert after == before + 1
    assert logged == len(refresh_views.VIEWS)


def test_partitions(migrated: Any, owner_db: Engine) -> None:
    from app.jobs import partitions

    assert partitions.run(migrated) == 0  # already present, idempotent
    with owner_db.connect() as c:
        assert c.execute(text("SELECT insights_partitions_ahead('events_raw')")).scalar_one() == 2
    with owner_db.connect() as c, pytest.raises(Exception, match="not a partitioned table"):
        c.execute(text("SELECT insights_ensure_partition('runs', CAST(now() AS date))"))


def test_retention_rollup_keeps_all_time_totals(
    client: TestClient,
    token: TokenFactory,
    people: dict[str, Person],
    world: Any,
    migrated: Any,
    owner_db: Engine,
) -> None:
    import random

    from app.jobs import refresh_views, retention

    rid = new_run()
    post(
        client,
        token(people["eng"].oid, people["eng"].roles),
        [
            event("run.started", run_started(world.system), rid, now_iso(-30)),
            event(
                "pr.opened",
                {
                    "repo": world.repo,
                    "number": random.randint(10**6, 10**7),
                    "draft": False,
                    "lowest_band": "High",
                },
                rid,
                now_iso(-20),
            ),
        ],
        strict=True,
    )
    project(migrated)
    with owner_db.begin() as c:
        c.execute(
            text("UPDATE pull_requests SET state = 'merged', merged_at = now() WHERE run_id = :r"),
            {"r": rid},
        )
    refresh_views.run(migrated)
    biz = bearer(token(people["biz"].oid, people["biz"].roles, client="portal"))
    before = client.get("/v1/insights/business?period=all", headers=biz).json()["data"]
    # age one merged run beyond the retention window
    with owner_db.begin() as c:
        c.execute(
            text(
                "UPDATE runs SET updated_at = now() - interval '14 months', started_at = now() - interval '14 months' "
                "WHERE id = :r"
            ),
            {"r": rid},
        )
        c.execute(
            text(
                "UPDATE pull_requests SET merged_at = now() - interval '14 months' WHERE run_id = :r"
            ),
            {"r": rid},
        )
    refresh_views.run(migrated)
    mid = client.get("/v1/insights/business?period=all", headers=biz).json()["data"]
    out = retention.run(migrated)
    assert out["runs"] >= 1
    refresh_views.run(migrated)
    after = client.get("/v1/insights/business?period=all", headers=biz).json()["data"]
    assert (
        after["prs_delivered"]["value"]
        == mid["prs_delivered"]["value"]
        == before["prs_delivered"]["value"]
    )  # M-04
    assert after["engineers_using"]["value"] == before["engineers_using"]["value"]  # M-08
    with owner_db.connect() as c:
        assert (
            c.execute(text("SELECT count(*) FROM runs WHERE id = :r"), {"r": rid}).scalar_one() == 0
        )
        assert (
            c.execute(
                text("SELECT count(*) FROM agg_monthly WHERE metric = 'prs_merged'")
            ).scalar_one()
            >= 1
        )


def test_audit_purge_floor(owner_db: Engine, migrated: Any) -> None:
    from app.db import engine

    with engine("app", migrated).connect() as c, pytest.raises(Exception, match="24 months"):
        c.execute(text("SELECT insights_purge_audit_log(now() - interval '1 month')"))
    with engine("app", migrated).connect() as c:
        assert (
            c.execute(
                text("SELECT insights_purge_audit_log(now() - interval '36 months')")
            ).scalar_one()
            == 0
        )


def test_outbox_watch_and_worker_tick(migrated: Any) -> None:
    from app.jobs import outbox_watch
    from app.obs import metrics
    from app.worker import Schedule, tick

    out = outbox_watch.run(migrated)
    assert "nonempty" in out
    assert tick(migrated, Schedule(), 1e9) >= 0
    assert metrics.JOB_LAST_SUCCESS.labels(job="refresh_views")._value.get() > 0


def test_rd6_workflow_name_choice() -> None:
    from app.catalogue.sync import non_canonical_workflow

    # RD-6 default (a): Doc 3 names are canonical; Doc 1 spellings are skipped by catalogue sync
    assert not non_canonical_workflow("brownfield-change", "doc3")
    assert non_canonical_workflow("brownfield-feature", "doc3")
    assert not non_canonical_workflow("brownfield-feature", "doc1")
    assert non_canonical_workflow("defect-fix", "doc1")
    assert not non_canonical_workflow("pipeline-check", "doc3")  # in neither set: accepted
