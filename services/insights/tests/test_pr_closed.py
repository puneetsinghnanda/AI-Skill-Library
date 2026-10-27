"""pr.closed from tsl pr-sync: a merge or close the webhook missed (SDD-08 §4.5)."""

from __future__ import annotations

import random
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.engine import Engine

from tests.conftest import Person, TokenFactory, event, new_run, now_iso, post, project, run_started


def _pr(owner_db: Engine, n: int) -> Any:
    with owner_db.connect() as c:
        return c.execute(
            text(
                "SELECT state, merged_at IS NOT NULL AS merged, closed_at IS NOT NULL AS closed, "
                "run_id FROM pull_requests WHERE number = :n"
            ),
            {"n": n},
        ).one()


def test_pr_closed_marks_an_opened_pr_merged(
    client: TestClient,
    token: TokenFactory,
    people: dict[str, Person],
    world: Any,
    migrated: Any,
    owner_db: Engine,
) -> None:
    run_id = new_run()
    n = random.randint(100_000, 999_999)
    tok = token(people["eng"].oid, people["eng"].roles)
    post(
        client,
        tok,
        [
            event("run.started", run_started(world.system), run_id),
            event(
                "pr.opened",
                {"repo": world.repo, "number": n, "draft": True, "lowest_band": "High"},
                run_id,
            ),
            event(
                "pr.closed",
                {"repo": world.repo, "number": n, "merged": True, "closed_at": now_iso()},
                run_id,
            ),
        ],
        strict=True,
    )
    project(migrated)
    pr = _pr(owner_db, n)
    assert pr.state == "merged" and pr.merged and pr.run_id == run_id


def test_pr_closed_without_merge_never_unmerges(
    client: TestClient,
    token: TokenFactory,
    people: dict[str, Person],
    world: Any,
    migrated: Any,
    owner_db: Engine,
) -> None:
    run_id = new_run()
    n = random.randint(100_000, 999_999)
    tok = token(people["eng"].oid, people["eng"].roles)
    closed = {"repo": world.repo, "number": n, "closed_at": now_iso()}
    post(
        client,
        tok,
        [
            event("run.started", run_started(world.system), run_id),
            event("pr.closed", {**closed, "merged": False}, run_id),
        ],
        strict=True,
    )
    project(migrated)
    pr = _pr(owner_db, n)
    assert pr.state == "closed" and pr.closed and not pr.merged
    post(client, tok, [event("pr.closed", {**closed, "merged": True}, run_id)], strict=True)
    project(migrated)
    assert _pr(owner_db, n).state == "merged"
    post(client, tok, [event("pr.closed", {**closed, "merged": False}, run_id)], strict=True)
    project(migrated)
    assert _pr(owner_db, n).state == "merged"
