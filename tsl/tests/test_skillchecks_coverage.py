"""The `coverage` check kind against the checks.yaml files the plugin ships (SDD-03 §5.2)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from tsl.core.frontmatter import split
from tsl.core.jsonio import read_yaml
from tsl.harness.skillchecks import CheckEnv, run_declared, validate_declared
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
    answered: frozenset[str] = frozenset(),
) -> Any:
    doc = _checks(skill)
    doc["checks"] = [c for c in doc["checks"] if c["id"] == check_id]
    assert doc["checks"], f"{check_id} not declared"
    env = CheckEnv(front, "", root, list((inputs or {}).values()), {}, dict(inputs or {}), answered)
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


# test-automation (#6 and the #45 review): results must equal the plan's non-manual tests, as
# TP-n/S-n/ACn pairs. results-linked: plan -> results (ran: pass or fail). results-planned: the reverse.
LINKED, PLANNED = "test-automation.results-linked", "test-automation.results-planned"


def _plan_input(root: Path, *levels: str) -> dict[str, str]:
    """TP-1 unit S-1/AC1, TP-2 integration S-1/AC2 + S-2/AC1, TP-3 manual S-3/AC1 (not automated)."""
    tests = _tests(["S-1/AC1"], ["S-1/AC2", "S-2/AC1"], ["S-3/AC1"])
    for t, level in zip(tests, levels or ("unit", "integration", "manual"), strict=True):
        t["level"] = level
    front = {"schema": "test-plan.v1", "tests": tests}
    return {"test_plan": _write_input(root, "in/tplan.md", front)}


def _result(test_id: str, covers: list[str], status: str = "pass") -> dict[str, Any]:
    return {"test_id": test_id, "covers": covers, "status": status}


GOOD = [_result("TP-1", ["S-1/AC1"]), _result("TP-2", ["S-1/AC2", "S-2/AC1"])]


def _both(
    root: Path,
    results: list[dict[str, Any]],
    inputs: dict[str, str] | None = None,
    answered: frozenset[str] = frozenset(),
    **front: Any,
) -> dict[str, tuple[str, str]]:
    art = {"schema": "test-result.v1", "results": results, **front}
    inputs = _plan_input(root) if inputs is None else inputs
    out = {}
    for cid in (LINKED, PLANNED):
        o = _outcome("test-automation", cid, art, root, inputs, answered)
        assert o.gate == "H2"
        out[cid] = (o.status, o.detail)
    return out


def test_test_automation_results_that_match_the_plan_pass_both_checks(tmp_path: Path) -> None:
    assert _both(tmp_path, GOOD) == {LINKED: ("pass", ""), PLANNED: ("pass", "")}


def test_test_automation_a_failing_test_still_covers_its_criteria(tmp_path: Path) -> None:
    results = [GOOD[0], _result("TP-2", ["S-1/AC2", "S-2/AC1"], "fail")]
    assert _both(tmp_path, results)[LINKED] == ("pass", "")


def test_test_automation_fails_when_a_result_drops_a_planned_criterion(tmp_path: Path) -> None:
    results = [GOOD[0], _result("TP-2", ["S-1/AC2"])]
    assert _both(tmp_path, results)[LINKED] == ("fail", "TP-2/S-2/AC1 covered fewer than 1 times")


def test_test_automation_fails_when_a_planned_test_is_hidden_behind_extra_claims(
    tmp_path: Path,
) -> None:
    """Review point 5: TP-2 never written, TP-1 claims its criteria. Both directions catch it."""
    results = [_result("TP-1", ["S-1/AC1", "S-1/AC2", "S-2/AC1"])]
    got = _both(tmp_path, results)
    assert got[LINKED] == ("fail", "TP-2/S-1/AC2 covered fewer than 1 times")
    assert got[PLANNED] == ("fail", "TP-1/S-1/AC2 covered fewer than 1 times")


def test_test_automation_fails_for_an_invented_test_id(tmp_path: Path) -> None:
    results = [*GOOD, _result("TP-7", ["S-1/AC1"])]
    assert _both(tmp_path, results)[PLANNED] == ("fail", "TP-7/S-1/AC1 covered fewer than 1 times")


def test_test_automation_fails_for_a_criterion_the_plan_does_not_give_the_test(
    tmp_path: Path,
) -> None:
    results = [_result("TP-1", ["S-1/AC1", "S-9/AC9"]), GOOD[1]]
    got = _both(tmp_path, results)
    assert got == {
        LINKED: ("pass", ""),
        PLANNED: ("fail", "TP-1/S-9/AC9 covered fewer than 1 times"),
    }


def test_test_automation_fails_for_a_result_of_a_manual_test(tmp_path: Path) -> None:
    results = [*GOOD, _result("TP-3", ["S-3/AC1"])]
    assert _both(tmp_path, results)[PLANNED] == ("fail", "TP-3/S-3/AC1 covered fewer than 1 times")


def test_test_automation_a_skipped_test_does_not_cover_its_criteria(tmp_path: Path) -> None:
    """Review point 3: only results that ran (pass or fail) count."""
    results = [GOOD[0], _result("TP-2", ["S-1/AC2", "S-2/AC1"], "skip")]
    got = _both(tmp_path, results)
    assert got[LINKED] == ("fail", "TP-2/S-1/AC2 covered fewer than 1 times")
    assert got[PLANNED] == ("pass", "")


def test_test_automation_results_linked_waits_for_an_open_blocking_question(
    tmp_path: Path,
) -> None:
    """Review point 1: a step that stops to ask must reach NEEDS-INPUT, not RETRY (decide row 5
    comes before row 6). The reverse check still runs: what was written must be planned."""
    q = {"id": "Q-01", "blocking": True, "ask": "tech lead", "text": "Which TP-2 data?"}
    got = _both(tmp_path, [GOOD[0]], questions=[q])
    assert got[LINKED] == ("skip", "blocking question open; checked after the answer")
    assert got[PLANNED] == ("pass", "")


def test_test_automation_results_linked_waits_for_a_blocking_unknown(tmp_path: Path) -> None:
    got = _both(tmp_path, [GOOD[0]], unknown=[{"id": "U-1", "blocking": True}])
    assert got[LINKED][0] == "skip"


def test_test_automation_results_linked_runs_once_the_question_is_answered(
    tmp_path: Path,
) -> None:
    q = {"id": "Q-01", "blocking": True, "ask": "tech lead", "text": "Which TP-2 data?"}
    got = _both(tmp_path, [GOOD[0]], answered=frozenset({"Q-01"}), questions=[q])
    assert got[LINKED] == ("fail", "TP-2/S-1/AC2 covered fewer than 1 times")


def test_test_automation_a_non_blocking_question_does_not_defer_the_check(tmp_path: Path) -> None:
    q = {"id": "Q-01", "blocking": False, "ask": "tech lead", "text": "Rename TP-2?"}
    assert _both(tmp_path, [GOOD[0]], questions=[q])[LINKED][0] == "fail"


def test_test_automation_a_plan_of_only_manual_tests_takes_no_results(tmp_path: Path) -> None:
    """Review point 4: with nothing to automate, no result may be claimed."""
    inputs = _plan_input(tmp_path, "manual", "manual", "manual")
    assert _both(tmp_path, [], inputs) == {LINKED: ("pass", ""), PLANNED: ("pass", "")}
    assert _both(tmp_path, [GOOD[0]], inputs)[PLANNED][0] == "fail"


def test_test_automation_fails_for_results_linked_to_criteria_the_plan_lacks(
    tmp_path: Path,
) -> None:
    """Before #6 this passed: each result's covers were compared with every result's covers."""
    got = _both(tmp_path, [_result("TP-1", ["S-9/AC9"]), _result("TP-2", ["S-9/AC8"])])
    assert got[LINKED][0] == "fail" and got[PLANNED][0] == "fail"


def test_test_automation_fails_when_the_test_plan_input_is_missing(tmp_path: Path) -> None:
    got = _both(tmp_path, GOOD, inputs={})
    assert got[LINKED] == ("fail", "input test_plan missing or has no front matter")
    assert got[PLANNED] == ("fail", "input test_plan missing or has no front matter")


def test_coverage_inputs_name_inputs_the_skill_declares() -> None:
    """tsl validate (validate_declared with the skill.yaml inputs) passes for every shipped skill."""
    for skill_dir in sorted(SKILLS.iterdir()):
        if not (skill_dir / "checks.yaml").is_file():
            continue
        declared = {i["name"] for i in read_yaml(skill_dir / "skill.yaml").get("inputs") or []}
        assert validate_declared(_checks(skill_dir.name), declared) == [], skill_dir.name


def test_validate_rejects_a_coverage_input_the_skill_does_not_declare() -> None:
    """Review point 6: a misspelt input fails tsl validate, not every run."""
    doc = _checks("test-automation")
    for c in doc["checks"]:
        if c["id"] == LINKED:
            c["each_input"] = "testplan"
        if c["id"] == PLANNED:
            c["covered_by_input"] = "plan"
    assert validate_declared(doc, {"test_plan", "test_strategy"}) == [
        f"{LINKED}: each_input testplan is not an input of the skill",
        f"{PLANNED}: covered_by_input plan is not an input of the skill",
    ]
    assert validate_declared(doc) == []  # without the skill's inputs, nothing to compare


def test_accuracy_cases_name_inputs_like_skill_yaml(tmp_path: Path) -> None:
    """Review point 8: inputs/test-plan.md must reach the check as `test_plan`."""
    from tsl.harness.accuracy import case_inputs

    for rel in ("inputs/test-plan.md", "inputs/stories.md"):
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text("---\nschema: x\n---\n", encoding="utf-8")
    got = {i["name"]: i["path"] for i in case_inputs(tmp_path)}
    assert got == {"test_plan": "inputs/test-plan.md", "stories": "inputs/stories.md"}
