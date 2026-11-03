"""Dropped findings reach the next attempt: decide keeps their severity and text, feedback.v1
carries them in dropped_findings, and verify passes them as data.retry.dropped."""

from __future__ import annotations

from typing import Any

from tsl.harness.decide import DecideInput, verify_findings
from tsl.harness.verify import _retry_from_feedback
from tsl.schemas.registry import errors as schema_errors

ROW_TYPES = "The list row types are marked changed with no citation."


def _feedback(**over: Any) -> dict[str, Any]:
    fb: dict[str, Any] = {
        "schema": "feedback.v1",
        "run_id": "run_01JA0B3C4D5E6F7G8H9JKMNPQR",
        "step": "design",
        "from_attempt": 1,
        "kind": "review",
        "gate_failures": [{"id": "H4", "detail": "DS-C01: GET /api/x is changed"}],
        "findings": [],
        "dropped": ["F-2"],
        "must_resolve": ["H4"],
    }
    fb.update(over)
    return fb


def test_decide_keeps_severity_and_text_of_a_dropped_finding() -> None:
    finding = {
        "id": "F-2",
        "severity": "major",
        "category": "correctness",
        "text": ROW_TYPES,
        "cites": [{"ref": "bad ref", "quote": "anything at all"}],
    }
    inp = DecideInput(
        checks={},
        review={"status": "ok", "findings": [finding]},
        front={},
        rubric={},
        limits={},
        used={},
        thresholds={},
        s5="fresh",
        requires_fresh_pack=False,
        is_code=False,
        change_limits={},
        resolver=None,  # type: ignore[arg-type]  # a bad cite is dropped before any lookup
        repos=set(),
    )
    kept, dropped, _ = verify_findings(inp)
    assert kept == []
    [d] = dropped
    assert d["id"] == "F-2" and d["severity"] == "major" and d["text"] == ROW_TYPES
    assert d["reason"].startswith("bad citation format")


def test_retry_carries_dropped_findings_when_feedback_has_them() -> None:
    dropped = [{"id": "F-2", "severity": "major", "text": ROW_TYPES, "reason": "not verified"}]
    retry = _retry_from_feedback(_feedback(dropped_findings=dropped, comment="Fix it"))
    assert retry["dropped"] == dropped
    assert retry["comment"] == "Fix it"
    assert retry["failures"] == [{"gate": "H4", "detail": "DS-C01: GET /api/x is changed"}]


def test_retry_has_no_dropped_key_for_older_feedback() -> None:
    retry = _retry_from_feedback(_feedback())
    assert set(retry) == {"failures", "findings"}


def test_feedback_with_and_without_dropped_findings_is_valid() -> None:
    dropped = [{"id": "F-2", "severity": "major", "text": ROW_TYPES, "reason": "not verified"}]
    assert schema_errors("feedback.v1", _feedback()) == []
    assert schema_errors("feedback.v1", _feedback(dropped_findings=dropped)) == []
    bad = [{"id": "F-2", "severity": "huge", "text": ROW_TYPES, "reason": "x"}]
    assert schema_errors("feedback.v1", _feedback(dropped_findings=bad)) != []
