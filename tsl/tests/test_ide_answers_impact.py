"""answers.logged with `with` params, as impact-analysis 1.2.0 uses it on impact.v1: answers decide
modules, apis, tables or claims (`decides`), not requirements. The intent.v1 form is covered,
unchanged, by test_ide_answers.py."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tsl.approvals import ide_answers
from tsl.harness.skillchecks import CheckEnv, run_declared

RUN = "run_01JA0B3C4D5E6F7G8H9JKMNPQR"
LOG = f"runs/{RUN}/ide-answers.md"
INTENT = f"artifacts/T-1/{RUN}/intent.md"
MODULE_MAP = "context/generated/module-map.json"
REORDER = "module:orders-web:src/pages/reorder"

CHECKS = {
    "schema": "skill-checks.v1",
    "skill": "impact-analysis",
    "artifact_schema": "impact.v1",
    "checks": [
        {
            "id": "IA-C01",
            "uses": "answers.logged",
            "gate": "H4",
            "with": {
                "targets": ["modules", "apis", "tables", "claims"],
                "field": "decides",
                "noun": "item",
            },
        }
    ],
}

Q01 = {
    "id": "Q-01",
    "blocking": False,
    "ask": "tech lead",
    "text": "Q-01: Which pages call GET /api/orders?",
    "why": "The generated facts have no call edges",
    "evidence": [f"{MODULE_MAP}#{REORDER}"],
    "default": "Only the order history page",
}


def _log(root: Path, entries: list[dict[str, Any]], attempt: int = 1) -> None:
    ide_answers.append(
        root / LOG, RUN, "impact", attempt, "t", "Jane <jane@example.com>", "toolu_1", entries
    )


def _world(tmp_path: Path) -> Path:
    (tmp_path / INTENT).parent.mkdir(parents=True)
    (tmp_path / INTENT).write_text("---\nschema: intent.v1\n---\n", encoding="utf-8")
    _log(
        tmp_path,
        [
            {
                "question": "Q-01: Which pages call GET /api/orders?",
                "options": ["Only the order history page", "Also the reorder page"],
                "answer": "Also the reorder page",
            }
        ],
    )
    return tmp_path


def _front(**over: Any) -> dict[str, Any]:
    f: dict[str, Any] = {
        "schema": "impact.v1",
        "run_id": RUN,
        "step": "impact",
        "attempt": 1,
        "claims": [],
        "questions": [],
        "modules": [
            {
                "id": REORDER,
                "change": "existing",
                "cites": [f"{MODULE_MAP}#{REORDER}", f"{LOG}#a-01"],
            }
        ],
        "apis": [
            {
                "id": "http:GET:/api/orders",
                "change": "changed",
                "cites": ["context/generated/api-inventory.json#http:GET:/api/orders"],
            }
        ],
        "tables": [],
        "answers": [
            {
                "id": "A-01",
                "kind": "question",
                "about": "Q-01",
                "answer": "Also the reorder page",
                "decides": [REORDER],
            }
        ],
    }
    f.update(over)
    return f


def _run(root: Path, front: dict[str, Any]) -> tuple[str, str]:
    env = CheckEnv(front, "", root, [INTENT], {}, {"intent": INTENT})
    out = {o.id: (o.status, o.detail) for o in run_declared(env, CHECKS)}
    return out["IA-C01"]


def test_module_decided_by_a_recorded_answer_passes(tmp_path: Path) -> None:
    assert _run(_world(tmp_path), _front()) == ("pass", "")


def test_module_that_does_not_cite_its_answer_fails(tmp_path: Path) -> None:
    f = _front()
    f["modules"][0]["cites"] = [f"{MODULE_MAP}#{REORDER}"]
    status, detail = _run(_world(tmp_path), f)
    assert status == "fail" and detail == f"{REORDER} does not cite {LOG}#a-01"


def test_dropping_a_recorded_answer_fails(tmp_path: Path) -> None:
    f = _front(answers=[])
    f["modules"][0]["cites"] = [f"{MODULE_MAP}#{REORDER}"]
    status, detail = _run(_world(tmp_path), f)
    assert status == "fail" and detail == "A-01 was answered by the user but is not in answers"


def test_answer_naming_an_unknown_item_uses_the_noun(tmp_path: Path) -> None:
    f = _front()
    f["answers"][0]["decides"] = ["module:orders-web:src/nowhere"]
    status, detail = _run(_world(tmp_path), f)
    assert status == "fail"
    assert detail == "A-01 names module:orders-web:src/nowhere, which is not an item"


def test_answer_that_decides_nothing_uses_the_noun(tmp_path: Path) -> None:
    f = _front()
    f["answers"][0]["decides"] = []
    f["modules"][0]["cites"] = [f"{MODULE_MAP}#{REORDER}"]
    status, detail = _run(_world(tmp_path), f)
    assert status == "fail" and "decides no item" in detail


def test_answered_claim_assumption_must_decide_its_own_claim(tmp_path: Path) -> None:
    root = _world(tmp_path)
    _log(
        root,
        [
            {
                "question": "C1: I assumed OrderHistoryPage also calls it. Right?",
                "options": ["Yes, confirm", "No"],
                "answer": "Yes, confirm",
            }
        ],
    )
    claim = {
        "id": "C1",
        "text": "`OrderHistoryPage` calls the changed route",
        "cites": ["context/architecture.md#components", f"{LOG}#a-02"],
    }
    f = _front(claims=[claim])
    f["answers"].append(
        {
            "id": "A-02",
            "kind": "assumption",
            "about": "C1",
            "answer": "Yes, confirm",
            "decides": [REORDER],
        }
    )
    f["modules"][0]["cites"].append(f"{LOG}#a-02")
    status, detail = _run(root, f)
    assert status == "fail" and detail == "A-02 answers the assumption in C1 but does not decide it"
    # Deciding its own claim (which cites the answer) passes.
    f["answers"][1]["decides"] = ["C1"]
    f["modules"][0]["cites"].remove(f"{LOG}#a-02")
    assert _run(root, f) == ("pass", "")


def test_dont_know_answer_keeps_its_question_open_and_passes(tmp_path: Path) -> None:
    root = tmp_path
    (root / INTENT).parent.mkdir(parents=True)
    (root / INTENT).write_text("---\nschema: intent.v1\n---\n", encoding="utf-8")
    _log(
        root,
        [
            {
                "question": "Q-01: Which pages call GET /api/orders?",
                "options": ["Only the order history page", "Also the reorder page"],
                "answer": "Don't know, ask the web lead",
            }
        ],
    )
    f = _front(questions=[Q01], modules=[])
    f["answers"][0]["answer"] = "Don't know, ask the web lead"
    f["answers"][0]["decides"] = []
    assert _run(root, f) == ("pass", "")


def test_answered_question_still_open_fails(tmp_path: Path) -> None:
    status, detail = _run(_world(tmp_path), _front(questions=[Q01]))
    assert status == "fail" and detail == "Q-01 was answered in A-01 but is still an open question"


def test_without_with_params_impact_items_are_not_decidable(tmp_path: Path) -> None:
    """The default form only knows requirements: a skill that sets no `with` keeps that behaviour."""
    checks = {**CHECKS, "checks": [{"id": "IA-C01", "uses": "answers.logged", "gate": "H4"}]}
    f = _front()
    f["answers"][0]["requirements"] = f["answers"][0].pop("decides")
    env = CheckEnv(f, "", _world(tmp_path), [INTENT], {}, {"intent": INTENT})
    (o,) = run_declared(env, checks)
    assert o.status == "fail" and o.detail == f"A-01 names {REORDER}, which is not a requirement"


def test_impact_cites_a_requirement_review_answer(tmp_path: Path) -> None:
    """B2: an answer the req step logged may be cited by impact as a decision already made."""
    root = _world(tmp_path)
    ide_answers.append(
        root / LOG,
        RUN,
        "req",
        1,
        "t",
        "Jane <jane@example.com>",
        "toolu_0",
        [{"question": "Q-01: Date only?", "options": [], "answer": "Date only, no time"}],
    )
    f = _front()
    f["claims"] = [{"id": "C1", "text": "The value is a date", "cites": [f"{LOG}#a-02"]}]
    out = run_declared(CheckEnv(f, "", root, [INTENT], {}, {"intent": INTENT}), CHECKS)
    assert [(o.status, o.detail) for o in out] == [("pass", "")]
