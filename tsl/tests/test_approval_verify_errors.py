"""Resume after an approval names the real problem, not 'approver lacks role' (hardening)."""

from __future__ import annotations

from typing import Any

import pytest

from e2e_steps import SESSION, do_req_step, next_action, start_run
from helpers import World, git
from tsl.identity import keys as keysmod
from tsl.insights.client import HttpResult, InsightsUnavailable


def _approved_run(world: World) -> str:
    run_id = start_run(world)
    assert do_req_step(world, run_id)["code"] == 0
    _, nxt = next_action(world, run_id)
    assert nxt["code"] == "E-RUN-02", nxt
    appr = world.companion / f"runs/{run_id}/approvals.md"
    appr.write_text(
        appr.read_text().replace(
            "decision:          # approve | reject | changes | abort", "decision: approve"
        )
    )
    git(world.companion, "commit", "-qam", "approve G-req")
    git(world.companion, "push", "-q", "origin", "main")
    code, approved, _, err = world.cli(["approve", run_id, "G-req", "--json"], user="tl")
    assert code == 0, (approved, err)
    world.sync_companion()
    # The run owner's machine has never seen the approver's key (as on a real second laptop).
    cache = world.rt().home.key_cache("x").parent
    for f in cache.glob("*.json") if cache.exists() else []:
        f.unlink()
    return run_id


def _resume(world: World, run_id: str) -> dict[str, Any]:
    _, env, _, err = world.cli(["state", "resume", run_id, "--json"], session=SESSION)
    assert env is not None, err
    return env


def test_own_sign_in_refused_says_log_in_again(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_id = _approved_run(world)
    monkeypatch.setattr(world.insights, "get_key", lambda token, key_id: HttpResult(401, None))
    env = _resume(world, run_id)
    assert env["code"] == "E-AUTH-01", env
    assert "tsl login" in env["next"]


def test_unregistered_approver_key_is_named(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    run_id = _approved_run(world)
    monkeypatch.setattr(world.insights, "get_key", lambda token, key_id: HttpResult(404, None))
    env = _resume(world, run_id)
    assert env["code"] == "E-AUTH-11", env
    assert "not registered" in env["message"] and "G-req" in env["message"]


def test_unreachable_service_is_woken_then_reported(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_id = _approved_run(world)
    calls: list[int] = []

    def down(token: str, key_id: str) -> HttpResult:
        calls.append(1)
        raise InsightsUnavailable("asleep")

    monkeypatch.setattr(world.insights, "get_key", down)
    monkeypatch.setattr(keysmod, "WAKE_SECONDS", 0.0)
    env = _resume(world, run_id)
    assert env["code"] == "E-NET-02", env
    assert len(calls) == 2  # tried, woke the service, tried again


def test_valid_approval_still_resumes(world: World) -> None:
    run_id = _approved_run(world)
    env = _resume(world, run_id)
    assert env["code"] == "OK" and env["data"]["status"] == "RUNNING", env
