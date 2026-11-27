"""A step run in a forked subagent (roadmap 25-27 Nov, B1): tsl next picks it, tsl step brief
hands the subagent the same skill text and inputs, and the attempt records the runner."""

from __future__ import annotations

import json
from typing import Any

from e2e_steps import SESSION, next_action, start_run
from helpers import World, ticket_snapshot
from tsl.harness.brief import runner_for, runners_from_env
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


def test_runners_from_env_reads_steps_and_contexts() -> None:
    steps = ["req", "split", "ut"]
    assert runners_from_env({}, steps) == {}
    full = {"mode": "fork", "context": "full"}
    assert runners_from_env({"TSL_STEP_RUNNER": "ut=full"}, steps) == {"ut": full}
    env = {"TSL_STEP_RUNNER": " split=artifacts , ut=full"}
    assert runners_from_env(env, steps) == {
        "split": {"mode": "fork", "context": "artifacts"},
        "ut": full,
    }
    assert runners_from_env({"TSL_STEP_RUNNER": "ut=everything"}, steps) == {}
    assert runners_from_env({"TSL_STEP_RUNNER": "nope=full"}, steps) == {}
    assert runner_for({"step_runners": {"ut": full}}, "ut") == full
    assert runner_for({"step_runners": {"ut": full}}, "split") is None
    assert runner_for({}, "ut") is None


def test_runner_is_pinned_at_start_and_next_ignores_the_env(world: World) -> None:
    # Started without the variable: setting it later moves no step (the HMS-34 baseline).
    run_id = start_run(world)
    _c, env = next_action(world, run_id)
    first = str(env["data"]["step"])
    assert "runner" not in env["data"]
    _runner_env(world, f"{first}=full")
    _c, env = next_action(world, run_id)
    assert "runner" not in env["data"]
    assert "step_runners" not in _state(world, run_id)


def test_next_names_the_pinned_runner_only_for_the_chosen_step(world: World) -> None:
    _runner_env(world, "req=full")
    code, out, _t, err = world.cli(
        ["state", "start", "brownfield-change", "ABC-142", "--json"], session=SESSION
    )
    assert code == 0 and out is not None, err
    run_id = str(out["data"]["run_id"])
    assert out["data"]["step_runners"] == {"req": {"mode": "fork", "context": "full"}}
    st = _state(world, run_id)
    assert st["step_runners"] == {"req": {"mode": "fork", "context": "full"}}
    assert errors("run-state.v1", st) == []
    _runner_env(world, "")  # the env no longer matters once the run started
    _c, env = next_action(world, run_id)
    assert env["data"]["step"] == "req"
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


def test_brief_names_the_product_clones_in_both_contexts(world: World) -> None:
    _run_id, _step, art = _open_first_step(world)
    for context in ("artifacts", "full"):
        code, out, _t, err = world.cli(
            ["step", "brief", art, "--context", context, "--json"], session=SESSION
        )
        assert code == 0 and out is not None, err
        data = out["data"]
        assert "## Product repos" in data["brief"]
        assert [r["repo"] for r in data["product_repos"]] == ["sample-orders"]
        for r in data["product_repos"]:
            assert f"- {r['repo']}: {r['path']}" in data["brief"]
        assert "Never search the companion repo" in data["brief"]


def test_unknown_context_is_a_usage_error(world: World) -> None:
    run_id = start_run(world)
    _c, env = next_action(world, run_id)
    code, out, _t, _e = world.cli(
        ["step", "brief", env["data"]["artifact_path"], "--context", "all", "--json"],
        session=SESSION,
    )
    assert out is not None and out["code"] == "E-USE-01" and code != 0
