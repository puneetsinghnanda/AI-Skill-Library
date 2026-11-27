"""Calls into other roadmap items, made only when their code is installed (design A1 §7).

- D1 metrics: `tsl.metrics.on_phase` on every phase change, in both loop modes.
- B2 questions: `tsl.approvals.ide_questions.raised` when code mode returns `ask`.

Both are best effort: a missing module is skipped, and an error is logged (and for B2 returned
as a warning). Neither ever changes what `tsl next` returns.
"""

from __future__ import annotations

import importlib
import logging
from typing import Any

from tsl.core.clock import iso
from tsl.core.repo import Companion
from tsl.core.runtime import Runtime

log = logging.getLogger("tsl")

PHASES = (
    "run_step",
    "fix",
    "checks",
    "verifier",
    "run_reviewer",
    "record",
    "decide",
    "ask",
    "pause_approval",
    "pr",
    "done",
    "stopped",
)


def _module(name: str) -> Any:
    try:
        return importlib.import_module(name)
    except ImportError:
        return None


def phase(
    rt: Runtime,
    comp: Companion,
    state: dict[str, Any],
    step: str | None,
    attempt: int | None,
    name: str,
    *,
    outcome: str | None = None,
    agent_id: str | None = None,
) -> None:
    """D1: a phase starts (and ends the one before). `at` is an ISO UTC time from rt.clock()."""
    m = _module("tsl.metrics")
    if m is None or not hasattr(m, "on_phase"):
        return
    try:
        m.on_phase(
            comp,
            str(state["run_id"]),
            step,
            attempt,
            name,
            iso(rt.clock()),
            loop=str(state.get("run_loop") or "model"),
            outcome=outcome,
            session_id=rt.session_id(),
            agent_id=agent_id,
        )
    except Exception:  # best effort: metrics never change the run
        log.warning("metrics.on_phase failed for %s", name, exc_info=True)


def ask_raised(
    rt: Runtime,
    comp: Companion,
    run_id: str,
    step: str | None,
    attempt: int | None,
    questions: list[dict[str, Any]],
) -> list[dict[str, str]]:
    """B2: record the questions `ask` hands out. Returns warnings, never raises."""
    m = _module("tsl.approvals.ide_questions")
    if m is None or not hasattr(m, "raised") or not questions:
        return []
    try:
        m.raised(
            comp.root,
            run_id,
            step,
            attempt,
            [
                {
                    "id": q["id"],
                    "text": q.get("question") or "",
                    "options": list(q.get("options") or []),
                    "blocking": bool(q.get("blocking")),
                }
                for q in questions
            ],
            source="next",
            at=iso(rt.clock()),
        )
    except Exception as exc:  # a recording error never fails the run (B2 reply §1)
        log.warning("ide_questions.raised failed", exc_info=True)
        return [{"code": "E-INT-01", "message": f"questions not recorded (B2): {exc}"[:300]}]
    return []
