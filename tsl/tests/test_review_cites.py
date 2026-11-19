"""tsl review record checks the reviewer's citations before it writes (SDD-03 §7.4).

HMS-6 to HMS-9: 34 findings were dropped at decide for citations in a form tsl could not check,
and the reviewer was never told. Now the record is rejected with E-REV-05 while retry.record
lasts, so the reviewer corrects the cite; after that the review is recorded as it is."""

from __future__ import annotations

import json
from typing import Any

from e2e_steps import SESSION, do_req_step, start_run
from helpers import World, review_json

GOOD = {
    "ref": "context/intent-baseline.md#data-retention",
    "quote": "Order events are kept 24 hours",
}
BAD = {"ref": "context/intent-baseline.md#data-retention", "quote": "Order events are kept 90 days"}


def _finding(fid: str, cite: dict[str, str], severity: str = "minor") -> dict[str, Any]:
    return {
        "id": fid,
        "severity": severity,
        "category": "consistency",
        "text": "Retention differs from the baseline.",
        "cites": [cite],
    }


def _record(world: World, art: str, package: dict[str, Any], **kw: Any) -> tuple[int, Any]:
    code, env, _, err = world.cli(
        ["review", "record", art, "--json"], session=SESSION, stdin=review_json(package, **kw)
    )
    assert env is not None, err
    return code, env


def _attempt(world: World, run_id: str) -> dict[str, Any]:
    state = json.loads((world.companion / f"runs/{run_id}/state.json").read_text())
    return dict(state["steps"][0]["attempts"][-1])


def test_good_citations_are_recorded_at_once(world: World) -> None:
    run_id = start_run(world)
    res = do_req_step(world, run_id, until="prepared")
    code, env = _record(world, res["artifact"], res["package"], findings=[_finding("F-1", GOOD)])
    assert code == 0 and env["warnings"] == [], env
    assert "record_rejects" not in _attempt(world, run_id)


def test_bad_citation_is_rejected_then_the_corrected_review_is_recorded(world: World) -> None:
    run_id = start_run(world)
    res = do_req_step(world, run_id, until="prepared")
    art, package = res["artifact"], res["package"]
    findings = [_finding("F-1", GOOD), _finding("F-2", BAD)]
    code, env = _record(world, art, package, findings=findings)
    assert code == 2 and env["code"] == "E-REV-05", env
    assert env["message"].startswith("1 reviewer citation(s) do not verify: finding F-2 ")
    assert env["data"]["citations"] == [
        {"item": "finding F-2", "ref": BAD["ref"], "reason": "quote not found"}
    ]
    assert (env["data"]["rejects"], env["data"]["max"]) == (1, 2)
    assert not (world.companion / art.replace(".md", ".review.json")).exists()  # nothing written
    assert _attempt(world, run_id)["record_rejects"] == 1
    # The reviewer corrects the cite: recorded, and the finding is kept at decide.
    fixed = [_finding("F-1", GOOD), _finding("F-2", GOOD)]
    code, env = _record(world, art, package, findings=fixed)
    assert code == 0 and env["warnings"] == [], env
    code, dec, _, err = world.cli(["decide", art, "--json"], session=SESSION)
    assert dec is not None, err
    rec = json.loads((world.companion / dec["data"]["verification_path"]).read_text())
    assert rec["findings_dropped"] == []
    assert [f["id"] for f in rec["findings_kept"]] == ["F-1", "F-2"]
    # Citation corrections do not use the budget kept for step retries on a major finding.
    state = json.loads((world.companion / f"runs/{run_id}/state.json").read_text())
    assert state["steps"][0]["budget_used"]["review"] == 0


def test_after_the_budget_the_review_is_recorded_and_decide_drops(world: World) -> None:
    run_id = start_run(world)
    res = do_req_step(world, run_id, until="prepared")
    art, package = res["artifact"], res["package"]
    findings = [_finding("F-1", BAD)]
    for n in (1, 2):
        code, env = _record(world, art, package, findings=findings)
        assert code == 2 and env["code"] == "E-REV-05" and env["data"]["rejects"] == n, env
    code, env = _record(world, art, package, findings=findings)
    assert code == 0, env
    [warn] = env["warnings"]
    assert warn["code"] == "E-REV-05" and "Recorded as is" in warn["message"], warn
    assert env["data"]["status"] == "ok"  # never could_not_review, so no Low cap from this
    assert _attempt(world, run_id)["record_rejects"] == 2
    code, dec, _, err = world.cli(["decide", art, "--json"], session=SESSION)
    assert dec is not None, err
    rec = json.loads((world.companion / dec["data"]["verification_path"]).read_text())
    assert rec["findings_dropped"] == [{"id": "F-1", "reason": "quote not found"}]


def test_reviewer_forms_tsl_accepts_are_not_rejected(world: World) -> None:
    """An HTML-escaped quote and a bare item id verify, so they cost no correction round."""
    run_id = start_run(world)
    res = do_req_step(world, run_id, until="prepared")
    art = res["artifact"]
    findings = [
        _finding("F-1", {"ref": f"{art}#C1", "quote": "Order events are kept `24 hours`"}),
        _finding("F-2", {"ref": f"{art}#claims", "quote": "Order events are kept `24 hours`"}),
        _finding("F-3", {**GOOD, "quote": "Order events are kept 24&nbsp;hours"}),
    ]
    code, env = _record(world, art, res["package"], findings=findings)
    assert code == 0 and env["warnings"] == [], env


def test_bad_format_names_the_allowed_forms(world: World) -> None:
    run_id = start_run(world)
    res = do_req_step(world, run_id, until="prepared")
    # Not an absolute path (record refuses those first, E-REV-02): a repo tsl does not know.
    bad = {"ref": "nosuchrepo:skills/review/rubric.md#L46", "quote": "anything at all"}
    code, env = _record(world, res["artifact"], res["package"], findings=[_finding("F-1", bad)])
    assert code == 2 and env["code"] == "E-REV-05", env
    [c] = env["data"]["citations"]
    assert c["item"] == "finding F-1" and c["reason"].startswith("unknown repo"), c


def test_a_failing_pre_check_records_with_a_warning(world: World, monkeypatch: Any) -> None:
    """A bug in the record-time check must not turn it off quietly: the review is recorded
    (decide still checks every cite), with E-REV-07 and the trace in tsl.log."""
    import tsl.review.service as svc

    def boom(*_a: Any, **_k: Any) -> list[dict[str, str]]:
        raise RuntimeError("resolver broke")

    monkeypatch.setattr(svc, "cite_failures", boom)
    run_id = start_run(world)
    res = do_req_step(world, run_id, until="prepared")
    code, env = _record(world, res["artifact"], res["package"], findings=[_finding("F-1", BAD)])
    assert code == 0, env
    [warn] = env["warnings"]
    assert warn["code"] == "E-REV-07" and "RuntimeError: resolver broke" in warn["message"], warn
    assert "record_rejects" not in _attempt(world, run_id)
    log = world.rt().home.logs / "tsl.log"
    lines = [json.loads(x) for x in log.read_text(encoding="utf-8").splitlines()]
    assert any(x["code"] == "E-REV-07" and "resolver broke" in x["msg"] for x in lines), lines
