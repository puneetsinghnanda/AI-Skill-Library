"""Run status reaches the portal right away: run-changing commands send queued events (best effort)."""

from __future__ import annotations

from typing import Any

import pytest

from e2e_steps import SESSION, start_run
from helpers import World
from tsl.insights.client import HttpResult, InsightsUnavailable


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


def test_state_start_itself_sends_run_started(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Turn off the CLI's after-command send so only start()'s own flush can deliver the event.
    monkeypatch.setattr("tsl.telemetry.emit.send_soon", lambda get_rt: None)
    run_id = start_run(world)
    sent = [e for e in world.insights.events if e.get("type") == "run.started"]
    assert [e.get("run_id") for e in sent] == [run_id]


def test_state_start_succeeds_while_the_event_service_is_offline(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Start itself needs Insights (identity); only event delivery is down here.
    def offline(token: str, events: list[dict[str, Any]]) -> HttpResult:
        raise InsightsUnavailable("offline")

    monkeypatch.setattr(world.insights, "post_events", offline)
    assert start_run(world)
    assert world.rt().outbox().stats()["pending"] >= 1


def test_state_start_succeeds_when_the_flush_itself_raises(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(rt: object, max_seconds: float) -> None:
        raise RuntimeError("token cache corrupt")

    monkeypatch.setattr("tsl.telemetry.emit.flush", broken)
    assert start_run(world)
    assert world.rt().outbox().stats()["pending"] >= 1
