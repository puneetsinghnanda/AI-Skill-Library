"""B3: the step context carries the answers the user already gave in this run
(data.prior_answers), each with the cite to use. Never another run's answers, even of the same
ticket: runs are independent, and an artifact may not cite another run."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tsl.approvals import ide_answers
from tsl.harness.verify import prior_answers

RUN = "run_01JA0B3C4D5E6F7G8H9JKMNPQR"
OLD = "run_01J90B3C4D5E6F7G8H9JKMNPQR"
OTHER = "run_01J80B3C4D5E6F7G8H9JKMNPQR"


class Comp:
    def __init__(self, root: Path) -> None:
        self.root = root

    def path(self, rel: str) -> Path:
        return self.root / rel


def _state(root: Path, rid: str, ticket: str, status: str, end: str | None) -> None:
    p = root / "runs" / rid / "state.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    st: dict[str, Any] = {
        "run_id": rid,
        "ticket": ticket,
        "status": status,
        "end_reason": end,
        "updated_at": "2026-11-01T00:00:00Z",
    }
    p.write_text(json.dumps(st), encoding="utf-8")


def _ask(root: Path, rid: str, step: str, attempt: int, q: str, a: str) -> None:
    ide_answers.append(
        root / "runs" / rid / "ide-answers.md",
        rid,
        step,
        attempt,
        "t",
        "Jane <jane@example.com>",
        "toolu",
        [{"question": q, "options": [], "answer": a}],
    )


def test_prior_answers_come_from_this_run_only(tmp_path: Path) -> None:
    _state(tmp_path, RUN, "HMS-4", "RUNNING", None)
    _state(tmp_path, OLD, "HMS-4", "COMPLETED", "cancelled")
    _state(tmp_path, OTHER, "HMS-9", "COMPLETED", "completed")
    _ask(tmp_path, RUN, "req", 1, "Q-01: Date only?", "Date only")
    _ask(tmp_path, RUN, "design", 1, "Q-01: Field name?", "last_visit_on")
    _ask(tmp_path, OLD, "impact", 1, "Q-02: Callers of GET /api/patients?", "PatientsPage only")
    _ask(tmp_path, OTHER, "req", 1, "Q-01: Unrelated?", "x")

    got = prior_answers(Comp(tmp_path), RUN, "HMS-4", "design", 2)  # type: ignore[arg-type]
    assert [g["cite"] for g in got] == [
        f"runs/{RUN}/ide-answers.md#a-01",
        f"runs/{RUN}/ide-answers.md#a-02",  # an earlier attempt of this step
    ]  # the ended run of the same ticket (OLD) is not offered


def test_this_attempts_own_answers_are_left_out(tmp_path: Path) -> None:
    _state(tmp_path, RUN, "HMS-4", "RUNNING", None)
    _ask(tmp_path, RUN, "design", 1, "Q-01: Field name?", "last_visit_on")
    assert prior_answers(Comp(tmp_path), RUN, "HMS-4", "design", 1) == []  # type: ignore[arg-type]


def test_another_runs_answer_is_not_an_allowed_cite(tmp_path: Path) -> None:
    from tsl.harness.skillchecks import CheckEnv, c_cites_present

    _ask(tmp_path, OLD, "impact", 1, "Q-02: Callers?", "PatientsPage only")
    _ask(tmp_path, RUN, "req", 1, "Q-01: Date only?", "Date only")
    front: dict[str, Any] = {
        "run_id": RUN,
        "claims": [{"id": "C1", "text": "x", "cites": [f"runs/{OLD}/ide-answers.md#a-01"]}],
    }
    assert "not a declared input" in str(c_cites_present(CheckEnv(front, "", tmp_path, [], {}), {}))
    front["claims"][0]["cites"] = [f"runs/{RUN}/ide-answers.md#a-01"]  # this run's own answer
    assert c_cites_present(CheckEnv(front, "", tmp_path, [], {}), {}) is None
