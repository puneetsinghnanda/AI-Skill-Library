"""Runs are independent (HMS-5 rerun: the run read the earlier run's artifacts and feedback "as a
starting point" at every step, and reviewers read other tickets' runs).

- While a session holds a run, the hook refuses reading another run's files, even of the same
  ticket, its answers or questions, and any search whose scope takes in other runs.
- An artifact that names another run's file fails H1 (E-H1-06).
- data.prior_answers holds this run's answers only (tests/test_prior_answers.py)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from e2e_steps import hook, next_action, start_run
from helpers import World
from tsl.harness.gates import other_run_refs
from tsl.hooks.pre_tool import _other_run_bash
from tsl.schemas.registry import errors

RUN = "run_01JA0B3C4D5E6F7G8H9JKMNPQR"
OLD = "run_01J90B3C4D5E6F7G8H9JKMNPQR"


# --------------------------------------------------------------------------- H1 (E-H1-06)
def test_artifact_naming_another_run_is_found() -> None:
    text = (
        f"---\nrun_id: {RUN}\nclaims:\n  - {{id: C1, cites: [runs/{OLD}/ide-answers.md#a-01]}}\n"
        f"---\nAs in artifacts/HMS-5/{OLD}/split.md, and C:\\repo\\artifacts\\HMS-5\\"
        f"{OLD}\\design.md.\nOwn: artifacts/HMS-5/{RUN}/req.md and runs/{RUN}/ide-answers.md\n"
    )
    assert other_run_refs(text, RUN, []) == [
        f"runs/{OLD}/ide-answers.md",
        f"artifacts/HMS-5/{OLD}/split.md",
        f"artifacts/HMS-5/{OLD}/design.md",  # a Windows path; the full stop is not part of it
    ]


def test_declared_input_of_another_run_is_allowed() -> None:
    """status-report cites each run's state.json, which tsl gives it as inputs."""
    text = f"cites: [runs/{OLD}/state.json#key:status]"
    assert other_run_refs(text, RUN, [{"path": f"runs/{OLD}/state.json"}]) == []
    assert other_run_refs(text, RUN, []) == [f"runs/{OLD}/state.json"]


# -------------------------------------------------------------------------------- the hook
def _decide(world: World, tool: str, ti: dict[str, Any]) -> str:
    out, _ = hook(
        world, "pre-tool", {"hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": ti}
    )
    if not out.strip():
        return "allow"
    return str(json.loads(out)["hookSpecificOutput"]["permissionDecision"])


def test_bound_run_reads_only_its_own_runs_files(world: World) -> None:
    run_id = start_run(world)
    next_action(world, run_id)
    c = world.companion
    own_art = c / "artifacts" / "T-1" / run_id / "req.md"
    other_art = c / "artifacts" / "T-1" / OLD / "req.md"  # an earlier run of the same ticket
    other_tkt = c / "artifacts" / "T-9" / OLD / "split.md"
    assert _decide(world, "Read", {"file_path": str(own_art)}) == "allow"
    assert _decide(world, "Read", {"file_path": str(c / "runs" / run_id / "state.json")}) == "allow"
    assert (
        _decide(world, "Read", {"file_path": str(c / "context" / "intent-baseline.md")}) == "allow"
    )
    assert _decide(world, "Read", {"file_path": str(c / "tsl.yaml")}) == "allow"
    for p in (
        other_art,
        other_tkt,
        c / "runs" / OLD / "ide-answers.md",
        c / "runs" / OLD / "open-questions.md",
    ):
        assert _decide(world, "Read", {"file_path": str(p)}) == "deny", p
    # Searches whose scope takes in other runs.
    assert _decide(world, "Grep", {"pattern": "x"}) == "deny"  # the repo root
    assert _decide(world, "Grep", {"pattern": "x", "path": str(c / "artifacts")}) == "deny"
    assert _decide(world, "Grep", {"pattern": "x", "path": str(c / "artifacts" / "T-1")}) == "deny"
    assert _decide(world, "Glob", {"pattern": "runs/*/ide-answers.md"}) == "deny"
    assert _decide(world, "Glob", {"pattern": "**/*.md"}) == "deny"
    # Searches kept to this run or to context/.
    assert _decide(world, "Grep", {"pattern": "x", "path": str(c / "context")}) == "allow"
    assert _decide(world, "Grep", {"pattern": "x", "glob": "context/**/*.md"}) == "allow"
    assert _decide(world, "Glob", {"pattern": f"artifacts/T-1/{run_id}/*.md"}) == "allow"
    assert _decide(world, "Grep", {"pattern": "x", "path": str(c / "runs" / run_id)}) == "allow"
    # Each refusal is logged as an E-POL-06 deny, so the run record counts them (H7 skips them).
    log = c / "runs" / run_id / "tool-log.jsonl"
    entries = [json.loads(x) for x in log.read_text().splitlines()] if log.is_file() else []
    denies = [e for e in entries if e.get("decision") == "deny"]
    assert len(denies) == 9 and {e["code"] for e in denies} == {"E-POL-06"}, denies
    # Logged relative to the companion repo: the target never leaves it (tool-log.v1).
    assert other_tkt.relative_to(c).as_posix() in [e["target"] for e in denies]
    assert all(str(c) not in e["target"] for e in denies)
    assert all(errors("tool-log.v1", e) == [] for e in denies)


def test_outside_a_run_reads_are_not_limited(world: World) -> None:
    c = world.companion
    assert (
        _decide(world, "Read", {"file_path": str(c / "runs" / OLD / "ide-answers.md")}) == "allow"
    )
    assert _decide(world, "Grep", {"pattern": "x"}) == "allow"


def test_bash_naming_another_run_is_refused() -> None:
    assert _other_run_bash(f"cat artifacts/HMS-5/{OLD}/req.md", RUN)
    assert _other_run_bash(f"cd /c/x && cat runs/{OLD}/ide-answers.md", RUN)
    assert _other_run_bash("grep -r foo artifacts/HMS-5/", RUN)
    assert _other_run_bash("ls runs/*/state.json", RUN)
    assert _other_run_bash(f"cat artifacts/HMS-5/{RUN}/req.md", RUN) is None
    assert _other_run_bash(f"tsl state show {OLD} --json", RUN) is None
    assert _other_run_bash("echo two runs ok", RUN) is None


# ------------------------------------------------- status-report: the one exception (run states)
def test_status_report_declares_run_states() -> None:
    import yaml

    from tsl.orchestrator.skills import reads_run_states

    root = Path(__file__).resolve().parents[2] / "plugins" / "truminds" / "skills"
    meta = yaml.safe_load((root / "status-report" / "skill.yaml").read_text(encoding="utf-8"))
    assert reads_run_states(meta)
    design = yaml.safe_load((root / "design" / "skill.yaml").read_text(encoding="utf-8"))
    assert not reads_run_states(design)


def test_run_state_skill_cites_other_runs_state_only() -> None:
    text = f"cites: [runs/{OLD}/state.json#key:status, runs/{OLD}/ide-answers.md#a-01]"
    assert other_run_refs(text, RUN, [], run_states=True) == [f"runs/{OLD}/ide-answers.md"]
    assert other_run_refs(text, RUN, []) == [
        f"runs/{OLD}/state.json",
        f"runs/{OLD}/ide-answers.md",
    ]


def test_run_state_skill_reads_other_runs_state_only(world: World, monkeypatch: Any) -> None:
    import tsl.hooks.pre_tool as pt

    run_id = start_run(world)
    next_action(world, run_id)
    c = world.companion
    state = str(c / "runs" / OLD / "state.json")
    assert _decide(world, "Read", {"file_path": state}) == "deny"  # an ordinary step
    monkeypatch.setattr(pt, "_reads_run_states", lambda *_a: True)  # a status-report step
    assert _decide(world, "Read", {"file_path": state}) == "allow"
    assert _decide(world, "Glob", {"pattern": "runs/*/state.json"}) == "allow"
    assert _decide(world, "Read", {"file_path": str(c / "runs" / OLD / "ide-answers.md")}) == "deny"
    assert _decide(world, "Glob", {"pattern": "runs/*/ide-answers.md"}) == "deny"
    assert _decide(world, "Grep", {"pattern": "x", "path": str(c / "runs")}) == "deny"
