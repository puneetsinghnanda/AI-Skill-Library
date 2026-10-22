"""tsl smoke: one command proves the run plumbing end to end, with no AI (hardening)."""

from __future__ import annotations

import pytest

from helpers import World
from tsl.insights.client import HttpResult


def test_smoke_run_passes_and_leaves_a_cancelled_run(world: World) -> None:
    code, env, _, err = world.cli(["smoke", "--json"])
    assert env is not None, err
    assert code == 0, (env, err)
    steps = {s["name"]: s["ok"] for s in env["data"]["steps"]}
    for name in (
        "pre-flight",
        "start run",
        "first step",
        "harness checks",
        "review",
        "decide",
        "cancel",
        "portal",
    ):
        assert steps.get(name) is True, (name, env["data"]["steps"])
    run_id = env["data"]["run_id"]
    sent = [e for e in world.insights.events if e.get("run_id") == run_id]
    assert any(e["type"] == "run.status_changed" and e["body"]["to"] == "COMPLETED" for e in sent)
    lock_dir = world.companion / "runs" / "active"
    assert not any(p.name.startswith("SMOKE-") for p in lock_dir.iterdir())


def test_smoke_stops_before_starting_when_pre_flight_fails(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(world.insights, "get_me", lambda token: HttpResult(401, None))
    code, env, _, err = world.cli(["smoke", "--json"])
    assert env is not None, err
    assert code == 3 and env["code"] == "E-ENV-01" and env["next"] == "tsl login", env
    assert not list((world.companion / "runs").glob("run_*"))


def test_smoke_does_not_need_docker(world: World) -> None:
    world.verifier.up = False
    code, env, _, err = world.cli(["smoke", "--json"])
    assert env is not None and code == 0, (env, err)
