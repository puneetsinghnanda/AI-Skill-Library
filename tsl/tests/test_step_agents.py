"""Step agents (HMS-6 pilot feedback, issue 4): each step runs as its own subagent with exactly
the skill's tools, tsl next names that agent, and a step cannot read another run's files."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from e2e_steps import do_req_step, hook, next_action, start_run
from helpers import World
from tsl.core.jsonio import read_yaml
from tsl.orchestrator import agents
from tsl.orchestrator.skills import installed

PLUGIN = Path(__file__).resolve().parents[2] / "plugins" / "truminds"


# --------------------------------------------------------------------------- generator
def test_shipped_step_agents_are_up_to_date() -> None:
    assert agents.stale(PLUGIN) == [], "run: python -m tsl.orchestrator.agents plugins/truminds"


def test_agent_tools_are_exactly_the_skill_tools() -> None:
    for sk in installed(PLUGIN).values():
        text = (PLUGIN / "agents" / f"step-{sk.id}.md").read_text(encoding="utf-8")
        line = next(x for x in text.splitlines() if x.startswith("tools: "))
        assert line[7:].split(", ") == [*sk.meta["allowed_tools"], "Bash(tsl verify *)"], sk.id


def test_a_changed_skill_makes_its_agent_stale(tmp_path: Path) -> None:
    plugin = tmp_path / "truminds"
    shutil.copytree(PLUGIN / "skills" / "design", plugin / "skills" / "design")
    assert agents.stale(plugin) == ["step-design.md"]  # missing
    agents.write(plugin)
    assert agents.stale(plugin) == []
    meta = plugin / "skills" / "design" / "skill.yaml"
    text = meta.read_text(encoding="utf-8").replace("- Write\n", "- Write\n- Edit\n")
    meta.write_text(text, encoding="utf-8")
    assert read_yaml(meta)["allowed_tools"][-1] == "Edit"
    assert agents.stale(plugin) == ["step-design.md"]  # tools changed
    (plugin / "agents" / "step-gone.md").write_text("x")
    assert "step-gone.md" in agents.stale(plugin)  # left over from a removed skill
    agents.write(plugin)
    assert agents.stale(plugin) == []
    assert not (plugin / "agents" / "step-gone.md").exists()


def test_agent_body_is_the_skill_without_its_preamble() -> None:
    sk = installed(PLUGIN)["design"]
    text = agents.render(sk)
    assert "tsl verify <artifact path> --inputs --json" in text
    assert "!`" not in text and "$0" not in text
    assert text.endswith((sk.dir / "SKILL.md").read_text(encoding="utf-8").split("\n## ", 1)[1])


# --------------------------------------------------------------------------- tsl next
def test_next_names_the_step_agent(world: World) -> None:
    run_id = start_run(world)
    _c, env = next_action(world, run_id)
    data = env["data"]
    assert data["action"] == "run_skill"
    assert data["agent"] == "truminds:step-" + data["skill"].split("@")[0]


# --------------------------------------------------------------------------- read scope
def _pre(w: World, tool: str, tool_input: dict[str, Any]) -> str | None:
    out, code = hook(w, "pre-tool", {"tool_name": tool, "tool_input": tool_input})
    assert code == 0
    if not out:
        return None
    hso = json.loads(out)["hookSpecificOutput"]
    assert hso["permissionDecision"] == "deny"
    return str(hso["permissionDecisionReason"])


def test_open_step_cannot_read_another_tickets_artifacts(world: World) -> None:
    run_id = start_run(world)
    art = do_req_step(world, run_id, until="written")["artifact"]
    other = world.companion / "artifacts" / "HMS-4" / "run_01JA0B3C4D5E6F7G8H9JKMNPQR"
    other.mkdir(parents=True)
    (other / "design.md").write_text("other ticket", encoding="utf-8")
    c = world.companion
    # another ticket's files, another run's records, and sweeping searches are refused
    for tool, ti in [
        ("Read", {"file_path": str(other / "design.md")}),
        ("Read", {"file_path": "artifacts/HMS-4/run_01JA0B3C4D5E6F7G8H9JKMNPQR/design.md"}),
        ("Read", {"file_path": str(c / "runs" / "run_01JA0B3C4D5E6F7G8H9JKMNPQR" / "state.json")}),
        ("Grep", {"pattern": "slot", "path": str(c / "artifacts")}),
        ("Grep", {"pattern": "slot"}),  # cwd is the companion root
        ("Glob", {"pattern": "**/design.md"}),
        ("Glob", {"pattern": "artifacts/HMS-4/**/*.md"}),
        ("Glob", {"pattern": "*.md", "path": str(c / "artifacts" / "ABC-142")}),
    ]:
        why = _pre(world, tool, ti)
        assert why is not None and "E-POL-07" in why, (tool, ti, why)
    # this run's files, the context pack and paths outside the companion stay readable
    for tool, ti in [
        ("Read", {"file_path": str(c / art)}),
        ("Read", {"file_path": str(c / "runs" / run_id / "state.json")}),
        ("Read", {"file_path": str(c / "context" / "manifest.json")}),
        ("Grep", {"pattern": "REQ", "path": str(c / "context")}),
        ("Glob", {"pattern": f"artifacts/ABC-142/{run_id}/*.md"}),
        ("Glob", {"pattern": "context/**/*.md"}),
        ("Read", {"file_path": str(world.plugin / "skills" / "story-split" / "SKILL.md")}),
    ]:
        assert _pre(world, tool, ti) is None, (tool, ti)


def test_reads_are_not_scoped_before_the_skill_launches(world: World) -> None:
    run_id = start_run(world)
    next_action(world, run_id)
    path = world.companion / "artifacts" / "HMS-4" / "x.md"
    assert _pre(world, "Read", {"file_path": str(path)}) is None
