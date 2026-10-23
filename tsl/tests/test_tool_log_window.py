"""H5 and H7 read the tool log from the skill's launch; sessions that lost the run are not logged."""

from __future__ import annotations

import json
from typing import Any

from e2e_steps import SESSION, do_req_step, hook, next_action, start_run
from helpers import World
from tsl.core.clock import iso
from tsl.core.repo import Companion
from tsl.state.store import RunStore, find_step, latest


def _state(w: World, run_id: str) -> dict[str, Any]:
    return dict(json.loads((w.companion / "runs" / run_id / "state.json").read_text()))


def _log(w: World, run_id: str) -> list[dict[str, Any]]:
    p = w.companion / "runs" / run_id / "tool-log.jsonl"
    if not p.is_file():
        return []
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]


def _append(w: World, run_id: str, ts: str, step: str, tool: str, target: str) -> None:
    line = {
        "ts": ts,
        "session_id": "sess-setup",
        "step": step,
        "attempt": 1,
        "tool": tool,
        "target": target,
        "decision": "allow",
        "code": None,
    }
    p = w.companion / "runs" / run_id / "tool-log.jsonl"
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(line, sort_keys=True) + "\n")


def _h7(w: World, art: str) -> dict[str, Any]:
    _code, env, _, err = w.cli(["verify", art, "--json"], session=SESSION)
    assert env is not None, err
    return next(g for g in env["data"]["gates"] if g["id"] == "H7")


def test_verify_inputs_records_skill_launch_and_relaunch_moves_it(world: World) -> None:
    run_id = start_run(world)
    res = do_req_step(world, run_id, until="written")
    a = latest(find_step(_state(world, run_id), "req"))
    assert a is not None and a["skill_started_at"] == iso(world.clock())
    world.clock.advance(minutes=5)
    code, _env, _, err = world.cli(
        ["verify", res["artifact"], "--inputs", "--json"], session=SESSION
    )
    assert code == 0, err
    a = latest(find_step(_state(world, run_id), "req"))
    assert a is not None and a["skill_started_at"] == iso(world.clock())


def test_h7_ignores_calls_logged_before_the_skill_launched(world: World) -> None:
    run_id = start_run(world)
    _c, env = next_action(world, run_id)
    step = env["data"]["step"]
    _append(world, run_id, "2025-12-31T23:59:00Z", step, "Bash", "winget install gitleaks")
    _append(world, run_id, "2025-12-31T23:59:30Z", step, "Edit", "notes.md")
    res = do_req_step(world, run_id, until="written")
    h7 = _h7(world, res["artifact"])
    assert h7["status"] == "pass", h7


def test_h7_still_fails_a_disallowed_call_after_launch(world: World) -> None:
    run_id = start_run(world)
    res = do_req_step(world, run_id, until="written")
    _append(world, run_id, iso(world.clock()), "req", "Bash", "winget install gitleaks")
    h7 = _h7(world, res["artifact"])
    assert h7["status"] == "fail" and "E-POL-04" in h7["codes"], h7


def test_session_that_lost_the_run_is_not_logged(world: World) -> None:
    run_id = start_run(world)
    next_action(world, run_id)
    bash = {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": "ls"}}
    hook(world, "pre-tool", bash)
    before = len(_log(world, run_id))
    assert before >= 1

    def other(st: dict[str, Any]) -> None:
        st["active_session"] = {
            "session_id": "sess-other",
            "host_hash": "h_0000",
            "since": st["updated_at"],
        }

    with world.using() as rt:
        RunStore(rt, Companion(world.companion), run_id).update(other)
    out, code = hook(world, "pre-tool", bash)
    assert (out, code) == ("", 0)
    assert len(_log(world, run_id)) == before
