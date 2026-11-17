"""The `coverage` check kind against the checks.yaml files the plugin ships (SDD-03 §5.2)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from tsl.core.frontmatter import split
from tsl.core.jsonio import read_yaml
from tsl.harness.skillchecks import CheckEnv, run_declared
from tsl.schemas.registry import errors as schema_errors

ROOT = Path(__file__).resolve().parents[2]
SKILLS = ROOT / "plugins" / "truminds" / "skills"


def _checks(skill: str) -> dict[str, Any]:
    return dict(read_yaml(SKILLS / skill / "checks.yaml"))


def _outcome(
    skill: str,
    check_id: str,
    front: dict[str, Any],
    root: Path = ROOT,
    inputs: dict[str, str] | None = None,
) -> Any:
    doc = _checks(skill)
    doc["checks"] = [c for c in doc["checks"] if c["id"] == check_id]
    assert doc["checks"], f"{check_id} not declared"
    env = CheckEnv(front, "", root, list((inputs or {}).values()), {}, dict(inputs or {}))
    [out] = run_declared(env, doc)
    return out


def _write_input(root: Path, rel: str, front: dict[str, Any]) -> str:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f"---\n{yaml.safe_dump(front, sort_keys=False)}---\n\n# Input\n", encoding="utf-8")
    return rel


def _story(sid: str, trace: list[str]) -> dict[str, Any]:
    ac = {"id": "AC1", "text": "Given a user, when they log in, then they see the dashboard"}
    return {"id": sid, "title": f"Story {sid}", "trace": trace, "acceptance_criteria": [ac]}


def test_story_split_trace_passes_when_every_req_is_traced_by_a_story() -> None:
    front = {"schema": "stories.v1", "trace": ["REQ-1"], "stories": [_story("S-1", ["REQ-1"])]}
    out = _outcome("story-split", "story-split.trace-req", front)
    assert (out.gate, out.status) == ("H5", "pass"), out.detail


def test_story_split_trace_passes_for_a_schema_valid_stories_artifact() -> None:
    # A real stories.v1 artifact the plugin ships as an eval input, not a hand-built dict.
    art = SKILLS / "test-plan" / "evals" / "cases" / "EC-01" / "inputs" / "stories.md"
    front = dict(split(art.read_text(encoding="utf-8")).front)
    assert schema_errors("stories.v1", front) == []
    out = _outcome("story-split", "story-split.trace-req", front)
    assert (out.gate, out.status) == ("H5", "pass"), out.detail


def test_story_split_trace_counts_reqs_traced_by_several_stories() -> None:
    front = {
        "schema": "stories.v1",
        "trace": ["REQ-1", "REQ-2"],
        "stories": [_story("S-1", ["REQ-1"]), _story("S-2", ["REQ-1", "REQ-2"])],
    }
    assert _outcome("story-split", "story-split.trace-req", front).status == "pass"


def test_story_split_trace_fails_for_a_req_no_story_traces() -> None:
    front = {
        "schema": "stories.v1",
        "trace": ["REQ-1", "REQ-2"],
        "stories": [_story("S-1", ["REQ-1"])],
    }
    out = _outcome("story-split", "story-split.trace-req", front)
    assert out.status == "fail"
    assert out.detail == "REQ-2 covered fewer than 1 times"


def _threats(*components: str) -> list[dict[str, Any]]:
    return [
        {
            "id": f"T-{n}",
            "component": c,
            "stride": "tampering",
            "threat": "Request body altered in transit",
            "mitigation": "TLS and signed payloads",
        }
        for n, c in enumerate(components, 1)
    ]


def _design(root: Path, *components: str) -> dict[str, str]:
    comps = [{"name": c, "module": f"src/{c.lower()}", "change": "new"} for c in components]
    return {
        "design": _write_input(root, "in/design.md", {"schema": "design.v1", "components": comps})
    }


def test_threat_model_passes_when_every_design_component_has_a_threat(tmp_path: Path) -> None:
    inputs = _design(tmp_path, "NotesRoute", "NotesService")
    front = {"schema": "threat-model.v1", "threats": _threats("NotesRoute", "NotesService")}
    out = _outcome("threat-model", "threat-model.stride-per-component", front, tmp_path, inputs)
    assert (out.gate, out.status) == ("H2", "pass"), out.detail


def test_threat_model_fails_for_a_design_component_without_a_threat(tmp_path: Path) -> None:
    inputs = _design(tmp_path, "NotesRoute", "NotesService")
    front = {"schema": "threat-model.v1", "threats": _threats("NotesRoute")}
    out = _outcome("threat-model", "threat-model.stride-per-component", front, tmp_path, inputs)
    assert (out.status, out.detail) == ("fail", "NotesService covered fewer than 1 times")


def test_threat_model_fails_when_the_design_input_is_missing(tmp_path: Path) -> None:
    # The old check read $.inputs.design, found nothing and passed; a missing input must fail.
    front = {"schema": "threat-model.v1", "threats": _threats("NotesRoute")}
    out = _outcome("threat-model", "threat-model.stride-per-component", front, tmp_path, {})
    assert out.status == "fail"
    assert "input design" in out.detail


def _tests(*covers: list[str]) -> list[dict[str, Any]]:
    return [
        {"id": f"TP-{n}", "title": f"Test {n}", "covers": c, "level": "unit"}
        for n, c in enumerate(covers, 1)
    ]


def _stories_input(root: Path) -> dict[str, str]:
    s1 = _story("S-1", ["REQ-1"])
    s1["acceptance_criteria"] = [dict(s1["acceptance_criteria"][0], id=f"AC{n}") for n in (1, 2)]
    front = {"schema": "stories.v1", "trace": ["REQ-1"], "stories": [s1, _story("S-2", ["REQ-1"])]}
    return {"stories": _write_input(root, "in/stories.md", front)}


def test_test_plan_passes_when_every_acceptance_criterion_is_tested(tmp_path: Path) -> None:
    inputs = _stories_input(tmp_path)
    front = {"schema": "test-plan.v1", "tests": _tests(["S-1/AC1"], ["S-1/AC2", "S-2/AC1"])}
    out = _outcome("test-plan", "test-plan.every-ac-tested", front, tmp_path, inputs)
    assert (out.gate, out.status) == ("H2", "pass"), out.detail


def test_test_plan_fails_for_an_untested_acceptance_criterion(tmp_path: Path) -> None:
    inputs = _stories_input(tmp_path)
    front = {"schema": "test-plan.v1", "tests": _tests(["S-1/AC1"], ["S-2/AC1"])}
    out = _outcome("test-plan", "test-plan.every-ac-tested", front, tmp_path, inputs)
    assert (out.status, out.detail) == ("fail", "S-1/AC2 covered fewer than 1 times")


def test_test_plan_fails_when_the_stories_input_is_missing(tmp_path: Path) -> None:
    front = {"schema": "test-plan.v1", "tests": _tests(["S-1/AC1"])}
    out = _outcome("test-plan", "test-plan.every-ac-tested", front, tmp_path, {})
    assert out.status == "fail"
    assert "input stories" in out.detail


def _plan_input(root: Path) -> dict[str, str]:
    """TP-1 unit S-1/AC1, TP-2 integration S-1/AC2 + S-2/AC1, TP-3 manual S-3/AC1 (not automated)."""
    tests = _tests(["S-1/AC1"], ["S-1/AC2", "S-2/AC1"], ["S-3/AC1"])
    tests[1]["level"], tests[2]["level"] = "integration", "manual"
    return {
        "test_plan": _write_input(root, "in/tplan.md", {"schema": "test-plan.v1", "tests": tests})
    }


def _results(*covers: list[str]) -> dict[str, Any]:
    results = [
        {"test_id": f"TP-{n}", "covers": c, "status": "pass"} for n, c in enumerate(covers, 1)
    ]
    return {"schema": "test-result.v1", "results": results}


def test_test_automation_results_link_every_automated_criterion(tmp_path: Path) -> None:
    front = _results(["S-1/AC1"], ["S-1/AC2", "S-2/AC1"])
    out = _outcome(
        "test-automation", "test-automation.results-linked", front, tmp_path, _plan_input(tmp_path)
    )
    assert (out.gate, out.status) == ("H2", "pass"), out.detail


def test_test_automation_fails_for_a_planned_criterion_no_result_links(tmp_path: Path) -> None:
    front = _results(["S-1/AC1"], ["S-1/AC2"])  # TP-2 dropped S-2/AC1 from its covers
    out = _outcome(
        "test-automation", "test-automation.results-linked", front, tmp_path, _plan_input(tmp_path)
    )
    assert (out.status, out.detail) == ("fail", "S-2/AC1 covered fewer than 1 times")


def test_test_automation_fails_when_a_planned_tests_criteria_have_no_result(tmp_path: Path) -> None:
    """TP-2 was never automated and no other result links its criteria. The check works per
    criterion, not per test id: a result that links TP-2's criteria under another id passes."""
    front = _results(["S-1/AC1"])
    out = _outcome(
        "test-automation", "test-automation.results-linked", front, tmp_path, _plan_input(tmp_path)
    )
    assert (out.status, out.detail) == ("fail", "S-1/AC2 covered fewer than 1 times")


def test_test_automation_fails_when_results_link_none_of_the_planned_criteria(
    tmp_path: Path,
) -> None:
    """Before #6 this passed: each result's covers were compared with every result's covers.
    It fails because the planned criteria are unlinked; an extra link to a criterion the plan
    lacks, next to complete links, is not detected (the coverage kind checks one direction)."""
    front = _results(["S-9/AC9"], ["S-9/AC8"])
    out = _outcome(
        "test-automation", "test-automation.results-linked", front, tmp_path, _plan_input(tmp_path)
    )
    assert out.status == "fail"


def test_test_automation_does_not_need_results_for_manual_tests(tmp_path: Path) -> None:
    front = _results(["S-1/AC1"], ["S-1/AC2", "S-2/AC1"])  # nothing for manual TP-3 (S-3/AC1)
    out = _outcome(
        "test-automation", "test-automation.results-linked", front, tmp_path, _plan_input(tmp_path)
    )
    assert out.status == "pass", out.detail


def test_test_automation_fails_when_the_test_plan_input_is_missing(tmp_path: Path) -> None:
    front = _results(["S-1/AC1"])
    out = _outcome("test-automation", "test-automation.results-linked", front, tmp_path, {})
    assert out.status == "fail"
    assert "input test_plan" in out.detail


def test_coverage_each_input_names_an_input_the_skill_declares() -> None:
    """A misspelt each_input would fail every run; tie it to skill.yaml."""
    for skill_dir in sorted(SKILLS.iterdir()):
        if not (skill_dir / "checks.yaml").is_file():
            continue
        declared = {i["name"] for i in read_yaml(skill_dir / "skill.yaml").get("inputs") or []}
        for c in _checks(skill_dir.name)["checks"]:
            if c.get("each_input"):
                assert c["each_input"] in declared, (c["id"], sorted(declared))
