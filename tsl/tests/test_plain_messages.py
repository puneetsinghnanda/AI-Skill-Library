"""Plain-words pause messages (what happened, where to look, what to do next)."""

from __future__ import annotations

import pytest

from tsl.harness import plain


@pytest.mark.parametrize(
    ("score", "words"),
    [
        (5, "very good"),
        (4.65, "very good"),
        (4.2, "good"),
        (3.7, "fair"),
        (3.1, "weak"),
        (2.4, "poor"),
    ],
)
def test_score_words(score: float, words: str) -> None:
    assert plain.score_words(score) == words


def test_score_text() -> None:
    assert plain.score_text(4.65) == "4.7/5 (very good)"


def test_low_band_reason_has_no_codes() -> None:
    why = plain.escalation_reason(
        "band Low", {"S1": 0.63, "S2": 1.0, "S3": 4.65, "S6": 0.0}, ["S1"]
    )
    assert "4.7/5 (very good)" in why and "63% of claims" in why
    assert "S1" not in why and "band" not in why


def test_budget_and_same_finding_reasons() -> None:
    assert "maximum number of retries" in plain.escalation_reason(
        "retry budget exhausted (verifier)", {}, []
    )
    assert "same major finding" in plain.escalation_reason("the same finding came back", {}, [])


def test_paused_messages_name_file_and_next_action() -> None:
    msg, nxt = plain.paused_input(2, "run_X", "runs/run_X/open-questions.md")
    assert "2 questions need" in msg
    assert nxt == (
        "Answer the questions in runs/run_X/open-questions.md, then run /truminds:resume run_X"
    )
    msg, nxt = plain.paused_approval("x", "run_X", "G-1", "runs/run_X/approvals.md")
    assert "edit runs/run_X/approvals.md" in nxt and "`tsl approve run_X G-1`" in nxt
    assert nxt.endswith("/truminds:resume run_X")
