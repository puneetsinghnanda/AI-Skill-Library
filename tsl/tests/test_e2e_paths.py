"""Run paths: NEEDS-INPUT and resume, RETRY with feedback, dropped findings, ESCALATE, ABORT."""

from __future__ import annotations

import json

from e2e_steps import SESSION, do_req_step, next_action, start_run
from helpers import World, git


def _answer(world: World, run_id: str, answered_by: str = "Customer A <po@example.com>") -> None:
    p = world.companion / f"runs/{run_id}/open-questions.md"
    text = p.read_text()
    text = text.replace("answer:\n", "answer: Keep 24 hours\n", 1)
    text = text.replace("answered_by:\n", f"answered_by: {answered_by}\n", 1)
    p.write_text(text)


def test_needs_input_then_resume(world: World) -> None:
    run_id = start_run(world)
    res = do_req_step(world, run_id, variant={"blocking_question": True})
    assert res["code"] == 4 and res["env"]["code"] == "E-RUN-01"
    assert res["env"]["data"]["action"] == "pause_input"
    qfile = world.companion / f"runs/{run_id}/open-questions.md"
    assert "## Q-01 · blocking · ask: product owner" in qfile.read_text()
    code, env = next_action(world, run_id)
    assert code == 4 and env["data"]["action"] == "pause_input"
    # resume refused while the blocking question is unanswered (E-RUN-03)
    code, env2, _, _ = world.cli(["state", "resume", run_id, "--json"], session=SESSION)
    assert code == 2 and env2 is not None and env2["code"] == "E-RUN-03"
    # an answer without a name and email is not valid (US-04 AC1)
    _answer(world, run_id, answered_by="someone")
    code, env3, _, _ = world.cli(["state", "resume", run_id, "--json"], session=SESSION)
    assert code == 2 and env3 is not None and env3["code"] == "E-RUN-03"
    qfile.write_text(
        qfile.read_text().replace(
            "answered_by: someone", "answered_by: Customer A <po@example.com>"
        )
    )
    code, env4, _, err = world.cli(["state", "resume", run_id, "--json"], session=SESSION)
    assert code == 0, (env4, err)
    assert env4 is not None and env4["data"]["answered"] == ["Q-01"]
    code, env5 = next_action(world, run_id)
    assert env5["data"]["cause"] == "input_answered" and env5["data"]["attempt"] == 2
    assert env5["data"]["answers"] == f"runs/{run_id}/open-questions.md"
    # attempt 1 moved to history (R-03)
    assert (
        world.companion / f"artifacts/ABC-142/{run_id}/history/req/a1/req.verification.json"
    ).exists()
    # editing a frozen answer is refused later (E-RUN-07)
    qfile.write_text(qfile.read_text().replace("answer: Keep 24 hours", "answer: Extend"))
    state = json.loads((world.companion / f"runs/{run_id}/state.json").read_text())
    assert "Q-01" in state["questions"]["answered_sha256"]
    import pytest

    from tsl.core.errors import TslError
    from tsl.core.repo import Companion
    from tsl.orchestrator.run import RunCtx
    from tsl.state.service import _resume_input

    with world.using("eng", SESSION) as rt:
        ctx = RunCtx(rt, Companion(world.companion), run_id)
        with pytest.raises(TslError) as ei:
            _resume_input(rt, ctx)
    assert ei.value.code == "E-RUN-07"


def test_retry_from_post_write_block_and_feedback(world: World) -> None:
    run_id = start_run(world)
    res = do_req_step(world, run_id, variant={"drop_section": "Unknown"}, expect_block=True)
    reason = res["blocked"]["reason"]
    assert reason.startswith("E-CHK-01") and "H2" in reason
    state = json.loads((world.companion / f"runs/{run_id}/state.json").read_text())
    assert state["steps"][0]["budget_used"]["checks"] == 1
    checks = json.loads(
        (world.companion / res["artifact"].replace(".md", ".checks.json")).read_text()
    )
    h2 = next(g for g in checks["gates"] if g["id"] == "H2")
    assert h2["status"] == "fail" and "E-H2-01" in h2["codes"]


def test_review_major_finding_retry_then_dropped_finding(world: World) -> None:
    run_id = start_run(world)
    major = [
        {
            "id": "F-1",
            "severity": "major",
            "category": "completeness",
            "text": "Retention rule is not listed as a requirement",
            "cites": [
                {
                    "ref": "context/intent-baseline.md#data-retention",
                    "quote": "Order events are kept 24 hours",
                }
            ],
        },
        {
            "id": "F-2",
            "severity": "minor",
            "category": "style",
            "text": "Invented citation",
            "cites": [{"ref": "context/missing.md#nowhere", "quote": "this text does not exist"}],
        },
    ]
    res = do_req_step(world, run_id, findings=major)
    env = res["env"]
    assert res["code"] == 2 and env["code"] == "E-CHK-01" and env["data"]["action"] == "retry"
    assert env["data"]["findings_dropped"] == ["F-2"]
    fb = json.loads((world.companion / env["data"]["retry_input"]).read_text())
    assert fb["kind"] == "review" and fb["must_resolve"] == ["F-1"] and fb["dropped"] == ["F-2"]
    rec = json.loads((world.companion / env["data"]["verification_path"]).read_text())
    assert rec["signals"]["S1"] == round(2 / 3, 4)  # 1 claim + 1 kept of 1 claim + 2 findings
    _code, nxt = next_action(world, run_id)
    assert (
        nxt["data"]["cause"] == "retry_review"
        and nxt["data"]["feedback"] == env["data"]["retry_input"]
    )
    # the same major finding again escalates at once (SDD-02 §8.2)
    res2 = do_req_step(world, run_id, findings=major[:1])
    assert res2["code"] == 4 and res2["env"]["code"] == "E-RUN-02"
    assert "G-escalate-req-a2" in (world.companion / f"runs/{run_id}/approvals.md").read_text()


def test_low_score_escalates_then_accept(world: World) -> None:
    run_id = start_run(world)
    res = do_req_step(world, run_id, score=2)
    assert res["code"] == 4 and res["env"]["data"]["action"] == "pause_approval"
    assert res["env"]["data"]["band"] == "Low"
    appr = world.companion / f"runs/{run_id}/approvals.md"
    appr.write_text(
        appr.read_text().replace(
            "decision:          # approve | reject | changes | abort",
            "decision: approve\ncomment: Accepted as is",
        )
    )
    git(world.companion, "commit", "-qam", "decision")
    git(world.companion, "push", "-q", "origin", "main")
    code, env, _, err = world.cli(["approve", run_id, "G-escalate-req-a1", "--json"], user="tl")
    assert code == 0, (env, err)
    world.sync_companion()
    code, env2, _, err = world.cli(["state", "resume", run_id, "--json"], session=SESSION)
    assert code == 0, (env2, err)
    state = json.loads((world.companion / f"runs/{run_id}/state.json").read_text())
    assert state["steps"][0]["status"] == "ACCEPTED"


def test_secret_in_artifact_aborts(world: World) -> None:
    run_id = start_run(world)
    canary = "AKIA" + "Z" * 16  # generated at run time, never committed (TC-SEC-004)
    res = do_req_step(
        world, run_id, variant={"known_value": f"newest first {canary}"}, expect_block=True
    )
    assert res["blocked"]["reason"].startswith("E-SEC-01")
    art = res["artifact"]
    _, _pkg, _, _ = world.cli(
        ["review", "record", art, "--unavailable", "not reached", "--json"], session=SESSION
    )
    code, env, _, err = world.cli(["decide", art, "--json"], session=SESSION)
    assert code == 5 and env is not None and env["code"] == "E-SEC-01", (env, err)
    state = json.loads((world.companion / f"runs/{run_id}/state.json").read_text())
    assert state["status"] == "COMPLETED" and state["end_reason"] == "aborted"
    assert not (world.companion / "runs/active/ABC-142__brownfield-change.lock").exists()
