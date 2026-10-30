"""Step agents: one subagent definition per step skill, generated from skill.yaml and SKILL.md.

Each workflow step runs as a fresh subagent whose tools are exactly the skill's allowed-tools
(allowed_tools + Bash(tsl verify *), the SKL-V09 set), so the main session only dispatches
and never carries a step's reading. The files live in plugins/truminds/agents/step-<id>.md and
are never edited by hand: `python -m tsl.orchestrator.agents <plugin>` writes them and
`--check` fails when one is stale. See docs/design/step-agents.md.
"""

from __future__ import annotations

import sys
from pathlib import Path

from tsl.core.frontmatter import split
from tsl.orchestrator.skills import Skill, installed

PREFIX = "step-"
VERIFY_TOOL = "Bash(tsl verify *)"


def agent_name(skill_id: str) -> str:
    return f"{PREFIX}{skill_id}"


def agent_ref(skill_id: str) -> str:
    """The subagent_type the run loop passes to the Agent tool."""
    return f"truminds:{agent_name(skill_id)}"


def agent_tools(sk: Skill) -> list[str]:
    return [*sk.allowed_tools, VERIFY_TOOL]


def _skill_body(sk: Skill) -> str:
    """SKILL.md from its first `## ` heading: the preamble's job moves to the agent header."""
    body = split((sk.dir / "SKILL.md").read_text(encoding="utf-8")).body
    at = body.find("\n## ")
    return body[at + 1 :].rstrip() + "\n" if at >= 0 else body.strip() + "\n"


def render(sk: Skill) -> str:
    title = str(sk.meta.get("title") or sk.id)
    return (
        "---\n"
        f"name: {agent_name(sk.id)}\n"
        f"description: Truminds workflow step {sk.id} ({title}). Runs one attempt of the "
        f"{sk.id} skill and writes only the artifact tsl names. Use only when tsl next names "
        f"{agent_ref(sk.id)}.\n"
        f"tools: {', '.join(agent_tools(sk))}\n"
        "model: inherit\n"
        "---\n"
        f"<!-- Generated from skills/{sk.id}/skill.yaml ({sk.ref}) and SKILL.md by\n"
        "     `python -m tsl.orchestrator.agents`. Do not edit; edit the skill. -->\n"
        f"You run one attempt of one Truminds workflow step: skill {sk.ref}.\n"
        "Your prompt gives the step's artifact path. Before anything else run\n"
        "`tsl verify <artifact path> --inputs --json`. Its JSON is the step context: below,\n"
        '"the JSON above" and data.* mean that JSON. If it has "ok": false, reply with its\n'
        '"message" and "next" and stop. Write nothing.\n\n'
        "Read only the data.inputs paths, the data.context sections and the product repos.\n"
        "Never read another ticket's or another run's files under artifacts/ or runs/; the\n"
        "pre-tool hook refuses them (E-POL-07).\n\n"
        "When the file is written, reply with one line: the path you wrote. The run loop runs\n"
        "the checks, the review and the decision.\n\n" + _skill_body(sk)
    )


def expected(plugin_root: Path) -> dict[Path, str]:
    out = plugin_root / "agents"
    return {out / f"{agent_name(sk.id)}.md": render(sk) for sk in installed(plugin_root).values()}


def stale(plugin_root: Path) -> list[str]:
    """Agent files that are missing, out of date, or left over from a removed skill."""
    want = expected(plugin_root)
    bad = [
        p.name
        for p, text in want.items()
        if not p.is_file() or p.read_text(encoding="utf-8").replace("\r\n", "\n") != text
    ]
    have = (plugin_root / "agents").glob(f"{PREFIX}*.md")
    bad += [p.name for p in have if p not in want]
    return sorted(bad)


def write(plugin_root: Path) -> list[str]:
    want = expected(plugin_root)
    (plugin_root / "agents").mkdir(exist_ok=True)
    for p in (plugin_root / "agents").glob(f"{PREFIX}*.md"):
        if p not in want:
            p.unlink()
    for p, text in want.items():
        p.write_text(text, encoding="utf-8", newline="\n")
    return sorted(p.name for p in want)


def main(argv: list[str]) -> int:
    check = "--check" in argv
    args = [a for a in argv if a != "--check"]
    root = Path(args[0]) if args else Path("plugins/truminds")
    if check:
        bad = stale(root)
        for name in bad:
            sys.stderr.write(f"stale step agent: agents/{name}\n")
        return 1 if bad else 0
    for name in write(root):
        sys.stdout.write(f"agents/{name}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
