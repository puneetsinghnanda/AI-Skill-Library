"""Every row of the SDD-03 §11.1 decision table, the caps (§10.3) and band boundaries (§10.2)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from tsl.core.config import effective_bands
from tsl.harness.citations import Resolver
from tsl.harness.decide import DecideInput, compute_band, evaluate

RUBRIC = {"criteria": [{"id": "RR-R1", "weight": 0.5}, {"id": "RR-R2", "weight": 0.5}]}
QUOTE = "Order events are kept 24 hours"


def gates(
    fail: dict[str, list[str]] | None = None, pending: str | None = None
) -> list[dict[str, Any]]:
    out = []
    for g in ("H1", "H2", "H3", "H4", "H5", "H6", "H7"):
        codes = (fail or {}).get(g, [])
        status = "fail" if codes else ("pending" if g == pending else "pass")
        out.append({"id": g, "pass": not codes, "status": status, "codes": codes, "detail": ""})
    return out


def finding(
    fid: str,
    sev: str,
    ref: str = "context/base.md#retention",
    quote: str = QUOTE,
    category: str = "completeness",
) -> dict[str, Any]:
    return {
        "id": fid,
        "severity": sev,
        "category": category,
        "text": "x",
        "cites": [{"ref": ref, "quote": quote}],
    }


def review(
    score: int = 5,
    findings: list[dict[str, Any]] | None = None,
    questions: list[dict[str, Any]] | None = None,
    status: str = "ok",
) -> dict[str, Any]:
    return {
        "status": status,
        "rubric_score": float(score),
        "rubric_items": [{"id": "RR-R1", "score": score}, {"id": "RR-R2", "score": score}],
        "findings": findings or [],
        "claims_checked": [],
        "questions": questions or [],
    }


@pytest.fixture
def root(tmp_path: Path) -> Path:
    (tmp_path / "context").mkdir()
    (tmp_path / "context" / "base.md").write_text(
        "# Base\n\n## Retention {#retention}\n" + QUOTE + ".\n"
    )
    (tmp_path / "auth").mkdir()
    (tmp_path / "auth" / "login.md").write_text(
        "# Login\n\n## Flow {#flow}\nTokens are checked on login.\n"
    )
    return tmp_path


def make(root: Path, **kw: Any) -> DecideInput:
    base: dict[str, Any] = dict(
        checks={
            "gates": gates(),
            "soft": [{"id": "GEN-SIZE-01", "pass": True}],
            "product_changes": None,
        },
        review=review(),
        front={
            "claims": [
                {"id": "C1", "text": "kept `24 hours`", "cites": ["context/base.md#retention"]}
            ]
        },
        rubric=RUBRIC,
        limits={"checks": 2, "review": 2, "verifier": 3},
        used={"checks": 0, "review": 0, "verifier": 0},
        thresholds=effective_bands(None, None),
        s5="fresh",
        requires_fresh_pack=True,
        is_code=False,
        change_limits={"lines": 400, "files": 15, "sensitive_paths": ["**/auth/**"]},
        resolver=Resolver(root, {}, {}),
        repos=set(),
    )
    base.update(kw)
    return DecideInput(**base)


def test_row1_abort_on_security_code(root: Path) -> None:
    d = evaluate(make(root, checks={"gates": gates({"H4": ["E-SEC-01"]}), "soft": []}))
    assert (d.outcome, d.row, d.band) == ("ABORT", 1, None)


@pytest.mark.parametrize(
    "code", ["E-SEC-02", "E-POL-01", "E-POL-02", "E-POL-03", "E-POL-04", "E-POL-05"]
)
def test_row1_abort_every_code(root: Path, code: str) -> None:
    assert (
        evaluate(make(root, checks={"gates": gates({"H7": [code]}), "soft": []})).outcome == "ABORT"
    )


def test_row2_escalate_checks_budget(root: Path) -> None:
    d = evaluate(
        make(
            root,
            checks={"gates": gates({"H2": ["E-H2-01"]}), "soft": []},
            used={"checks": 2, "review": 0, "verifier": 0},
        )
    )
    assert (d.outcome, d.row) == ("ESCALATE", 2) and "checks" in str(d.escalate_reason)


def test_row2_escalate_fix_loop_budget(root: Path) -> None:
    d = evaluate(
        make(
            root,
            checks={"gates": gates({"H3": ["E-H3-02"]}), "soft": []},
            used={"checks": 0, "review": 0, "verifier": 3},
        )
    )
    assert (d.outcome, d.row) == ("ESCALATE", 2) and "verifier" in str(d.escalate_reason)


def test_row3_retry_upstream_on_h6(root: Path) -> None:
    d = evaluate(
        make(root, checks={"gates": gates({"H6": ["E-IN-02"]}), "soft": []}, stale_steps=["impact"])
    )
    assert (d.outcome, d.row, d.rerun_step, d.budget_kind) == ("RETRY", 3, "impact", None)


def test_row4_retry_fix_loop(root: Path) -> None:
    d = evaluate(make(root, checks={"gates": gates({"H3": ["E-H3-02"]}), "soft": []}))
    assert (d.outcome, d.row, d.budget_kind) == ("RETRY", 4, "verifier")


def test_row5_retry_checks(root: Path) -> None:
    d = evaluate(make(root, checks={"gates": gates({"H1": ["E-H1-04"]}), "soft": []}))
    assert (d.outcome, d.row, d.budget_kind, d.band) == ("RETRY", 5, "checks", None)


def test_row6_needs_input_from_blocker_and_question(root: Path) -> None:
    d = evaluate(
        make(
            root,
            review=review(
                findings=[finding("F-1", "blocker")],
                questions=[{"id": "Q-1", "text": "?", "ask_role": "tech_lead", "blocking": True}],
            ),
        )
    )
    assert (d.outcome, d.row) == ("NEEDS-INPUT", 6) and d.signals["S4"] == 2


def test_row6_envelope_question_with_bad_evidence_is_dropped(root: Path) -> None:
    q = {
        "id": "Q-01",
        "blocking": True,
        "ask": "tech lead",
        "text": "?",
        "evidence": ["context/none.md#x"],
    }
    d = evaluate(make(root, front={"claims": [], "questions": [q]}))
    assert d.outcome != "NEEDS-INPUT" and d.signals["S4"] == 0


def test_row7_retry_on_major_finding(root: Path) -> None:
    d = evaluate(make(root, review=review(findings=[finding("F-1", "major")])))
    assert (d.outcome, d.row, d.budget_kind) == ("RETRY", 7, "review")


def test_row7_repeat_finding_escalates(root: Path) -> None:
    f = finding("F-1", "major")
    prev = {"findings": [{"id": "F-1", "severity": "major", "cites": f["cites"]}]}
    d = evaluate(make(root, review=review(findings=[f]), prev_feedback=prev))
    assert (d.outcome, d.row) == ("ESCALATE", 7)


def test_row8_escalate_on_low_band(root: Path) -> None:
    d = evaluate(make(root, review=review(score=2)))
    assert (d.outcome, d.row, d.band) == ("ESCALATE", 8, "Low") and "S3" in d.reasons


def test_row8_reviewer_missing_caps_low(root: Path) -> None:
    d = evaluate(make(root, review=review(status="could_not_review")))
    assert d.outcome == "ESCALATE" and d.band == "Low" and "reviewer-missing" in d.caps
    assert d.signals["S3"] is None


def test_row9_pass_with_findings(root: Path) -> None:
    d = evaluate(make(root, review=review(findings=[finding("F-1", "minor", category="style")])))
    assert (d.outcome, d.row, d.band) == ("PASS-WITH-FINDINGS", 9, "High")


def test_row9_major_after_review_retries(root: Path) -> None:
    d = evaluate(
        make(
            root,
            review=review(findings=[finding("F-1", "major")]),
            used={"checks": 0, "review": 2, "verifier": 0},
        )
    )
    assert d.outcome == "PASS-WITH-FINDINGS"


def test_row10_pass(root: Path) -> None:
    d = evaluate(make(root))
    assert (d.outcome, d.row, d.band) == ("PASS", 10, "High")


def test_cap_pack_stale_limits_medium(root: Path) -> None:
    d = evaluate(make(root, s5="stale"))
    assert d.band == "Medium" and "pack-stale" in d.caps and "CAP-PACK" in d.reasons
    d2 = evaluate(make(root, s5="missing", requires_fresh_pack=False))
    assert "pack-stale" not in d2.caps


def test_cap_format_only_cites(root: Path) -> None:
    f = {
        "id": "F-1",
        "severity": "minor",
        "category": "style",
        "text": "x",
        "cites": [{"ref": "design.fig#node:12-34", "quote": "button label"}],
    }
    d = evaluate(make(root, review=review(findings=[f])))
    assert "format-only-cites" in d.caps and d.band == "Medium"


def test_severity_raised_never_lowered(root: Path) -> None:
    sec = finding("F-1", "minor", category="security")
    d = evaluate(make(root, review=review(findings=[sec])))
    assert d.kept[0]["severity"] == "major" and d.kept[0]["raised_from"] == "minor"
    path = finding("F-2", "minor", ref="auth/login.md#flow", quote="Tokens are checked on login")
    d2 = evaluate(make(root, review=review(findings=[path])))
    assert d2.kept[0]["severity"] == "major"
    blocker = finding("F-3", "blocker")
    assert evaluate(make(root, review=review(findings=[blocker]))).kept[0]["severity"] == "blocker"


def test_dropped_finding_counts_against_s1(root: Path) -> None:
    bad = finding("F-9", "minor", ref="context/missing.md#x", quote="no such text here")
    d = evaluate(make(root, review=review(findings=[bad])))
    assert d.dropped == [{"id": "F-9", "reason": "path not found"}]
    assert d.signals["S1"] == 0.5  # 1 verified claim of 1 claim + 1 finding


@pytest.mark.parametrize(
    ("s1", "band"), [(0.90, "High"), (0.8999, "Medium"), (0.75, "Medium"), (0.7499, "Low")]
)
def test_band_boundaries_s1(s1: float, band: str) -> None:
    s = {"S1": s1, "S2": 1.0, "S3": 4.0, "S4": 0, "S5": "fresh"}
    assert compute_band(s, 0.0, effective_bands(None, None), []) == band


@pytest.mark.parametrize(
    ("s3", "band"), [(4.0, "High"), (3.99, "Medium"), (3.0, "Medium"), (2.99, "Low")]
)
def test_band_boundaries_s3(s3: float, band: str) -> None:
    s = {"S1": 1.0, "S2": 1.0, "S3": s3, "S4": 0, "S5": "fresh"}
    assert compute_band(s, 0.0, effective_bands(None, None), []) == band


@pytest.mark.parametrize(
    ("r6", "band"), [(1.0, "High"), (1.01, "Medium"), (2.0, "Medium"), (2.01, "Low")]
)
def test_band_boundaries_s6(r6: float, band: str) -> None:
    s = {"S1": 1.0, "S2": 1.0, "S3": 5.0, "S4": 0, "S5": "fresh"}
    assert compute_band(s, r6, effective_bands(None, None), []) == band


def test_s2_boundary() -> None:
    s = {"S1": 1.0, "S2": 0.9, "S3": 5.0, "S4": 0, "S5": "fresh"}
    assert compute_band(s, 0, effective_bands(None, None), []) == "Medium"
    s["S2"] = 0.8999
    assert compute_band(s, 0, effective_bands(None, None), []) == "Low"


def test_thresholds_only_tighten() -> None:
    t = effective_bands({"high": {"S1_min": 0.95, "S6_max_ratio": 3.0}}, {"high": {"S1_min": 0.8}})
    assert t["high"]["S1_min"] == 0.95 and t["high"]["S6_max_ratio"] == 1.0


def test_s6_sensitive_path_is_infinite_risk(root: Path) -> None:
    ch = [{"repo": "r", "lines_added": 1, "lines_deleted": 0, "files": ["src/auth/token.js"]}]
    d = evaluate(
        make(root, is_code=True, checks={"gates": gates(), "soft": [], "product_changes": ch})
    )
    assert d.signals["S6"] == {"lines": 1, "files": 1, "sensitive": True} and d.band == "Low"


def test_cap_no_verifier(root: Path) -> None:
    g = gates()
    g[2] = {
        "id": "H3",
        "pass": True,
        "status": "skip",
        "codes": [],
        "detail": "no verifier profile",
    }
    d = evaluate(make(root, is_code=True, checks={"gates": g, "soft": [], "product_changes": []}))
    assert "no-verifier" in d.caps and d.band == "Medium" and d.outcome == "PASS"


def test_first_matching_row_wins(root: Path) -> None:
    # a security abort beats an exhausted budget, a stale input and a blocker
    d = evaluate(
        make(
            root,
            checks={"gates": gates({"H4": ["E-SEC-01"], "H6": ["E-IN-02"]}), "soft": []},
            used={"checks": 2, "review": 2, "verifier": 3},
            review=review(findings=[finding("F-1", "blocker")]),
        )
    )
    assert (d.outcome, d.row) == ("ABORT", 1)
    # an H6 retry beats an H3 fix loop
    d = evaluate(
        make(
            root,
            checks={"gates": gates({"H3": ["E-H3-02"], "H6": ["E-IN-02"]}), "soft": []},
            stale_steps=["req"],
        )
    )
    assert (d.outcome, d.row) == ("RETRY", 3)
    # blockers pause before a major finding retries
    d = evaluate(
        make(root, review=review(findings=[finding("F-1", "blocker"), finding("F-2", "major")]))
    )
    assert (d.outcome, d.row) == ("NEEDS-INPUT", 6)
