"""tsl improve plan | case | check | pr (SDD-11 §5-§6) on the invented fixture skill."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from helpers import World, git, intent_artifact
from tsl.schemas.registry import errors

SKILL = "requirement-review"
ENV = {
    "schema": "intent.v1",
    "run_id": "run_01J9ZK2M4Q8X7T3B5N6R0VWYCD",
    "step": "req",
    "attempt": 1,
    "skill": "requirement-review@1.0.0",
    "inputs": [],
    "pack_sha": {},
}


def _ok(w: World, args: list[str], user: str = "eng") -> dict[str, Any]:
    code, env, _, err = w.cli([*args, "--json"], user=user)
    assert code == 0, (env, err)
    assert env is not None
    return env


REVIEW = {
    "schema": "review.v1",
    "status": "ok",
    "rubric_score": 5.0,
    "rubric_items": [{"id": f"RR-R{i}", "score": 5, "reason": "ok"} for i in range(1, 7)],
    "findings": [],
    "claims_checked": [],
    "questions": [],
}


def write_outputs(plan: dict[str, Any], bad: set[str]) -> None:
    """What Claude does on the seat: one output (and canned review) per case."""
    for c in plan["cases"]:
        env = dict(ENV, skill=f"{SKILL}@{plan['version']}")
        text = intent_artifact(
            env, "inputs/ticket.md", drop_section="Unknown" if c["id"] in bad else None
        )
        Path(c["output_path"]).write_text(text, encoding="utf-8")
        cited = Path(c["output_path"]).parent / "context" / "intent-baseline.md"
        cited.parent.mkdir(parents=True, exist_ok=True)
        cited.write_text(
            "# Intent {#intent}\n\n## Data retention {#data-retention}\n"
            "Order events are kept 24 hours.\n",
            encoding="utf-8",
        )
        Path(c["review_path"]).write_text(json.dumps(REVIEW), encoding="utf-8")


def _eval(w: World, bad: set[str]) -> dict[str, Any]:
    plan = _ok(w, ["eval", "plan", SKILL])["data"]
    write_outputs(plan, bad)
    _code, env, _, err = w.cli(["eval", "run", SKILL, "--json"])
    assert env is not None, err
    data: dict[str, Any] = env["data"]
    return data


def _bump(w: World, version: str = "1.0.1") -> None:
    p = w.plugin / "skills" / SKILL / "skill.yaml"
    meta = yaml.safe_load(p.read_text())
    meta["version"] = version
    p.write_text(yaml.safe_dump(meta, sort_keys=False))
    (w.plugin / "skills" / SKILL / "SKILL.md").open("a").write("\nAsk about retention.\n")


def _prepare(w: World, case_ok_before: bool = False) -> dict[str, Any]:
    plan: dict[str, Any] = _ok(
        w, ["improve", "plan", SKILL, "--flag", "flg_01JA1Z0000000000000000000A"]
    )["data"]
    assert plan["first_step"] == "add_failing_eval_case" and plan["flags"]
    case = _ok(w, ["improve", "case", SKILL, "--id", "EC-11", "--kind", "conflict"])["data"]
    meta = yaml.safe_load((Path(case["case_dir"]) / "case.yaml").read_text())
    assert meta["provenance"] == "invented" and meta["attestation"]["by"] == "eng-4f2a"
    assert errors("eval-case.v1", meta) == []
    _eval(w, set() if case_ok_before else {"EC-11"})
    _bump(w)
    return plan


def test_improve_happy_path(world: World) -> None:
    plan = _prepare(world)
    after = _eval(world, set())
    assert after["version"] == "1.0.1" and after["pass_rate"] == 1.0
    env = _ok(world, ["improve", "check", SKILL])
    rec = json.loads(Path(env["data"]["improvement_path"]).read_text())
    assert errors("improvement.v1", rec) == []
    assert rec["id"] == plan["improvement_id"] and rec["cases_added"] == ["EC-11"]
    assert rec["before"]["new_cases_failed"] == ["EC-11"]
    assert rec["after"]["new_cases_passed"] == ["EC-11"]
    assert rec["flags"] == ["flg_01JA1Z0000000000000000000A"]


def test_new_case_must_fail_before(world: World) -> None:
    _prepare(world, case_ok_before=True)
    _eval(world, set())
    code, env, _, _ = world.cli(["improve", "check", SKILL, "--json"])
    assert code == 2 and env is not None and env["code"] == "E-IMP-01"
    assert not list((world.plugin / "skills" / SKILL / "evals").glob("improvements/*.json"))


def test_regression_is_refused(world: World) -> None:
    _prepare(world)
    _eval(world, {"EC-02"})
    code, env, _, _ = world.cli(["improve", "check", SKILL, "--json"])
    assert code == 2 and env is not None and env["code"] == "E-IMP-02"
    assert env["data"]["regressions"] == ["EC-02"]


def test_tampered_result_is_refused(world: World) -> None:
    _prepare(world)
    data = _eval(world, set())
    p = Path(data["result_path"])
    rec = json.loads(p.read_text())
    rec["pass_rate"] = 1.0
    rec["cases"][0]["result"] = "pass"
    rec["recorded_at"] = "2026-01-01T00:00:01Z"
    p.write_text(json.dumps(rec))
    code, env, _, _ = world.cli(["improve", "check", SKILL, "--json"])
    assert code == 2 and env is not None and env["code"] == "E-IMP-04"


def test_skill_change_after_eval_is_refused(world: World) -> None:
    _prepare(world)
    _eval(world, set())
    (world.plugin / "skills" / SKILL / "SKILL.md").open("a").write("\nchanged after the eval\n")
    code, env, _, _ = world.cli(["improve", "check", SKILL, "--json"])
    assert code == 2 and env is not None and env["code"] == "E-IMP-04"


def test_forbidden_content_in_new_case(world: World) -> None:
    _ok(world, ["improve", "plan", SKILL])
    case = _ok(world, ["improve", "case", SKILL, "--id", "EC-12"])["data"]
    (Path(case["case_dir"]) / "inputs" / "ticket.md").write_text(
        "# T-1\nSee artifacts/ABC-142/run_01J9ZK2M4Q8X7T3B5N6R0VWYCD/req.md\n"
    )
    _eval(world, {"EC-12"})
    _bump(world)
    _eval(world, set())
    code, env, _, _ = world.cli(["improve", "check", SKILL, "--json"])
    assert code == 2 and env is not None and env["code"] == "E-IMP-05"
    hit = env["data"]["forbidden"][0]
    assert hit["path"].endswith("EC-12/inputs/ticket.md") and hit["line"] == 2
    assert "run_01J9" not in env["message"]  # the matched value is never echoed


def test_case_id_and_unknown_skill(world: World) -> None:
    code, env, _, _ = world.cli(["improve", "case", SKILL, "--id", "ia-021", "--json"])
    assert code == 1 and env is not None and env["code"] == "E-USE-01"
    code, env, _, _ = world.cli(["improve", "plan", "no-such-skill", "--json"])
    assert code == 1 and env is not None and env["code"] == "E-USE-01"


def test_plan_offline_uses_cache(world: World) -> None:
    _ok(world, ["improve", "plan", SKILL])
    world.insights.offline = True
    code, env, _, _ = world.cli(["improve", "plan", SKILL, "--json"])
    assert code == 10 and env is not None and env["code"] == "E-NET-02"
    env = _ok(world, ["improve", "plan", SKILL, "--offline"])
    assert env["warnings"][0]["code"] == "E-NET-01"
    report = world.base / "report.json"
    report.write_text(json.dumps(world.insights.report))
    env = _ok(world, ["improve", "plan", SKILL, "--report", str(report)])
    assert env["data"]["top_issues"]


def test_improve_pr_opens_a_pull_request(world: World) -> None:
    # make the plugin a clone of a skill-library repo with a remote
    remote = world.base / "remotes" / "skill-library.git"
    git(world.base, "init", "-q", "--bare", "-b", "main", str(remote))
    lib = world.plugin
    git(lib, "init", "-q", "-b", "main")
    git(lib, "remote", "add", "origin", str(remote))
    git(lib, "add", "-A")
    git(lib, "commit", "-qm", "library")
    git(lib, "push", "-q", "origin", "main")
    code, env, _, _ = world.cli(["improve", "pr", SKILL, "--json"])
    assert code == 3 and env is not None and env["code"] == "E-ENV-01"
    plan = _prepare(world)
    assert plan["branch"] == f"improve/{SKILL}/{plan['improvement_id']}"
    assert git(lib, "rev-parse", "--abbrev-ref", "HEAD") == plan["branch"]
    _eval(world, set())
    _ok(world, ["improve", "check", SKILL])
    env = _ok(world, ["improve", "pr", SKILL, "--summary", "Ask about retention conflicts."])
    pr = world.github.created[-1]
    assert pr["head"] == plan["branch"] and pr["draft"] is False
    assert f"<!-- tsl:improvement={plan['improvement_id']} -->" in pr["body"]
    assert "1.0.0 → 1.0.1" in pr["title"]
    assert plan["branch"] in git(remote, "branch", "--list", "improve/*")
    ev = [e for e in world.rt().outbox().events() if e["type"] == "improvement.proposed"]
    assert ev and ev[-1]["body"]["cases_added"] == 1
    assert env["data"]["pr"]["url"].endswith(f"/pull/{len(world.github.created)}")


def test_pass_rate_below_minimum(world: World) -> None:
    _ok(world, ["improve", "plan", SKILL])
    _ok(world, ["improve", "case", SKILL, "--id", "EC-11"])
    _eval(world, {"EC-11", "EC-02", "EC-03"})
    _bump(world)
    _eval(world, {"EC-02", "EC-03"})
    code, env, _, _ = world.cli(["improve", "check", SKILL, "--json"])
    assert env is not None and (code, env["code"]) == (2, "E-IMP-03")  # 9/12 < 0.9
    assert env["data"]["regressions"] == []
