"""A step run in a forked subagent (roadmap 25-27 Nov, B1): tsl next picks it, tsl step brief
hands the subagent the same skill text and inputs, and the attempt records the runner."""

from __future__ import annotations

import json
from typing import Any

from e2e_steps import SESSION, next_action, start_run
from helpers import World, ticket_snapshot
from tsl.harness.brief import runner_for
from tsl.schemas.registry import errors
from tsl.state.store import find_step, latest


def _runner_env(w: World, value: str) -> None:
    rt = w.rt("eng", SESSION)
    rt.env = {**rt.env, "TSL_STEP_RUNNER": value}


def _open_first_step(w: World) -> tuple[str, str, str]:
    """Start a run and open its first step with the ticket snapshot in place."""
    run_id = start_run(w)
    _c, env = next_action(w, run_id)
    tp = w.companion / f"artifacts/ABC-142/{run_id}/ticket.md"
    tp.parent.mkdir(parents=True, exist_ok=True)
    tp.write_text(ticket_snapshot(run_id), encoding="utf-8")
    return run_id, str(env["data"]["step"]), str(env["data"]["artifact_path"])


def _state(w: World, run_id: str) -> dict[str, Any]:
    return dict(json.loads((w.companion / "runs" / run_id / "state.json").read_text()))


def test_runner_for_reads_step_and_context() -> None:
    assert runner_for({}, "ut") is None
    assert runner_for({"TSL_STEP_RUNNER": "ut=full"}, "ut") == {"mode": "fork", "context": "full"}
    env = {"TSL_STEP_RUNNER": " split=artifacts , ut=full"}
    assert runner_for(env, "split") == {"mode": "fork", "context": "artifacts"}
    assert runner_for({"TSL_STEP_RUNNER": "ut=everything"}, "ut") is None
    assert runner_for({"TSL_STEP_RUNNER": "ut=full"}, "split") is None


def test_next_names_the_runner_only_for_the_chosen_step(world: World) -> None:
    run_id = start_run(world)
    _c, env = next_action(world, run_id)
    assert "runner" not in env["data"]
    _runner_env(world, f"{env['data']['step']}=full")
    _c, env = next_action(world, run_id)
    assert env["data"]["runner"] == {"mode": "fork", "context": "full"}
    assert errors("next-action.v1", env["data"]) == []


def test_brief_carries_skill_text_and_inputs_and_records_the_runner(world: World) -> None:
    run_id, step, art = _open_first_step(world)
    code, _e, text, err = world.cli(
        ["step", "brief", art, "--context", "artifacts"], session=SESSION
    )
    assert code == 0, err
    assert text.startswith(f"# Step brief: {step} (attempt 1)")
    assert "!`tsl verify" not in text  # the preamble is replaced by its data
    assert '"allowed_tools"' in text and art in text
    assert "## Open questions of this run" in text
    assert "## Preloaded context" not in text
    st = _state(world, run_id)
    a = latest(find_step(st, step))
    assert a is not None and a["runner"] == {"mode": "fork", "context": "artifacts"}
    assert a["skill_started_at"]  # the launch is marked as with the skill preamble
    assert errors("run-state.v1", st) == []


def test_full_context_preloads_sections_within_budget(world: World) -> None:
    _run_id, _step, art = _open_first_step(world)
    code, out, _t, err = world.cli(
        ["step", "brief", art, "--context", "full", "--json"],
        session=SESSION,
    )
    assert code == 0 and out is not None, err
    data = out["data"]
    assert data["runner"]["context"] == "full"
    assert "## Preloaded context" in data["brief"]
    for p in data["preloaded"]:
        assert f"### {p['path']}" in data["brief"]


def test_unknown_context_is_a_usage_error(world: World) -> None:
    run_id = start_run(world)
    _c, env = next_action(world, run_id)
    code, out, _t, _e = world.cli(
        ["step", "brief", env["data"]["artifact_path"], "--context", "all", "--json"],
        session=SESSION,
    )
    assert out is not None and out["code"] == "E-USE-01" and code != 0
