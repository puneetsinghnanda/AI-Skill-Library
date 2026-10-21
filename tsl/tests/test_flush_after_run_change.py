"""Run status reaches the portal right away: run-changing commands send queued events (best effort)."""

from __future__ import annotations

from e2e_steps import SESSION, start_run
from helpers import World
from tsl.insights.client import HttpResult


def test_state_start_sends_run_started_without_waiting_for_session_end(world: World) -> None:
    run_id = start_run(world)
    sent = [e for e in world.insights.events if e.get("type") == "run.started"]
    assert [e.get("run_id") for e in sent] == [run_id]
    assert world.rt().outbox().stats()["pending"] == 0


def test_cancel_sends_the_status_change(world: World) -> None:
    run_id = start_run(world)
    code, env, _, err = world.cli(
        ["state", "cancel", run_id, "--reason", "test", "--json"], session=SESSION
    )
    assert code == 0, (env, err)
    changed = [e for e in world.insights.events if e.get("type") == "run.status_changed"]
    assert changed and changed[-1]["body"]["to"] == "COMPLETED"


def test_event_service_failure_never_fails_the_command(world: World) -> None:
    world.insights.event_responses = [HttpResult(503, None)] * 5
    run_id = start_run(world)
    assert run_id
    assert world.rt().outbox().stats()["pending"] >= 1
