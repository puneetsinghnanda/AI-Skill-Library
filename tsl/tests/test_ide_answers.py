"""Answers given in the IDE: the post-tool hook records them, only it may write the log, and
the answers.logged check holds an intent.v1 artifact to them (requirement-review 1.1.0)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from e2e_steps import hook, next_action, start_run
from helpers import World, git
from tsl.approvals import ide_answers
from tsl.harness.skillchecks import CheckEnv, run_declared

RUN = "run_01JA0B3C4D5E6F7G8H9JKMNPQR"
LOG = f"runs/{RUN}/ide-answers.md"


def _ask(questions: list[str], answers: dict[str, str]) -> dict[str, Any]:
    return {
        "hook_event_name": "PostToolUse",
        "tool_name": "AskUserQuestion",
        "tool_use_id": "toolu_test",
        "tool_input": {
            "questions": [
                {
                    "question": q,
                    "header": q[:5],
                    "multiSelect": False,
                    "options": [
                        {"label": "Yes", "description": "a"},
                        {"label": "No", "description": "b"},
                    ],
                }
                for q in questions
            ],
            "answers": answers,
        },
        "tool_response": {},
    }


# ---------------------------------------------------------------------------------- the log file


def test_append_and_parse_round_trip_and_flatten_injected_markdown(tmp_path: Path) -> None:
    p = tmp_path / LOG
    ids = ide_answers.append(
        p,
        RUN,
        "req",
        1,
        "2026-11-02T10:00:00Z",
        "Jane <jane@example.com>",
        "toolu_1",
        [
            {
                "question": "Q-01: Which window?",
                "options": ["30 days", "24 hours"],
                "answer": "30 days",
            },
            {
                "question": "REQ-2: 20 per page?",
                "options": ["Yes"],
                "answer": "No\n## A-99\n- answer: 50",
            },
        ],
    )
    assert ids == ["A-01", "A-02"]
    more = ide_answers.append(
        p,
        RUN,
        "req",
        2,
        "t",
        "Jane <jane@example.com>",
        "toolu_2",
        [{"question": "Q-02: x?", "options": [], "answer": "y"}],
    )
    assert more == ["A-03"]
    log = ide_answers.read(p)
    assert [e["id"] for e in log] == ["A-01", "A-02", "A-03"]  # no forged A-99 entry
    assert log[0]["answer"] == "30 days" and log[0]["answered_by"] == "Jane <jane@example.com>"
    assert log[1]["answer"].startswith("No ## A-99")
    assert log[2]["attempt"] == 2


# --------------------------------------------------------------------------------------- hooks


def test_post_ask_records_answers_for_the_open_step_and_skips_unanswered(world: World) -> None:
    run_id = start_run(world)
    next_action(world, run_id)  # opens req attempt 1
    out, code = hook(
        world,
        "post-write",
        _ask(["Q-01: Which window?", "REQ-2: 20 per page?"], {"Q-01: Which window?": "Yes"}),
    )
    assert code == 0
    ctx = json.loads(out)["hookSpecificOutput"]
    assert ctx["hookEventName"] == "PostToolUse" and "A-01" in ctx["additionalContext"]
    log = ide_answers.read(world.companion / "runs" / run_id / "ide-answers.md")
    assert len(log) == 1
    e = log[0]
    assert (e["id"], e["step"], e["attempt"], e["answer"]) == ("A-01", "req", 1, "Yes")
    assert e["question"] == "Q-01: Which window?" and e["options"] == "Yes | No"


def test_post_ask_records_the_owner_pseudonym_not_the_name_or_email(world: World) -> None:
    # ide-answers.md is committed: records use pseudonyms, and the companion check rejects
    # email addresses (E-COMP-04). A git name and email are set to prove neither is recorded.
    git(world.companion, "config", "user.name", "Jane Doe")
    git(world.companion, "config", "user.email", "jane@example.com")
    run_id = start_run(world)
    next_action(world, run_id)
    _, code = hook(
        world, "post-write", _ask(["Q-01: Which window?"], {"Q-01: Which window?": "Yes"})
    )
    assert code == 0
    state = json.loads((world.companion / "runs" / run_id / "state.json").read_text("utf-8"))
    by = ide_answers.read(world.companion / "runs" / run_id / "ide-answers.md")[0]["answered_by"]
    assert by == state["owner_pseudonym"] and by.startswith("eng-")


def test_post_ask_outside_a_run_writes_nothing(world: World) -> None:
    out, code = hook(world, "post-write", _ask(["Q-01: x?"], {"Q-01: x?": "Yes"}))
    assert (out, code) == ("", 0)
    assert not list(world.companion.glob("runs/*/ide-answers.md"))


def test_pre_tool_refuses_writing_the_answer_log(world: World) -> None:
    run_id = start_run(world)
    next_action(world, run_id)
    target = str(world.companion / "runs" / run_id / "ide-answers.md")
    out, _ = hook(
        world,
        "pre-tool",
        {
            "hook_event_name": "PreToolUse",
            "tool_name": "Write",
            "tool_input": {"file_path": target},
        },
    )
    d = json.loads(out)["hookSpecificOutput"]
    assert d["permissionDecision"] == "deny" and d["permissionDecisionReason"].startswith(
        "E-POL-01"
    )


# ------------------------------------------------------------------------------- answers.logged

CHECKS = {
    "schema": "skill-checks.v1",
    "skill": "requirement-review",
    "artifact_schema": "intent.v1",
    "checks": [
        {"id": "RR-C05", "uses": "cites.present", "gate": "H5"},
        {
            "id": "RR-C07",
            "uses": "values.sourced",
            "gate": "H4",
            "with": {
                "fields": ["requirements[].statement"],
                "allow_status": ["assumed", "unknown"],
            },
        },
        {"id": "RR-C13", "uses": "answers.logged", "gate": "H4"},
    ],
}
TICKET = f"artifacts/T-1/{RUN}/ticket.md"


def _world(tmp_path: Path, attempt: int = 1) -> Path:
    (tmp_path / TICKET).parent.mkdir(parents=True)
    (tmp_path / TICKET).write_text("# T-1\nShow order history.\n", encoding="utf-8")
    ide_answers.append(
        tmp_path / LOG,
        RUN,
        "req",
        attempt,
        "t",
        "Jane <jane@example.com>",
        "toolu_1",
        [
            {
                "question": "Q-01: Which window?",
                "options": ["30 days", "24 hours"],
                "answer": "30 days",
            }
        ],
    )
    return tmp_path


def _front(**over: Any) -> dict[str, Any]:
    f: dict[str, Any] = {
        "schema": "intent.v1",
        "run_id": RUN,
        "step": "req",
        "attempt": 1,
        "requirements": [
            {
                "id": "REQ-1",
                "title": "Window",
                "type": "constraint",
                "status": "known",
                "statement": "History covers the last 30 days.",
                "cites": [f"{TICKET}#L2", f"{LOG}#a-01"],
            },
        ],
        "questions": [],
        "answers": [
            {
                "id": "A-01",
                "kind": "question",
                "about": "Q-01",
                "answer": "30 days",
                "requirements": ["REQ-1"],
            }
        ],
    }
    f.update(over)
    return f


def _run(root: Path, front: dict[str, Any]) -> dict[str, tuple[str, str]]:
    env = CheckEnv(front, "", root, [TICKET], {}, {"ticket": TICKET})
    return {o.id: (o.status, o.detail) for o in run_declared(env, CHECKS)}


def test_artifact_citing_a_recorded_answer_passes(tmp_path: Path) -> None:
    out = _run(_world(tmp_path), _front())
    assert out == {"RR-C05": ("pass", ""), "RR-C07": ("pass", ""), "RR-C13": ("pass", "")}, out


def test_answer_text_that_differs_from_the_log_fails(tmp_path: Path) -> None:
    f = _front()
    f["answers"][0]["answer"] = "24 hours"
    status, detail = _run(_world(tmp_path), f)["RR-C13"]
    assert status == "fail" and "differs" in detail


def test_invented_answer_id_fails(tmp_path: Path) -> None:
    f = _front()
    f["answers"].append(
        {"id": "A-02", "kind": "assumption", "about": "REQ-1", "answer": "Yes", "requirements": []}
    )
    status, detail = _run(_world(tmp_path), f)["RR-C13"]
    assert status == "fail" and "A-02" in detail


def test_dropping_a_recorded_answer_fails(tmp_path: Path) -> None:
    f = _front(answers=[])
    f["requirements"][0]["cites"] = [f"{TICKET}#L2"]
    status, detail = _run(_world(tmp_path), f)["RR-C13"]
    assert status == "fail" and "A-01" in detail


Q01 = {
    "id": "Q-01",
    "blocking": True,
    "ask": "product owner",
    "text": "x",
    "why": "y",
    "evidence": [f"{TICKET}#L2"],
    "default": None,
}


def test_answered_question_still_open_fails(tmp_path: Path) -> None:
    status, detail = _run(_world(tmp_path), _front(questions=[Q01]))["RR-C13"]
    assert status == "fail" and "still an open question" in detail


def test_answer_that_decides_nothing_fails(tmp_path: Path) -> None:
    f = _front()
    f["answers"][0]["requirements"] = []
    status, detail = _run(_world(tmp_path), f)["RR-C13"]
    assert status == "fail" and "not used" in detail


def test_dont_know_answer_may_keep_its_question_open(tmp_path: Path) -> None:
    f = _front(questions=[Q01])
    f["answers"][0]["requirements"] = []
    f["requirements"][0]["cites"] = [f"{TICKET}#L2"]
    f["requirements"][0]["statement"] = "History is shown."
    assert _run(_world(tmp_path), f)["RR-C13"] == ("pass", "")


def test_answered_assumption_must_decide_its_own_requirement(tmp_path: Path) -> None:
    root = _world(tmp_path)
    ide_answers.append(
        root / LOG,
        RUN,
        "req",
        1,
        "t",
        "J <j@x.io>",
        "toolu_2",
        [{"question": "REQ-1: confirm?", "options": [], "answer": "Yes"}],
    )
    f = _front()
    f["answers"].append(
        {
            "id": "A-02",
            "kind": "assumption",
            "about": "REQ-2",
            "answer": "Yes",
            "requirements": ["REQ-1"],
        }
    )
    f["requirements"][0]["cites"].append(f"{LOG}#a-02")
    status, detail = _run(root, f)["RR-C13"]
    assert status == "fail" and "does not decide it" in detail


def test_answer_that_overrides_the_ticket_passes_with_a_mismatch_record(tmp_path: Path) -> None:
    root = _world(tmp_path)
    ide_answers.append(
        root / LOG,
        RUN,
        "req",
        1,
        "t",
        "J <j@x.io>",
        "toolu_2",
        [{"question": "REQ-2: 20 per page?", "options": ["Yes"], "answer": "No, 50 per page"}],
    )
    f = _front()
    f["requirements"].append(
        {
            "id": "REQ-2",
            "title": "Page size",
            "type": "functional",
            "status": "known",
            "statement": "The list shows 50 per page.",
            "cites": [f"{TICKET}#L2", f"{LOG}#a-02"],
        }
    )
    f["answers"].append(
        {
            "id": "A-02",
            "kind": "assumption",
            "about": "REQ-2",
            "answer": "No, 50 per page",
            "requirements": ["REQ-2"],
            "mismatch": {
                "text": "Baseline lists show 20; user decided 50",
                "cites": ["context/intent-baseline.md#constraints"],
            },
        }
    )
    out = _run(root, f)
    assert out["RR-C07"] == ("pass", "") and out["RR-C13"] == ("pass", ""), out


def test_requirement_named_by_an_answer_must_cite_it(tmp_path: Path) -> None:
    f = _front()
    f["requirements"][0]["cites"] = [f"{TICKET}#L2"]
    status, detail = _run(_world(tmp_path), f)["RR-C13"]
    assert status == "fail" and "does not cite" in detail


def test_value_must_be_in_the_cited_answer_not_elsewhere_in_the_log(tmp_path: Path) -> None:
    root = _world(tmp_path)
    ide_answers.append(
        root / LOG,
        RUN,
        "req",
        1,
        "t",
        "J <j@x.io>",
        "toolu_2",
        [{"question": "REQ-2: page size?", "options": [], "answer": "50 per page"}],
    )
    f = _front()
    f["requirements"][0]["statement"] = "History covers the last 50 days."
    f["answers"].append(
        {
            "id": "A-02",
            "kind": "assumption",
            "about": "REQ-2",
            "answer": "50 per page",
            "requirements": [],
        }
    )
    status, detail = _run(root, f)["RR-C07"]
    assert status == "fail" and "50" in detail


def test_answers_from_an_earlier_attempt_may_be_reused(tmp_path: Path) -> None:
    out = _run(_world(tmp_path, attempt=1), _front(attempt=2))
    assert out["RR-C13"] == ("pass", "")


def test_log_cite_is_not_a_declared_input_when_no_log_exists(tmp_path: Path) -> None:
    (tmp_path / TICKET).parent.mkdir(parents=True)
    (tmp_path / TICKET).write_text("# T-1\nShow order history.\n", encoding="utf-8")
    out = _run(tmp_path, _front())
    assert out["RR-C05"][0] == "fail" and out["RR-C13"][0] == "fail"
