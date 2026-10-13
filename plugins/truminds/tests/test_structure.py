"""Structural validation of the truminds plugin, its workflows and the pods (TST-01 §2.6, TC-PLG-001/003, TC-EVL-002).

These tests need no LLM and no network. They mirror the SKL-V, POD-V and E-WFL rules that `tsl validate` owns
(SDD-01 §14.1, SDD-10 §9, SDD-02 §3.5) so the plugin is checked even before `tsl` is installed.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import jmespath
import pytest
import yaml

from conftest import (
    PLUGIN,
    PODS,
    ROOT,
    SDD02,
    SKILLS,
    STATUS_RANK,
    body,
    errors,
    front_matter,
    load,
    pods,
    registry_command_skills,
    satisfies,
    schema_index,
    sdd01_catalogue,
    sdlc_skill_dirs,
    skill_meta,
    split_ref,
    workflows,
)

# Conflicts between design documents that the build follows literally and reports instead of working around.
# Each entry must stay true: a test fails when a conflict disappears, so the list never goes stale.
KNOWN_RANGE_CONFLICTS = {
    # SDD-02 §4 pins requirement-review@^1.2; SDD-01 §13.1 fixes the reference skill at 1.0.0.
    ("brownfield-change", "req"),
}
KNOWN_BINDING_CONFLICTS = {
    # SDD-02 §4 binds `baseline`; SDD-01 §13.1 names the input `intent_baseline`.
    ("brownfield-change", "req", "baseline"),
}
EXCLUDED_DIRS = {"tests", "__pycache__", ".pytest_cache", ".venv", ".ruff_cache"}
SDLC_HEADINGS = ["Job", "Inputs", "Rules", "Method", "Output", "If this is a retry", "Hand-over"]
PREAMBLE = (
    "Step context from tsl (do not edit):\n!`tsl verify $0 --inputs --json`\n\n"
    'If the JSON above has "ok": false, show its "message" and "next" to the user and stop. Write nothing.\n'
)
COMMAND_PREAMBLES = {
    "run": "!`tsl state start $0 $1 --json`",
    "resume": "!`tsl state resume $0 --json`",
    "status": "!`tsl state show $0 --json`",
    "eval": "!`tsl eval plan $0 --json`",
    "improve": "!`tsl improve plan $0 --json`",
    "context-draft": "!`tsl context draft-prepare $0 --json`",
}


def _files(*roots: Path) -> list[Path]:
    out = []
    for root in roots:
        for p in sorted(root.rglob("*")):
            if p.is_file() and not (EXCLUDED_DIRS & set(p.relative_to(root).parts)):
                out.append(p)
    return out


def _rel(p: Path) -> str:
    return str(p.relative_to(ROOT))


# ------------------------------------------------------------------------------------------ YAML vs schemas
SCHEMA_DOCS = [p for p in _files(PLUGIN, PODS) if p.suffix in (".yaml", ".yml", ".json", ".md")]


def _schema_of(p: Path) -> tuple[str | None, Any]:
    try:
        doc = load(p)
    except (yaml.YAMLError, json.JSONDecodeError) as e:
        pytest.fail(f"{_rel(p)} does not parse: {e}")
    if isinstance(doc, dict) and isinstance(doc.get("schema"), str):
        return doc["schema"], doc
    return None, doc


@pytest.mark.parametrize("path", SCHEMA_DOCS, ids=_rel)
def test_every_yaml_json_and_front_matter_validates_against_its_schema(path: Path) -> None:
    schema_id, doc = _schema_of(path)
    if schema_id is None:
        return
    assert schema_id in schema_index(), f"{_rel(path)} names unknown schema {schema_id}"
    errs = errors(schema_id, doc)
    assert not errs, f"{_rel(path)} is not valid {schema_id}: {errs[:5]}"


@pytest.mark.parametrize(
    ("pattern", "schema_id"),
    [
        ("skills/*/skill.yaml", "skill-metadata.v1"),
        ("skills/*/rubric.md", "rubric.v1"),
        ("skills/*/checks.yaml", "skill-checks.v1"),
        ("skills/*/evals/eval-set.yaml", "eval-set.v1"),
        ("skills/*/evals/cases/*/case.yaml", "eval-case.v1"),
        ("workflows/*.workflow.yaml", "workflow.v1"),
        ("policy/policy.yaml", "policy.v2"),
    ],
)
def test_contract_files_carry_the_right_schema(pattern: str, schema_id: str) -> None:
    files = sorted(PLUGIN.glob(pattern))
    assert files, pattern
    for f in files:
        doc = load(f)
        assert isinstance(doc, dict) and doc.get("schema") == schema_id, f"{_rel(f)} must declare schema {schema_id}"


def test_pods_carry_pod_schema() -> None:
    assert pods()
    for name, doc in pods().items():
        assert doc["schema"] == "pod.v1", name


# ------------------------------------------------------------------------------------------ plugin package
def test_plugin_and_marketplace_manifests() -> None:
    plugin = json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    market = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    assert plugin["name"] == "truminds"
    assert re.fullmatch(r"\d+\.\d+\.\d+", plugin["version"])
    assert market["name"] == "truminds-skill-library"
    entry = next(p for p in market["plugins"] if p["name"] == "truminds")
    assert (ROOT / entry["source"]).resolve() == PLUGIN.resolve()


def test_hooks_json_lists_exactly_the_sdd05_hooks_with_timeouts() -> None:
    hooks = json.loads((PLUGIN / "hooks" / "hooks.json").read_text(encoding="utf-8"))["hooks"]
    seen = []
    for event, groups in hooks.items():
        for g in groups:
            for h in g["hooks"]:
                assert h["type"] == "command"
                assert isinstance(h.get("timeout"), int) and h["timeout"] > 0
                m = re.fullmatch(r'"\$\{CLAUDE_PLUGIN_ROOT\}/bin/tsl-hook" ([a-z-]+)', h["command"])
                assert m, h["command"]
                seen.append((event, g.get("matcher"), m.group(1), h["timeout"]))
    assert sorted(seen, key=str) == sorted(
        [
            ("SessionStart", None, "session-start", 15),
            ("PreToolUse", "Write|Edit|NotebookEdit|Bash", "pre-tool", 10),
            ("PreToolUse", "mcp__.*", "pre-mcp", 10),
            ("PostToolUse", "Write|Edit|NotebookEdit", "post-write", 90),
            ("SessionEnd", None, "session-end", 15),
        ],
        key=str,
    )
    assert (PLUGIN / "bin" / "tsl-hook").stat().st_mode & 0o111, "bin/tsl-hook must be executable"
    assert (PLUGIN / "bin" / "tsl-hook.cmd").is_file()


def test_reviewer_agent_is_read_only_and_review_skill_forks() -> None:
    agent = front_matter(PLUGIN / "agents" / "reviewer.md")
    assert agent and agent["name"] == "reviewer"
    assert [t.strip() for t in agent["tools"].split(",")] == ["Read", "Grep", "Glob"]
    review = front_matter(SKILLS / "review" / "SKILL.md")
    assert review == {
        "name": "review",
        "description": "Harness review step for one artifact. Used by truminds workflows only.",
        "context": "fork",
        "agent": "truminds:reviewer",
        "user-invocable": False,
    }
    assert "!`tsl review prepare $ARGUMENTS --json`" in body(SKILLS / "review" / "SKILL.md")


def test_every_skill_folder_is_a_command_the_review_step_or_an_sdlc_skill() -> None:
    commands = set(registry_command_skills().values())
    for d in sorted(p for p in SKILLS.iterdir() if p.is_dir()):
        assert (d / "SKILL.md").is_file(), d.name
        assert d.name in commands or d.name == "review" or (d / "skill.yaml").is_file(), d.name


# ------------------------------------------------------------------------------------------ command skills
@pytest.mark.parametrize("folder", sorted(set(registry_command_skills().values())))
def test_command_skill_frontmatter_and_preamble(folder: str) -> None:
    path = SKILLS / folder / "SKILL.md"
    assert path.is_file(), f"registry §3.2 lists skills/{folder}"
    fm = front_matter(path)
    assert fm is not None
    assert fm["name"] == folder
    assert fm["disable-model-invocation"] is True, "command skills never start on their own (SDD-05 §4.1)"
    assert fm["description"].endswith(f"Only when the user types /truminds:{folder}.")
    assert fm.get("argument-hint")
    assert fm["allowed-tools"].startswith("Bash(tsl *)")
    assert "user-invocable" not in fm or fm["user-invocable"] is True
    lines = [ln for ln in body(path).splitlines() if ln.strip()]
    assert lines[1] == COMMAND_PREAMBLES[folder], "the tsl call is the first thing the skill does (SDD-05 §4.1)"


def test_sdlc_skills_never_disable_model_invocation() -> None:
    for d in sdlc_skill_dirs():
        fm = front_matter(d / "SKILL.md")
        assert fm is not None and "disable-model-invocation" not in fm, d.name


# ------------------------------------------------------------------------------------------ SDLC skills
SKILL_IDS = [d.name for d in sdlc_skill_dirs()]


def test_release1_catalogue_is_complete() -> None:
    cat = sdd01_catalogue()
    assert len(cat) == 17
    assert sorted(r["id"] for r in cat) == sorted(SKILL_IDS)
    roles = {
        "Business Analyst": "business-analyst",
        "Solution Architect": "solution-architect",
        "Developer": "developer",
        "QA Engineer": "qa-engineer",
        "Security": "security",
        "DevOps": "devops",
        "UX Designer": "ux-designer",
        "Delivery Manager": "delivery-manager",
    }
    for row in cat:
        meta = skill_meta()[row["id"]]
        assert meta["agent"] == roles[row["role"]], row["id"]
        assert meta["phase"] == row["phase"], row["id"]
        assert meta["title"] == row["title"], row["id"]
        expected = (
            "draft" if row["id"] == "requirement-review" else row["target"]
        )  # SDD-01 §13.1 keeps the reference at draft
        assert meta["status"] == expected, row["id"]
        assert f"Skill code: {row['code']}" in (SKILLS / row["id"] / "skill.yaml").read_text(encoding="utf-8")


@pytest.mark.parametrize("skill", SKILL_IDS)
def test_sdlc_skill_md_follows_the_sdd01_template(skill: str) -> None:
    d = SKILLS / skill
    fm = front_matter(d / "SKILL.md")
    meta = skill_meta()[skill]
    assert fm is not None
    assert set(fm) == {"name", "description", "argument-hint", "user-invocable", "allowed-tools"}
    assert fm["name"] == skill == meta["id"]  # SKL-V01
    assert len(fm["description"]) <= 1024
    assert fm["description"].endswith(
        f"Use only as a step of a Truminds workflow run, when tsl names {skill} as the next step."
    )
    assert fm["argument-hint"] == "<artifact path from tsl next>"
    assert fm["user-invocable"] is False
    tools = [t.strip() for t in fm["allowed-tools"].split(",")]
    assert tools == ["Bash(tsl verify *)", *meta["allowed_tools"]]  # SKL-V09
    text = body(d / "SKILL.md")
    assert text.lstrip("\n").startswith(PREAMBLE), "SKL-V04: the preamble is the first body content"
    # The Output section shows the artifact skeleton, whose own "## Summary ..." lines are not template headings.
    headings = [h for h in re.findall(r"^## (.+)$", text, re.M) if h in SDLC_HEADINGS]
    assert headings == SDLC_HEADINGS, "SKL-V05"
    assert len(text.splitlines()) <= 500


@pytest.mark.parametrize("skill", SKILL_IDS)
def test_skill_folder_files(skill: str) -> None:
    d = SKILLS / skill
    meta = skill_meta()[skill]
    for f in ("SKILL.md", "skill.yaml", meta["rubric"], meta["checks"], "CHANGELOG.md", "evals/eval-set.yaml"):
        assert (d / f).is_file(), f"{skill}/{f}"
    assert f"## {meta['version']}" in (d / "CHANGELOG.md").read_text(encoding="utf-8")
    rubric = front_matter(d / meta["rubric"])
    assert rubric is not None and rubric["skill"] == skill
    assert abs(sum(c["weight"] for c in rubric["criteria"]) - 1.0) <= 0.001, "SKL-V07"
    code = re.search(r"Skill code: ([A-Z]{2,3})", (d / "skill.yaml").read_text(encoding="utf-8"))
    assert code
    assert all(c["id"].startswith(code.group(1) + "-R") for c in rubric["criteria"])
    checks = yaml.safe_load((d / meta["checks"]).read_text(encoding="utf-8"))
    assert checks["skill"] == skill
    assert checks["artifact_schema"] == next(
        o["schema"] for o in meta["outputs"] if o.get("kind", "artifact") == "artifact"
    )
    ids = [c["id"] for c in checks["checks"]]
    assert len(ids) == len(set(ids))
    for c in checks["checks"]:
        assert c["id"].startswith(code.group(1) + "-C") or c["id"].startswith(skill + "."), c["id"]
        terms = (c.get("with") or {}).get("terms_file")
        if terms:
            assert (d / terms).is_file()
    artifact_outputs = [o for o in meta["outputs"] if o.get("kind", "artifact") == "artifact"]
    assert len(artifact_outputs) == 1, "SDD-01 §5.2: exactly one artifact output"
    if any(o.get("kind") == "code" for o in meta["outputs"]):
        assert meta["change_limits"], "code skills declare change limits (DEF-05)"
    else:
        assert "Edit" not in meta["allowed_tools"] and not any(t.startswith("Bash") for t in meta["allowed_tools"])


def test_every_artifact_input_schema_is_produced_by_some_skill() -> None:  # SKL-V11, FR-REG-02
    produced = {o["schema"] for m in skill_meta().values() for o in m["outputs"] if "schema" in o}
    for skill, meta in skill_meta().items():
        for i in meta["inputs"]:
            if i["source"] == "artifact":
                assert i["schema"] in produced, f"{skill}.{i['name']}"


# ------------------------------------------------------------------------------------------ evals
def _cases(skill: str) -> list[Path]:
    return sorted((SKILLS / skill / "evals" / "cases").glob("*/case.yaml"))


@pytest.mark.parametrize("skill", SKILL_IDS)
def test_eval_cases_and_every_referenced_file_exist(skill: str) -> None:
    meta = skill_meta()[skill]
    eval_set = yaml.safe_load((SKILLS / skill / "evals" / "eval-set.yaml").read_text(encoding="utf-8"))
    assert eval_set["skill"] == skill
    cases = _cases(skill)
    minimum = 10 if skill == "requirement-review" else 3
    assert len(cases) >= minimum
    input_names = {i["name"] for i in meta["inputs"]}
    for c in cases:
        doc = yaml.safe_load(c.read_text(encoding="utf-8"))
        assert doc["id"] == c.parent.name
        for name, rel in doc["inputs"].items():
            assert name in input_names, f"{_rel(c)}: input {name} is not declared in skill.yaml"
            assert (c.parent / rel).exists(), f"{_rel(c)} references missing {rel}"
        for name in (
            i["name"] for i in meta["inputs"] if i.get("required", True) and i["source"] in ("run", "artifact")
        ):
            assert name in doc["inputs"], f"{_rel(c)} lacks required input {name}"
        for a in doc["expect"].get("assert", []):
            jmespath.compile(a["path"])
            for key in ("any_matches", "none_matches"):
                if key in a:
                    re.compile(a[key])


def test_requirement_review_eval_set_matches_sdd01_13_6() -> None:
    cases = {
        yaml.safe_load(c.read_text(encoding="utf-8"))["id"]: yaml.safe_load(c.read_text(encoding="utf-8"))
        for c in _cases("requirement-review")
    }
    assert sorted(cases) == [f"EC-{n:02d}" for n in range(1, 11)]
    kinds = {k: v["kind"] for k, v in cases.items()}
    assert kinds == {
        "EC-01": "normal",
        "EC-02": "normal",
        "EC-03": "conflict",
        "EC-04": "edge",
        "EC-05": "edge",
        "EC-06": "adversarial",
        "EC-07": "forbidden-content",
        "EC-08": "normal",
        "EC-09": "normal",
        "EC-10": "normal",
    }
    outcomes = {k: v["expect"]["outcome_in"] for k, v in cases.items()}
    assert (
        outcomes["EC-01"] == ["PASS"] and outcomes["EC-03"] == ["NEEDS-INPUT"] and outcomes["EC-05"] == ["NEEDS-INPUT"]
    )
    assert outcomes["EC-09"] == ["PASS-WITH-FINDINGS"]
    # SDD-01 §10.3 mix: 4 normal, 2 edge, 1 conflict, 1 adversarial, 1 forbidden-content
    counts = {k: list(kinds.values()).count(k) for k in set(kinds.values())}
    assert counts["normal"] >= 4 and counts["edge"] >= 2 and counts["conflict"] >= 1
    assert counts["adversarial"] >= 1 and counts["forbidden-content"] >= 1
    domains = {
        c.parent.name: (c.parent / "inputs" / "intent-baseline.md").read_text(encoding="utf-8")
        for c in _cases("requirement-review")
    }
    assert "sample-support" in domains["EC-08"] and "sample-library" in domains["EC-10"], (
        "domain-agnostic proof (SDD-01 §13.6)"
    )


def test_requirement_review_examples_are_labelled() -> None:
    ex = SKILLS / "requirement-review" / "examples"
    assert (ex / "good" / "intent.md").is_file()
    labels = {}
    for p in sorted((ex / "bad").glob("*.md")):
        m = re.search(r"<!-- expect_fail: \[([A-Z0-9, ]+)\] -->", body(p))
        assert m, p.name
        labels[p.name] = m.group(1)
    assert labels == {"missing-unknown.md": "H2", "invented-value.md": "H4"}
    assert "## Unknown" not in body(ex / "bad" / "missing-unknown.md")


# ------------------------------------------------------------------------------------------ workflows
DOC3_WORKFLOWS = {"brownfield-change", "greenfield-feature", "defect-fix", "ux-review", "estimate"}


def test_doc3_release1_workflows_exist() -> None:  # RD-6 default: Doc 3 names
    assert set(workflows()) >= DOC3_WORKFLOWS
    for name, wf in workflows().items():
        assert wf["id"] == name


def test_brownfield_change_matches_sdd02_exactly() -> None:
    text = SDD02.read_text(encoding="utf-8")
    section = text[text.index("## 4. The worked example") :]
    block = section[section.index("```yaml\n") + 8 : section.index("```", section.index("```yaml\n") + 8)]
    expected = yaml.safe_load(block)
    actual = dict(workflows()["brownfield-change"])
    assert actual.pop("status") in ("draft", "pilot", "production")  # registry §10 row 24 added `status`
    assert actual == expected


def _skill_steps(wf: dict[str, Any]) -> list[dict[str, Any]]:
    return [s for s in wf["steps"] if "skill" in s]


def _node(s: dict[str, Any]) -> str:
    return s.get("id") or s.get("gate") or "pr"


def _ancestors(wf: dict[str, Any], node: str) -> set[str]:
    deps = {_node(s): set(s.get("after", [])) for s in wf["steps"]}
    seen: set[str] = set()
    stack = list(deps.get(node, ()))
    while stack:
        n = stack.pop()
        if n not in seen:
            seen.add(n)
            stack.extend(deps.get(n, ()))
    return seen


@pytest.mark.parametrize("name", sorted(workflows()))
def test_workflow_skill_refs_resolve(name: str) -> None:
    wf = workflows()[name]
    unresolved = set()
    for s in _skill_steps(wf):
        skill, rng = split_ref(s["skill"])
        assert skill in skill_meta(), f"{name}.{s['id']}: skill {skill} does not exist"
        if not satisfies(skill_meta()[skill]["version"], rng):
            unresolved.add((name, s["id"]))
    known = {k for k in KNOWN_RANGE_CONFLICTS if k[0] == name}
    assert unresolved == known, (
        f"E-WFL-04 ranges that do not resolve: {unresolved - known}; stale known conflicts: {known - unresolved}"
    )


@pytest.mark.parametrize("name", sorted(workflows()))
def test_workflow_graph_is_valid(name: str) -> None:  # E-WFL-02
    wf = workflows()[name]
    nodes = [_node(s) for s in wf["steps"]]
    assert len(nodes) == len(set(nodes)), "ids unique"
    for s in wf["steps"]:
        for dep in s.get("after", []):
            assert dep in nodes and nodes.index(dep) < nodes.index(_node(s)), f"{_node(s)} after {dep}"
    roots = [n for n, s in zip(nodes, wf["steps"], strict=True) if not s.get("after")]
    assert roots, "at least one first step"
    for s in wf["steps"]:
        if "gate" in s:
            anc = _ancestors(wf, s["gate"])
            assert s["on_reject"] == "abort" or s["on_reject"] in anc, f"{s['gate']} on_reject upstream"
            if "on_changes" in s:
                assert s["on_changes"] in anc
            for a in s.get("artifacts", []):
                assert a in anc
    prs = [s for s in wf["steps"] if s.get("pr")]
    if prs:
        assert wf["steps"][-1] is prs[0] and len(prs) == 1, "pr is last"
    if wf["kind"] == "read_only":
        assert not prs
        for s in _skill_steps(wf):
            meta = skill_meta()[split_ref(s["skill"])[0]]
            assert not any(o.get("kind") == "code" for o in meta["outputs"]), "read_only has no code-editing skill"


@pytest.mark.parametrize("name", sorted(workflows()))
def test_workflow_input_bindings(name: str) -> None:  # E-WFL-03
    wf = workflows()[name]
    by_id = {s["id"]: s for s in _skill_steps(wf)}
    problems = []
    for s in _skill_steps(wf):
        meta = skill_meta()[split_ref(s["skill"])[0]]
        declared = {i["name"]: i for i in meta["inputs"]}
        binds = s.get("inputs", {})
        for bname, target in binds.items():
            if bname not in declared:
                if (name, s["id"], bname) not in KNOWN_BINDING_CONFLICTS:
                    problems.append(f"{s['id']}.{bname} is not an input of {meta['id']}")
                continue
            inp = declared[bname]
            if target == "run.ticket":
                ok = inp["source"] == "run" and inp.get("schema") == "ticket-snapshot.v1"
            elif target.startswith("context."):
                ok = (
                    inp["source"] == "context"
                    and inp["path"].removeprefix("context/").removesuffix(".md") == target[8:]
                )
            else:
                step, _, out = target.partition(".")
                producer = by_id.get(step)
                ok = producer is not None and step in _ancestors(wf, s["id"])
                if ok:
                    pmeta = skill_meta()[split_ref(producer["skill"])[0]]
                    outs = {o["name"]: o for o in pmeta["outputs"]}
                    ok = out in outs and outs[out].get("schema") == inp.get("schema")
            if not ok:
                problems.append(f"{s['id']}.{bname} -> {target}")
        for i in meta["inputs"]:
            if i.get("required", True) and i["source"] in ("artifact", "run") and i["name"] not in binds:
                problems.append(f"{s['id']}: required input {i['name']} unbound")
    assert not problems, problems
    for k in KNOWN_BINDING_CONFLICTS:
        if k[0] == name:
            step = by_id[k[1]]
            assert k[2] in step.get("inputs", {}), f"known conflict {k} no longer present"


@pytest.mark.parametrize("name", sorted(workflows()))
def test_workflow_status_not_above_its_skills(name: str) -> None:  # SDD-01 §7
    wf = workflows()[name]
    lowest = min(STATUS_RANK[skill_meta()[split_ref(s["skill"])[0]]["status"]] for s in _skill_steps(wf))
    assert STATUS_RANK[wf["status"]] <= lowest


# ------------------------------------------------------------------------------------------ pods
@pytest.mark.parametrize("pod_id", sorted(pods()))
def test_pod_references_existing_skills_and_workflows(pod_id: str) -> None:
    pod = pods()[pod_id]
    folder = PODS / pod_id
    assert pod["id"] == pod_id  # POD-V01
    assert (folder / pod["one_pager"]).is_file() and (folder / "CHANGELOG.md").is_file()  # POD-V11
    keys = [a["key"] for a in pod["agents"]]
    assert len(keys) == len(set(keys)) and 1 <= len(keys) <= 8  # POD-V10
    assigned: set[str] = set()
    statuses = [STATUS_RANK[pod["status"]]]
    for agent in pod["agents"]:
        cross = {c["skill"] for c in agent.get("cross_role_skills", [])}
        for ref in agent["skills"]:
            skill, rng = split_ref(ref)
            assert skill in skill_meta(), f"POD-V03 {ref}"
            meta = skill_meta()[skill]
            assert meta["status"] != "deprecated" and satisfies(meta["version"], rng), f"POD-V03 {ref}"
            assigned.add(skill)
            statuses.append(STATUS_RANK[meta["status"]])
            if meta["agent"] != agent["role"]:
                assert skill in cross, f"POD-V08 {skill} on {agent['key']}"
    gates: set[str] = set()
    for ref in pod["workflows"]:
        wid, rng = split_ref(ref)
        assert wid in workflows(), f"POD-V04 {ref}"
        wf = workflows()[wid]
        assert satisfies(wf["version"], rng), f"POD-V04 {ref}"
        statuses.append(STATUS_RANK[wf["status"]])
        for s in wf["steps"]:
            if "skill" in s:
                assert split_ref(s["skill"])[0] in assigned, f"POD-V05 {s['skill']} in {wid}"
            if "gate" in s:
                gates.add(s["gate"])
    assert STATUS_RANK[pod["status"]] <= min(statuses[1:]), "POD-V07"
    people_gates = {g for p in pod["people"] for g in p.get("gates", [])}
    assert any(p.get("platform_role") == "tech_lead" for p in pod["people"]), "POD-V09"
    assert gates <= people_gates and "escalate" in people_gates, "POD-V09"
    text = (folder / "pod.yaml").read_text(encoding="utf-8") + (folder / pod["one_pager"]).read_text(encoding="utf-8")
    assert not re.search(r"\d+ ?%|\d+ PRs", text), "POD-V12: no hand-written metrics"


# ------------------------------------------------------------------------------------------ versions
def _tsl_version() -> str | None:
    exe = shutil.which("tsl")
    if exe:
        out = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=30, check=False).stdout
        m = re.match(r"tsl\s+(\S+)", out)
        return m.group(1) if m else ""
    init = ROOT / "tsl" / "src" / "tsl" / "__init__.py"
    if init.is_file():
        m = re.search(r'__version__\s*=\s*"([^"]+)"', init.read_text(encoding="utf-8"))
        return m.group(1) if m else ""
    return None


def test_plugin_version_equals_tsl_version() -> None:  # TC-PLG-003, SDD-05 §7.1
    tv = _tsl_version()
    if tv is None:
        pytest.skip("tsl is not installed and tsl/src/tsl/__init__.py does not exist yet")
    plugin = json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    assert tv == plugin["version"]


# ------------------------------------------------------------------------------------------ spikes
SPIKES = ROOT / "spikes"


def test_spike_runbooks_cover_every_registry_spike() -> None:
    readme = (SPIKES / "README.md").read_text(encoding="utf-8")
    sections = re.split(r"^## (?=S-\d\d )", readme, flags=re.M)
    found = {s[:4]: s for s in sections if re.match(r"S-\d\d ", s)}
    assert sorted(found) == [f"S-{n:02d}" for n in range(1, 16)]  # registry §9: S-01 to S-15
    for sid, text in found.items():
        assert "**Steps**" in text and "**Expected observation:**" in text, sid
        assert re.search(r"^\| Run \|.*\n\| --- \|", text, re.M), f"{sid} needs a results table"


def test_spike_plugin_is_separate_and_wired() -> None:
    market = json.loads((SPIKES / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    assert market["name"] != "truminds-skill-library"
    plugin_dir = SPIKES / market["plugins"][0]["source"]
    manifest = json.loads((plugin_dir / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    assert manifest["name"] == "tsl-spike"
    hooks = json.loads((plugin_dir / "hooks" / "hooks.json").read_text(encoding="utf-8"))["hooks"]
    for groups in hooks.values():
        for g in groups:
            for h in g["hooks"]:
                m = re.match(r'"\$\{CLAUDE_PLUGIN_ROOT\}/(bin/[a-z-]+)"', h["command"])
                assert m, h["command"]
                script = plugin_dir / m.group(1)
                assert script.is_file() and script.stat().st_mode & 0o111, script
    for skill in ("run", "demo-step", "review", "env-probe"):
        assert front_matter(plugin_dir / "skills" / skill / "SKILL.md"), skill
