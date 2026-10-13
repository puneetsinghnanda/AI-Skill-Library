"""Projection and the run_id join (SDD-08 §7; §12 Order and Join)."""

from __future__ import annotations

import random
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.engine import Engine

from tests.conftest import (
    Person,
    TokenFactory,
    event,
    new_run,
    now_iso,
    post,
    project,
    run_started,
    step_decided,
)


def _run_events(world: Any, key: str, run_id: str, sess: str) -> list[dict[str, Any]]:
    t = [now_iso(-600 + i * 10) for i in range(12)]
    return [
        event(
            "run.started",
            run_started(world.system, session=sess, pod="brownfield-change-pod"),
            run_id,
            t[0],
        ),
        event(
            "step.started",
            {
                "step": "design",
                "skill": "design",
                "skill_version": "1.4.0",
                "attempt": 1,
                "seq": 4,
                "session_id": sess,
            },
            run_id,
            t[1],
        ),
        event(
            "step.decided",
            step_decided("design", "design", "1.4.0", 1, "RETRY", "Low", key, 4, ["S1"], sess),
            run_id,
            t[2],
        ),
        event(
            "step.started",
            {"step": "design", "skill": "design", "skill_version": "1.4.0", "attempt": 2, "seq": 4},
            run_id,
            t[3],
        ),
        event(
            "step.decided",
            step_decided("design", "design", "1.4.0", 2, "PASS", "High", key, 4),
            run_id,
            t[4],
        ),
        event(
            "question.created",
            {
                "step": "design",
                "question_id": "Q-01",
                "blocking": True,
                "ask_role": "product_owner",
                "evidence_ref": "context/system-baseline.md#ret",
            },
            run_id,
            t[5],
        ),
        event(
            "question.answered",
            {"step": "design", "question_id": "Q-01", "age_s": 30, "accepted_default": False},
            run_id,
            t[6],
        ),
        event(
            "run.status_changed",
            {
                "from": "RUNNING",
                "to": "PAUSED_APPROVAL",
                "reason_code": "paused_approval",
                "gate": "G-design",
                "step": "design",
            },
            run_id,
            t[7],
        ),
        event(
            "approval.recorded",
            {
                "gate": "G-design",
                "decision": "approve",
                "approver_role": "tech_lead",
                "step": "design",
                "signature_block_sha256": "b" * 64,
                "key_id": key,
            },
            run_id,
            t[8],
        ),
        event(
            "hook.decision",
            {"hook": "pre-tool", "decision": "deny", "code": "E-POL-01"},
            run_id,
            t[9],
        ),
        event(
            "pr.opened",
            {
                "repo": world.repo,
                "number": random.randint(1000, 999999),
                "draft": False,
                "lowest_band": "High",
            },
            run_id,
            t[10],
        ),
        event(
            "run.status_changed",
            {"from": "RUNNING", "to": "COMPLETED", "reason_code": "pr_opened"},
            run_id,
            t[11],
        ),
    ]


def _snapshot(c: Any, run_id: str) -> dict[str, Any]:
    run = c.execute(
        text(
            "SELECT system_id, workflow_id, pod_id, status, end_reason, current_step_id, lowest_band, "
            "is_partial FROM runs WHERE id = :r"
        ),
        {"r": run_id},
    ).one()
    steps = c.execute(
        text(
            "SELECT step_id, attempt, seq, outcome, band, started_at IS NOT NULL FROM steps "
            "WHERE run_id = :r ORDER BY 1, 2"
        ),
        {"r": run_id},
    ).all()
    q = c.execute(
        text(
            "SELECT question_id, created_at IS NOT NULL, answered_at IS NOT NULL FROM questions "
            "WHERE run_id = :r"
        ),
        {"r": run_id},
    ).all()
    a = c.execute(
        text("SELECT gate, decision, requested_at IS NOT NULL FROM approvals WHERE run_id = :r"),
        {"r": run_id},
    ).all()
    return {
        "run": tuple(run),
        "steps": [tuple(x) for x in steps],
        "q": [tuple(x) for x in q],
        "a": [tuple(x) for x in a],
    }


def test_full_run_projection(
    client: TestClient,
    token: TokenFactory,
    people: dict[str, Person],
    world: Any,
    keys_of: dict[str, str],
    migrated: Any,
    owner_db: Engine,
) -> None:
    run_id, sess = new_run(), "sess-full-1"
    tok = token(people["eng"].oid, people["eng"].roles)
    post(client, tok, strict=True, events=_run_events(world, keys_of["eng"], run_id, sess))
    project(migrated)
    with owner_db.connect() as c:
        snap = _snapshot(c, run_id)
        assert snap["run"][3:6] == ("COMPLETED", "pr_opened", "design")
        assert snap["run"][6] == "High" and snap["run"][7] is False
        assert snap["run"][2] == "brownfield-change-pod"
        assert len(snap["steps"]) == 2
        assert snap["q"] == [("Q-01", True, True)]
        assert snap["a"] == [("G-design", "approve", True)]
        assert (
            c.execute(
                text("SELECT count(*) FROM check_records WHERE run_id = :r"), {"r": run_id}
            ).scalar_one()
            == 2
        )
        assert (
            c.execute(
                text("SELECT count(*) FROM run_sessions WHERE run_id = :r AND session_id = :s"),
                {"r": run_id, "s": sess},
            ).scalar_one()
            == 1
        )
        assert (
            c.execute(
                text("SELECT count(*) FROM pull_requests WHERE run_id = :r"), {"r": run_id}
            ).scalar_one()
            == 1
        )
        assert (
            c.execute(
                text(
                    "SELECT n FROM hook_daily WHERE decision = 'deny' AND code = 'E-POL-01' "
                    "AND system_id = CAST(:s AS uuid)"
                ),
                {"s": world.system_id},
            ).scalar_one()
            >= 1
        )
        # anchors from the engineer's own key (SDD-07 §7.2)
        assert (
            c.execute(
                text("SELECT count(*) FROM signature_anchors WHERE key_id = :k"),
                {"k": keys_of["eng"]},
            ).scalar_one()
            >= 3
        )
        assert (
            c.execute(
                text("SELECT count(*) FROM events_raw WHERE run_id = :r AND projected_at IS NULL"),
                {"r": run_id},
            ).scalar_one()
            == 0
        )


def test_order_independence(
    client: TestClient,
    token: TokenFactory,
    people: dict[str, Person],
    world: Any,
    keys_of: dict[str, str],
    migrated: Any,
    owner_db: Engine,
) -> None:
    """Shuffle a run's events -> identical runs/steps rows (SDD-08 §12 Order)."""
    tok = token(people["eng"].oid, people["eng"].roles)
    snaps = []
    rng = random.Random(7)
    for i in range(12):
        run_id = new_run()
        evs = _run_events(world, keys_of["eng"], run_id, f"sess-order-{i}")
        rng.shuffle(evs)
        # deliver in two late batches, as an outbox flush would
        post(client, tok, evs[:6], strict=True)
        project(migrated)
        post(client, tok, evs[6:], strict=True)
        project(migrated)
        with owner_db.connect() as c:
            snaps.append(_snapshot(c, run_id))
    assert all(s == snaps[0] for s in snaps), snaps


def test_parked_until_system_exists(
    client: TestClient,
    token: TokenFactory,
    people: dict[str, Person],
    migrated: Any,
    owner_db: Engine,
) -> None:
    run_id = new_run()
    tok = token(people["eng"].oid, people["eng"].roles)
    e = event("run.started", run_started("SYS-NEW9"), run_id)
    post(client, tok, strict=True, events=[e])
    project(migrated)
    with owner_db.connect() as c:
        row = c.execute(
            text("SELECT projected_at, projection_error FROM events_raw WHERE event_id = :e"),
            {"e": e["event_id"]},
        ).one()
    assert row.projected_at is None and row.projection_error == "unknown_system"


def test_partial_run_placeholder(
    client: TestClient,
    token: TokenFactory,
    people: dict[str, Person],
    world: Any,
    keys_of: dict[str, str],
    migrated: Any,
    owner_db: Engine,
) -> None:
    run_id = new_run()
    tok = token(people["eng"].oid, people["eng"].roles)
    post(
        client,
        tok,
        strict=True,
        events=[
            event(
                "question.created",
                {"step": "req", "question_id": "Q-09", "blocking": True, "ask_role": "client"},
                run_id,
            )
        ],
    )
    project(migrated)
    with owner_db.connect() as c:
        assert (
            c.execute(text("SELECT is_partial FROM runs WHERE id = :r"), {"r": run_id}).scalar_one()
            is True
        )
    post(client, tok, strict=True, events=[event("run.started", run_started(world.system), run_id)])
    project(migrated)
    with owner_db.connect() as c:
        assert (
            c.execute(text("SELECT is_partial FROM runs WHERE id = :r"), {"r": run_id}).scalar_one()
            is False
        )


def test_session_device_and_context(
    client: TestClient,
    token: TokenFactory,
    people: dict[str, Person],
    world: Any,
    keys_of: dict[str, str],
    migrated: Any,
    owner_db: Engine,
) -> None:
    from app.crypto import ulid

    dev = ulid("dev")
    tok = token(people["lead"].oid, people["lead"].roles)
    post(
        client,
        tok,
        strict=True,
        events=[
            event(
                "session.started",
                {
                    "session_id": "sess-dev-1",
                    "device_id": dev,
                    "plugin_version": "0.1.0",
                    "tsl_version": "0.1.0",
                    "os": "linux",
                    "outbox_depth": 3,
                    "outbox_oldest_at": now_iso(-90000),
                },
                occurred=now_iso(-100),
            ),
            event(
                "session.ended",
                {
                    "session_id": "sess-dev-1",
                    "device_id": dev,
                    "outbox_depth": 0,
                    "outbox_oldest_at": None,
                },
                occurred=now_iso(-50),
            ),
            event(
                "context.signed",
                {
                    "system": world.system,
                    "age_days": 0,
                    "drift_files": 0,
                    "status": "fresh",
                    "signature_sha256": "c" * 64,
                    "key_id": keys_of["lead"],
                },
            ),
            event(
                "eval.recorded",
                {
                    "skill": "design",
                    "version": "1.4.0",
                    "cases": 12,
                    "pass_rate": 0.92,
                    "key_id": keys_of["owner"],
                    "result_sha256": "d" * 64,
                },
            ),
        ],
    )
    project(migrated)
    with owner_db.connect() as c:
        d = c.execute(
            text("SELECT os, outbox_depth FROM devices WHERE device_id = :d"), {"d": dev}
        ).one()
        assert d.os == "linux" and d.outbox_depth == 0
        sysrow = c.execute(
            text("SELECT pack_status, pack_signed_by::text FROM systems WHERE code = :c"),
            {"c": world.system},
        ).one()
        assert sysrow.pack_status == "fresh" and sysrow.pack_signed_by == people["lead"].user_id
        assert (
            c.execute(
                text(
                    "SELECT eval_cases FROM skill_versions WHERE skill_id = 'design' AND version = '1.4.0'"
                )
            ).scalar_one()
            == 12
        )
        # eval sent by another user's key: anchor ignored (key must belong to the event user)
        assert (
            c.execute(
                text("SELECT count(*) FROM signature_anchors WHERE sha256 = :h"), {"h": "d" * 64}
            ).scalar_one()
            == 0
        )
        assert (
            c.execute(
                text("SELECT count(*) FROM signature_anchors WHERE sha256 = :h"), {"h": "c" * 64}
            ).scalar_one()
            == 1
        )
