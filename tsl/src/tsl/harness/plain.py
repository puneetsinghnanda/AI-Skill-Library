"""Plain-words text for pauses: what happened, where to look, what to do next.

The codes and raw numbers stay in the JSON data; this text is for the person at the keyboard.

Score words (reviewer score S3, 1-5): 4.5 or more "very good", 4.0 to 4.49 "good",
3.5 to 3.99 "fair", 3.0 to 3.49 "weak", below 3.0 "poor".
"""

from __future__ import annotations

from typing import Any

SCORE_WORDS = ((4.5, "very good"), (4.0, "good"), (3.5, "fair"), (3.0, "weak"))


def score_words(score: float) -> str:
    for floor, word in SCORE_WORDS:
        if score >= floor:
            return word
    return "poor"


def score_text(score: float) -> str:
    """'4.7/5, very good'.

    The words are fixed cut-offs, independent of the profile's S3 threshold.
    """
    return f"{score:.1f}/5, {score_words(score)}"


def _pct(x: float) -> str:
    return f"{round(x * 100)}%"


def low_reasons_text(signals: dict[str, Any], reasons: list[str]) -> str:
    parts: list[str] = []
    s3 = signals.get("S3")
    if "S3" in reasons:
        parts.append(
            f"reviewer score {score_text(float(s3))}" if s3 is not None else "no reviewer score"
        )
    if "S1" in reasons:
        parts.append(f"only {_pct(float(signals['S1']))} of claims are backed by a verified source")
    if "S2" in reasons:
        parts.append(f"{_pct(float(signals['S2']))} of the writing checks passed")
    if "S6" in reasons:
        parts.append("the change is bigger than expected")
    return "; ".join(parts)


def escalation_reason(
    escalate_reason: str | None, signals: dict[str, Any], reasons: list[str]
) -> str:
    """Why the run needs a person to approve, in plain words."""
    r = escalate_reason or "band Low"
    if r == "band Low":
        detail = low_reasons_text(signals, reasons)
        return "overall quality came out low" + (f" ({detail})" if detail else "")
    if r.startswith("retry budget exhausted"):
        kind = "build, test or scan" if "verifier" in r else "quality checks"
        return f"the step still failed its {kind} after the maximum number of retries"
    if r == "the same finding came back":
        return "the reviewer raised the same major finding again after a retry"
    return r


def paused_input(n_blocking: int, run_id: str, questions_file: str) -> tuple[str, str]:
    if n_blocking < 1:
        return (
            "Paused: your answers are needed before the run can go on.",
            f"Answer the questions in {questions_file}, then run /truminds:resume {run_id}",
        )
    n = f"{n_blocking} question{'s' if n_blocking != 1 else ''}"
    return (
        f"Paused: {n} need{'' if n_blocking != 1 else 's'} your answer before the run can go on.",
        f"Answer the questions in {questions_file}, then run /truminds:resume {run_id}",
    )


def paused_approval(why: str, run_id: str, gate: str, approvals_file: str) -> tuple[str, str]:
    return (
        f"Paused: a person must approve before the run goes on, because {why}.",
        f"Approve: edit {approvals_file}, run `tsl approve {run_id} {gate}`, "
        f"then /truminds:resume {run_id}",
    )
