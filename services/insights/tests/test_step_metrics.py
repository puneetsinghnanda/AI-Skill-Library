"""D1: run metrics from `step.decided` are stored per attempt and shown on the run page.

The numbers are HMS-27's req attempts from `tsl state show <run> --metrics` (Shubham, D1).
"""

from __future__ import annotations

from typing import Any

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
    skill_version,
    step_decided,
)


def _decided(attempt: int, outcome: str, key: str, metrics: dict[str, Any] | None) -> Any:
    b = step_decided(
        "req",
        "requirement-review",
        skill_version("requirement-review"),
        attempt,
        outcome,
        "High",
        key,
        1,
    )
    if metrics is not None:
        b["metrics"] = metrics
        b["duration_ms"] = metrics["active_ms"]
    return b


def _metrics(
    output: int, cache_read: int, cache_write: int, calls: int, wait_s: int, active_ms: int
) -> dict[str, Any]:
    return {
        "tokens": {
            "input": 48,
            "output": output,
            "cache_read": cache_read,
            "cache_write": cache_write,
            "calls": calls,
            "subagent_calls": 5,
        },
        "models": ["claude-opus-5-5"],
        "wait_s": wait_s,
        "active_ms": active_ms,
        "source": "transcript",
    }


def test_step_metrics_stored_and_shown(
    client: TestClient,
    token: TokenFactory,
    people: dict[str, Person],
    world: Any,
    keys_of: dict[str, str],
    migrated: Any,
    owner_db: Engine,
) -> None:
    run_id = new_run()
    key = keys_of["eng"]
    a1 = _metrics(18890, 1_693_514, 72951, 23, 378, 216_000)
    a2 = _metrics(14800, 1_100_000, 53900, 13, 0, 144_000)
    no_transcript = {"tokens": None, "wait_s": 0, "active_ms": 90_000, "source": "none"}
    post(
        client,
        token(people["eng"].oid, people["eng"].roles),
        [
            event("run.started", run_started(world.system), run_id, now_iso(-600)),
            event("step.decided", _decided(1, "RETRY", key, a1), run_id, now_iso(-500)),
            event(
                "step.decided", _decided(2, "PASS-WITH-FINDINGS", key, a2), run_id, now_iso(-400)
            ),
            event(
                "step.decided",
                {
                    **_decided(1, "PASS", key, no_transcript),
                    "step": "split",
                    "skill": "story-split",
                    "skill_version": skill_version("story-split"),
                    "seq": 2,
                },
                run_id,
                now_iso(-300),
            ),
        ],
        strict=True,
    )
    project(migrated)

    with owner_db.connect() as c:
        row = c.execute(
            text(
                "SELECT tokens_in, tokens_out, cache_read, cache_write, calls, subagent_calls, "
                "wait_s, models, metrics_source, duration_ms FROM steps "
                "WHERE run_id = :r AND step_id = 'req' AND attempt = 1"
            ),
            {"r": run_id},
        ).one()
    assert tuple(row) == (
        48,
        18890,
        1_693_514,
        72951,
        23,
        5,
        378,
        ["claude-opus-5-5"],
        "transcript",
        216_000,
    )

    d = client.get(
        f"/v1/runs/{run_id}",
        headers=bearer(token(people["eng"].oid, people["eng"].roles, client="portal")),
    ).json()["data"]
    req = next(s for s in d["steps"] if s["step_id"] == "req")
    m1 = req["attempts"][0]["metrics"]
    assert m1["source"] == "transcript" and m1["wait_s"] == 378
    assert m1["tokens"] == {
        "input": 48,
        "output": 18890,
        "cache_read": 1_693_514,
        "cache_write": 72951,
        "calls": 23,
        "subagent_calls": 5,
    }
    split = next(s for s in d["steps"] if s["step_id"] == "split")
    assert split["attempts"][0]["metrics"] == {
        "source": "none",
        "wait_s": 0,
        "models": [],
        "tokens": None,
    }
    t = d["step_metrics"]
    assert (t["attempts"], t["retries"], t["measured_attempts"], t["token_attempts"]) == (
        3,
        1,
        3,
        2,
    )
    assert (t["ai_ms"], t["wait_s"], t["calls"], t["subagent_calls"]) == (450_000, 378, 36, 10)
    assert t["tokens"] == {
        "input": 96,
        "output": 33690,
        "cache_read": 2_793_514,
        "cache_write": 126_851,
    }


def test_run_from_an_older_tsl_has_no_metrics(
    client: TestClient,
    token: TokenFactory,
    people: dict[str, Person],
    world: Any,
    keys_of: dict[str, str],
    migrated: Any,
) -> None:
    run_id = new_run()
    post(
        client,
        token(people["eng"].oid, people["eng"].roles),
        [
            event("run.started", run_started(world.system), run_id, now_iso(-600)),
            event("step.decided", _decided(1, "PASS", keys_of["eng"], None), run_id, now_iso(-500)),
        ],
        strict=True,
    )
    project(migrated)
    d = client.get(
        f"/v1/runs/{run_id}",
        headers=bearer(token(people["eng"].oid, people["eng"].roles, client="portal")),
    ).json()["data"]
    req = next(s for s in d["steps"] if s["step_id"] == "req")
    assert req["attempts"][0]["metrics"] is None and d["step_metrics"] is None


def test_no_transcript_means_unknown_not_zero(
    client: TestClient,
    token: TokenFactory,
    people: dict[str, Person],
    world: Any,
    keys_of: dict[str, str],
    migrated: Any,
) -> None:
    """Every attempt without a transcript: tokens and calls are null, not 0 (Gaurav, #79)."""
    run_id = new_run()
    none = {"tokens": None, "wait_s": 30, "active_ms": 60_000, "source": "none"}
    odd = {"tokens": None, "wait_s": 0, "active_ms": 60_000, "source": "transcript"}  # schema-valid
    post(
        client,
        token(people["eng"].oid, people["eng"].roles),
        [
            event("run.started", run_started(world.system), run_id, now_iso(-600)),
            event(
                "step.decided", _decided(1, "RETRY", keys_of["eng"], none), run_id, now_iso(-500)
            ),
            event("step.decided", _decided(2, "PASS", keys_of["eng"], odd), run_id, now_iso(-400)),
        ],
        strict=True,
    )
    project(migrated)
    d = client.get(
        f"/v1/runs/{run_id}",
        headers=bearer(token(people["eng"].oid, people["eng"].roles, client="portal")),
    ).json()["data"]
    req = next(s for s in d["steps"] if s["step_id"] == "req")
    assert [a["metrics"]["tokens"] for a in req["attempts"]] == [None, None]
    t = d["step_metrics"]
    assert (t["measured_attempts"], t["token_attempts"], t["ai_ms"], t["wait_s"]) == (
        2,
        0,
        120_000,
        30,
    )
    assert t["calls"] is None and t["subagent_calls"] is None and t["tokens"] is None
