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


def _architecture(root: Path, *components: str) -> dict[str, str]:
    """The architecture context section; `components:` only when names are given (#5)."""
    front: dict[str, Any] = {
        "schema": "context-section.v1",
        "section": "architecture",
        "owner": "tl-7a1c",
        "origin": "human",
        "status": "reviewed",
        "verified_at": None,
    }
    if components:
        front["components"] = [{"name": c} for c in components]
    assert schema_errors("context-section.v1", front) == []
    return {"architecture": _write_input(root, "context/architecture.md", front)}


def test_threat_model_without_a_design_covers_the_architecture_components(tmp_path: Path) -> None:
    """security-review has no design step: the architecture's components list stands in (#5)."""
    inputs = _architecture(tmp_path, "api", "web", "db")
    front = {"schema": "threat-model.v1", "threats": _threats("api", "web", "db")}
    out = _outcome("threat-model", "threat-model.stride-per-component", front, tmp_path, inputs)
    assert (out.gate, out.status) == ("H2", "pass"), out.detail


def test_threat_model_without_a_design_fails_for_an_architecture_component_without_a_threat(
    tmp_path: Path,
) -> None:
    inputs = _architecture(tmp_path, "api", "web", "db")
    front = {"schema": "threat-model.v1", "threats": _threats("api", "web")}
    out = _outcome("threat-model", "threat-model.stride-per-component", front, tmp_path, inputs)
    assert (out.status, out.detail) == ("fail", "db covered fewer than 1 times")


def test_threat_model_uses_the_design_when_both_inputs_are_present(tmp_path: Path) -> None:
    inputs = {**_architecture(tmp_path, "api", "web"), **_design(tmp_path, "NotesRoute")}
    front = {"schema": "threat-model.v1", "threats": _threats("NotesRoute")}
    out = _outcome("threat-model", "threat-model.stride-per-component", front, tmp_path, inputs)
    assert out.status == "pass", out.detail  # the architecture's api and web are not required


def test_threat_model_fails_when_the_architecture_lists_no_components(tmp_path: Path) -> None:
    inputs = _architecture(tmp_path)
    front = {"schema": "threat-model.v1", "threats": _threats("api")}
    out = _outcome("threat-model", "threat-model.stride-per-component", front, tmp_path, inputs)
    assert (out.status, out.detail) == (
        "fail",
        "input architecture has nothing to cover at $.components[*].name",
    )


def test_threat_model_fails_for_a_design_with_no_components(tmp_path: Path) -> None:
    inputs = _design(tmp_path)
    front = {"schema": "threat-model.v1", "threats": _threats("api")}
    out = _outcome("threat-model", "threat-model.stride-per-component", front, tmp_path, inputs)
    assert (out.status, out.detail) == (
        "fail",
        "input design has nothing to cover at $.components[*].name",
    )


def test_threat_model_names_both_inputs_when_neither_is_present(tmp_path: Path) -> None:
    front = {"schema": "threat-model.v1", "threats": _threats("api")}
    out = _outcome("threat-model", "threat-model.stride-per-component", front, tmp_path, {})
    assert (out.status, out.detail) == (
        "fail",
        "input design or architecture missing or has no front matter",
    )


def test_threat_model_fails_for_a_bound_design_whose_file_is_missing(tmp_path: Path) -> None:
    """Review: a workflow that binds a design (brownfield-change) must not fall back to the
    architecture's generic components when the design file is missing."""
    inputs = {**_architecture(tmp_path, "api", "web"), "design": "in/missing-design.md"}
    front = {"schema": "threat-model.v1", "threats": _threats("api", "web")}
    out = _outcome("threat-model", "threat-model.stride-per-component", front, tmp_path, inputs)
    assert (out.status, out.detail) == ("fail", "input design missing or has no front matter")


def test_threat_model_waits_while_it_asks_for_the_components_list(tmp_path: Path) -> None:
    """Review: rule 5 asks the tech lead for the list; the question must reach NEEDS-INPUT, not a
    retry. Once answered, the check runs again."""
    inputs = _architecture(tmp_path)
    q = {"id": "Q-01", "blocking": True, "ask": "tech lead", "text": "Add a components list?"}
    front = {"schema": "threat-model.v1", "threats": _threats("api"), "questions": [q]}
    cid = "threat-model.stride-per-component"
    out = _outcome("threat-model", cid, front, tmp_path, inputs)
    assert (out.status, out.detail) == ("skip", "blocking question open; checked after the answer")
    out = _outcome("threat-model", cid, front, tmp_path, inputs, frozenset({"Q-01"}))
    assert out.status == "fail"


def test_threat_model_eval_without_a_design_lists_architecture_components() -> None:
    """Review: EC-02 (no design) must give the check something to cover."""
    case = SKILLS / "threat-model" / "evals" / "cases" / "EC-02"
    assert "design" not in read_yaml(case / "case.yaml")["inputs"]
    arch = split((case / "inputs" / "architecture.md").read_text(encoding="utf-8")).front
    assert schema_errors("context-section.v1", dict(arch)) == []
    assert [c["name"] for c in arch["components"]] == ["web", "api", "purge-job"]


def test_threat_model_security_review_input_is_declared() -> None:
    """The fallback input must be one threat-model declares (context/architecture.md)."""
    meta = read_yaml(SKILLS / "threat-model" / "skill.yaml")
    names = {i["name"]: i for i in meta["inputs"]}
    assert names["architecture"]["path"] == "context/architecture.md"
    assert names["design"]["required"] is False


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


def test_test_plan_fails_when_the_stories_hold_no_acceptance_criteria(tmp_path: Path) -> None:
    """Before #5 this passed: nothing to cover meant nothing could be uncovered."""
    story = {**_story("S-1", ["REQ-1"]), "acceptance_criteria": []}
    rel = _write_input(tmp_path, "in/stories.md", {"schema": "stories.v1", "stories": [story]})
    front = {"schema": "test-plan.v1", "tests": _tests(["S-1/AC1"])}
    out = _outcome("test-plan", "test-plan.every-ac-tested", front, tmp_path, {"stories": rel})
    assert (out.status, out.detail) == (  # names the path that came back empty (review)
        "fail",
        "input stories has nothing to cover at $.stories[*] $.acceptance_criteria[*].id",
    )


def test_test_plan_waits_while_it_asks_for_missing_acceptance_criteria(tmp_path: Path) -> None:
    """Review of #51: stories with no criteria are something the skill cannot fix. stories.v1 rejects
    them, but test-plan's inputs are not schema-checked again, so as a safeguard rule 5 asks the tech
    lead and the check waits: decide reaches NEEDS-INPUT, not RETRY until ESCALATE."""
    story = {**_story("S-1", ["REQ-1"]), "acceptance_criteria": []}
    stories = {"schema": "stories.v1", "trace": ["REQ-1"], "stories": [story]}
    ac_errors = [e for e in schema_errors("stories.v1", stories) if "acceptance" in e.pointer]
    assert [e.keyword for e in ac_errors] == [
        "minItems"
    ]  # stories.v1 rejects it at story-split (H1)
    rel = _write_input(tmp_path, "in/stories.md", stories)
    q = {"id": "Q-01", "blocking": True, "ask": "tech lead", "text": "S-1 has no criteria?"}
    front = {"schema": "test-plan.v1", "tests": _tests(["S-1/AC1"]), "questions": [q]}
    cid = "test-plan.every-ac-tested"
    out = _outcome("test-plan", cid, front, tmp_path, {"stories": rel})
    assert (out.status, out.detail) == ("skip", "blocking question open; checked after the answer")
    out = _outcome("test-plan", cid, front, tmp_path, {"stories": rel}, frozenset({"Q-01"}))
    assert out.status == "fail" and "nothing to cover" in out.detail


def test_coverage_without_nonempty_still_passes_on_nothing_to_cover() -> None:
    """`nonempty` is opt-in: test-automation may legitimately have only manual tests (#45)."""
    check = {"id": "x.y", "kind": "coverage", "each": "$.none[*]", "covered_by": "$.refs[*]"}
    env = CheckEnv({"refs": []}, "", ROOT, [], {}, {})
    assert run_declared(env, {"checks": [check]})[0].status == "pass"
    assert run_declared(env, {"checks": [{**check, "nonempty": True}]})[0].detail == (
        "the artifact has nothing to cover at $.none[*]"
    )


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
