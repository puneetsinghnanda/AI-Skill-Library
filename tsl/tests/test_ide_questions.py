"""Questions asked in the IDE are recorded in tsl with when each was asked and answered (roadmap
B2): the pre-tool hook opens an ask when the AskUserQuestion dialog opens, the post-tool hook
marks it answered, a dismissed dialog is closed by the next tool call, and --progress shows the
open ones and the engineer's wait per step."""

from __future__ import annotations

import json
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any

import pytest

from e2e_steps import SESSION, hook, next_action, start_run
from helpers import World
from tsl.approvals import ide_answers, ide_questions
from tsl.core.errors import TslError
from tsl.hooks import pre_tool

RUN = "run_01JA0B3C4D5E6F7G8H9JKMNPQR"
QS = [
    {"id": "Q-01", "text": "Q-01: Which window?", "options": ["30 days", "24 hours"]},
    {"id": "Q-02", "text": "Q-02: 20 per page?", "options": ["Yes", "No"]},
]


def _tool_input(questions: list[str]) -> dict[str, Any]:
    return {
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
        ]
    }


def _pre_ask(questions: list[str], tool_use_id: str = "toolu_1", **extra: Any) -> dict[str, Any]:
    return {
        "hook_event_name": "PreToolUse",
        "tool_name": "AskUserQuestion",
        "tool_use_id": tool_use_id,
        "tool_input": _tool_input(questions),
        **extra,
    }


def _post_ask(
    questions: list[str], answers: dict[str, str], tool_use_id: str = "toolu_1"
) -> dict[str, Any]:
    return {
        "hook_event_name": "PostToolUse",
        "tool_name": "AskUserQuestion",
        "tool_use_id": tool_use_id,
        "tool_input": {**_tool_input(questions), "answers": answers},
        "tool_response": {},
    }


def _other_tool(**extra: Any) -> dict[str, Any]:
    return {
        "hook_event_name": "PreToolUse",
        "tool_name": "TodoWrite",
        "tool_use_id": "toolu_9",
        "tool_input": {"todos": []},
        **extra,
    }


def _progress(world: World) -> dict[str, Any]:
    code, env, _, err = world.cli(["state", "show", "--progress", "--json"], session=SESSION)
    assert code == 0 and env is not None, (env, err)
    return dict(env["data"]["progress"])


def _asks(world: World, run_id: str) -> list[dict[str, Any]]:
    return list(ide_questions.load(world.companion, run_id)["asks"])


# ---------------------------------------------------------------------------------- the record


def test_raise_answer_close_and_the_wait_per_step(tmp_path: Path) -> None:
    a1 = ide_questions.raised(
        tmp_path, RUN, "req", 1, QS, source="hook", at="2026-11-25T10:00:00Z", tool_use_id="t1"
    )
    assert a1 == "ASK-01"
    # The same call reported twice (tsl next and the hook) is one ask.
    again = ide_questions.raised(tmp_path, RUN, "req", 1, QS, source="next", tool_use_id="t1")
    assert again == a1 and len(ide_questions.load(tmp_path, RUN)["asks"]) == 1
    assert [a["ask_id"] for a in ide_questions.open_asks(tmp_path, RUN)] == [a1]

    ids = ide_questions.answered(
        tmp_path,
        RUN,
        a1,
        [{"question": "Q-01: Which window?", "options": ["30 days"], "answer": "30 days"}],
        answered_by="eng-4f2a",
        at="2026-11-25T10:01:30Z",
    )
    assert ids == ["A-01"]
    ask = ide_questions.load(tmp_path, RUN)["asks"][0]
    assert (ask["status"], ask["answered_at"], ask["answers"]) == (
        "answered",
        "2026-11-25T10:01:30Z",
        ["A-01"],
    )
    # ide-answers.md gets the real ask time, not the answer time.
    e = ide_answers.read(tmp_path / f"runs/{RUN}/ide-answers.md")[0]
    assert (e["asked_at"], e["answered_at"]) == ("2026-11-25T10:00:00Z", "2026-11-25T10:01:30Z")

    a2 = ide_questions.raised(
        tmp_path, RUN, "split", 1, QS[:1], source="hook", at="2026-11-25T11:00:00Z"
    )
    ide_questions.closed(tmp_path, RUN, a2, reason="dismissed", at="2026-11-25T11:00:20Z")
    ide_questions.closed(tmp_path, RUN, a2, reason="later", at="2026-11-25T12:00:00Z")  # no-op
    assert ide_questions.load(tmp_path, RUN)["asks"][1]["close_reason"] == "dismissed"
    a3 = ide_questions.raised(
        tmp_path, RUN, "split", 2, QS[:1], source="hook", at="2026-11-25T11:05:00Z"
    )
    assert a3 == "ASK-03"
    # Answered or closed asks count to their end; an open one counts up to now.
    w = ide_questions.waits(tmp_path, RUN, now="2026-11-25T11:05:40Z")
    assert w == {"total_s": 90 + 20 + 40, "steps": {"req": 90, "split": 60}}


def test_next_raises_then_the_dialog_stamps_the_real_ask_time(tmp_path: Path) -> None:
    a = ide_questions.raised(tmp_path, RUN, "req", 1, QS, source="next", at="2026-11-25T10:00:00Z")
    b = ide_questions.raised(
        tmp_path, RUN, "req", 1, QS, source="hook", at="2026-11-25T10:00:07Z", tool_use_id="t1"
    )
    ask = ide_questions.load(tmp_path, RUN)["asks"]
    assert a == b and len(ask) == 1
    assert (ask[0]["tool_use_id"], ask[0]["asked_at"]) == ("t1", "2026-11-25T10:00:07Z")
    assert (
        ide_questions.find(tmp_path, RUN, "t1") == a
        and ide_questions.find(tmp_path, RUN, "") is None
    )


def test_asking_again_closes_the_dismissed_dialog_and_starts_a_new_wait(tmp_path: Path) -> None:
    # HMS-27: Esc on the dialog stopped the turn; the model's next call asked the same
    # questions again. The first ask ends there, and the wait restarts with the new dialog.
    a = ide_questions.raised(
        tmp_path, RUN, "design", 1, QS, source="hook", at="2026-11-25T13:03:12Z", tool_use_id="t1"
    )
    b = ide_questions.raised(
        tmp_path, RUN, "design", 1, QS, source="hook", at="2026-11-25T13:09:38Z", tool_use_id="t2"
    )
    assert (a, b) == ("ASK-01", "ASK-02")
    first, second = ide_questions.load(tmp_path, RUN)["asks"]
    assert (first["status"], first["closed_at"], first["close_reason"]) == (
        "closed",
        "2026-11-25T13:09:38Z",
        "dismissed",
    )
    assert (second["status"], second["asked_at"]) == ("open", "2026-11-25T13:09:38Z")
    # tsl next reporting the questions now joins the open dialog, it does not add a third.
    assert ide_questions.raised(tmp_path, RUN, "design", 1, QS, source="next") == b
    # Another agent's dialog leaves this one open.
    ide_questions.raised(
        tmp_path, RUN, "ut", 1, QS[:1], source="hook", tool_use_id="t3", agent_id="ag1"
    )
    assert [x["ask_id"] for x in ide_questions.open_asks(tmp_path, RUN)] == ["ASK-02", "ASK-03"]
    ide_questions.answered(
        tmp_path,
        RUN,
        b,
        [{"question": "Q-01: Which window?", "options": [], "answer": "x"}],
        answered_by="eng-4f2a",
        at="2026-11-25T13:10:56Z",
    )
    w = ide_questions.waits(tmp_path, RUN, now="2026-11-25T13:10:56Z")
    assert w["steps"]["design"] == 386 + 78  # the dismissed dialog, then the answered one


def test_question_ids_come_from_the_text() -> None:
    got = ide_questions.questions_of(_tool_input(["Q-01: x?", "C7: y?", "REQ-9 - z?", "Plain?"]))
    assert [q["id"] for q in got] == ["Q-01", "C7", "REQ-9", "ASK-4"]
    assert got[0]["options"] == ["Yes", "No"] and all(q["blocking"] for q in got)


def test_close_open_keeps_other_agents_and_parallel_calls(tmp_path: Path) -> None:
    ide_questions.raised(tmp_path, RUN, "req", 1, QS[:1], source="hook", at="2026-11-25T10:00:00Z")
    ide_questions.raised(
        tmp_path, RUN, "ut", 1, QS[1:], source="hook", at="2026-11-25T10:00:00Z", agent_id="ag1"
    )
    kw: dict[str, Any] = {"reason": "dismissed", "older_than_s": 10}
    assert ide_questions.close_open(tmp_path, RUN, at="2026-11-25T10:00:03Z", **kw) == 0
    assert ide_questions.close_open(tmp_path, RUN, at="2026-11-25T10:00:30Z", **kw) == 1
    assert [a["step"] for a in ide_questions.open_asks(tmp_path, RUN)] == ["ut"]
    assert (
        ide_questions.close_open(tmp_path, RUN, agent_id="ag1", at="2026-11-25T10:00:30Z", **kw)
        == 1
    )
    assert ide_questions.close_open(tmp_path / "none", RUN, **kw) == 0  # no file: nothing read


def test_a_broken_record_reads_as_empty(tmp_path: Path) -> None:
    p = tmp_path / f"runs/{RUN}/ide-questions.json"
    p.parent.mkdir(parents=True)
    for bad in ("<<<<<<< HEAD", "[]", '{"asks": 3}'):
        p.write_text(bad, encoding="utf-8")
        assert ide_questions.load(tmp_path, RUN)["asks"] == []
        assert ide_questions.waits(tmp_path, RUN) == {"total_s": 0, "steps": {}}


# --------------------------------------------------------------------------------------- hooks


def test_an_ask_is_shown_while_open_and_its_wait_recorded_once_answered(world: World) -> None:
    run_id = start_run(world)
    next_action(world, run_id)  # opens req attempt 1
    qs = ["Q-01: Which window?", "Q-02: 20 per page?"]
    out, code = hook(world, "pre-tool", _pre_ask(qs))
    assert (out, code) == ("", 0)  # recording never changes the decision
    [ask] = _asks(world, run_id)
    assert (ask["status"], ask["step"], ask["attempt"], ask["tool_use_id"]) == (
        "open",
        "req",
        1,
        "toolu_1",
    )

    q = _progress(world)["questions"]
    assert q["open_ide"] == 2
    assert [(i["id"], i["ask"], i["blocking"]) for i in q["items"][:2]] == [
        ("Q-01", "ide", True),
        ("Q-02", "ide", True),
    ]
    assert q["items"][0]["since"] == ask["asked_at"]
    assert q["items"][0]["text"] == "Which window?"  # the id is not repeated in the text

    out, code = hook(world, "post-write", _post_ask(qs, {qs[0]: "Yes", qs[1]: "No"}))
    assert code == 0 and "A-02" in json.loads(out)["hookSpecificOutput"]["additionalContext"]
    [ask] = _asks(world, run_id)
    assert ask["status"] == "answered" and ask["answers"] == ["A-01", "A-02"]
    log = ide_answers.read(world.companion / "runs" / run_id / "ide-answers.md")
    assert [e["asked_at"] for e in log] == [ask["asked_at"]] * 2
    assert [e["answered_at"] for e in log] == [ask["answered_at"]] * 2

    p = _progress(world)
    assert p["questions"]["open_ide"] == 0 and not p["questions"]["items"]
    assert set(p["wait"]["steps"]) == {"req"} and p["wait"]["total_s"] >= 0


def test_a_dismissed_dialog_is_closed_by_the_next_tool_call(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(pre_tool, "ASK_CLOSE_AFTER_S", 0)
    run_id = start_run(world)
    next_action(world, run_id)
    hook(world, "pre-tool", _pre_ask(["Q-01: Which window?"]))
    # A subagent's tool call is not the main session going on: the ask stays open.
    assert hook(world, "pre-tool", _other_tool(agent_id="ag1"))[0] == ""
    assert _asks(world, run_id)[0]["status"] == "open"
    assert hook(world, "pre-tool", _other_tool())[0] == ""
    [ask] = _asks(world, run_id)
    assert (ask["status"], ask["close_reason"]) == ("closed", "dismissed") and ask["closed_at"]
    assert _progress(world)["questions"]["open_ide"] == 0


def test_every_question_skipped_closes_the_ask(world: World) -> None:
    run_id = start_run(world)
    next_action(world, run_id)
    hook(world, "pre-tool", _pre_ask(["Q-01: Which window?"]))
    assert hook(world, "post-write", _post_ask(["Q-01: Which window?"], {})) == ("", 0)
    [ask] = _asks(world, run_id)
    assert (ask["status"], ask["close_reason"]) == ("closed", "skipped")
    assert not (world.companion / "runs" / run_id / "ide-answers.md").exists()


def test_answers_without_a_pre_tool_record_are_still_recorded(world: World) -> None:
    run_id = start_run(world)
    next_action(world, run_id)
    hook(world, "post-write", _post_ask(["Q-01: Which window?"], {"Q-01: Which window?": "Yes"}))
    [ask] = _asks(world, run_id)
    assert ask["status"] == "answered" and ask["asked_at"] == ask["answered_at"]


def test_a_recording_error_still_allows_the_dialog(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(*_a: Any, **_k: Any) -> str:
        raise OSError("disk full")

    monkeypatch.setattr(ide_questions, "raised", boom)
    run_id = start_run(world)
    next_action(world, run_id)
    assert hook(world, "pre-tool", _pre_ask(["Q-01: Which window?"])) == ("", 0)


def test_pre_tool_refuses_writing_the_question_record(world: World) -> None:
    run_id = start_run(world)
    next_action(world, run_id)
    target = str(world.companion / "runs" / run_id / "ide-questions.json")
    for tool in ("Write", "Edit"):
        out, _ = hook(
            world,
            "pre-tool",
            {
                "hook_event_name": "PreToolUse",
                "tool_name": tool,
                "tool_input": {"file_path": target},
            },
        )
        d = json.loads(out)["hookSpecificOutput"]
        assert d["permissionDecision"] == "deny"
        assert d["permissionDecisionReason"].startswith("E-POL-01 Blocked: ide-questions.json")


# ------------------------------------------------------------------- answers file (no dialog)


def _answers_file(tmp_path: Path, obj: Any) -> Path:
    p = tmp_path / "answers.json"
    p.write_text(obj if isinstance(obj, str) else json.dumps(obj), encoding="utf-8")
    return p


def test_an_answers_file_is_recorded_against_its_ask(tmp_path: Path) -> None:
    ask = ide_questions.raised(
        tmp_path, RUN, "req", 1, QS, source="next", at="2026-11-25T10:00:00Z"
    )
    f = _answers_file(
        tmp_path,
        {
            "schema": "ide-answers-input.v1",
            "ask_id": ask,
            "answers": [{"id": "Q-02", "answer": "No"}],
        },
    )
    kw: dict[str, Any] = {"answered_by": "eng-4f2a", "at": "2026-11-25T10:02:00Z"}
    assert ide_questions.answered_from_file(tmp_path, RUN, f, **kw) == ["A-01"]
    e = ide_answers.read(tmp_path / f"runs/{RUN}/ide-answers.md")[0]
    assert (e["question"], e["options"], e["answer"]) == ("Q-02: 20 per page?", "Yes | No", "No")
    assert e["asked_at"] == "2026-11-25T10:00:00Z"
    # Repeated: the same A-ids, nothing added.
    assert ide_questions.answered_from_file(tmp_path, RUN, f, **kw) == ["A-01"]
    assert len(ide_answers.read(tmp_path / f"runs/{RUN}/ide-answers.md")) == 1


def test_an_empty_answers_file_closes_the_ask_as_skipped(tmp_path: Path) -> None:
    ask = ide_questions.raised(tmp_path, RUN, "req", 1, QS, source="next")
    f = _answers_file(tmp_path, {"schema": "ide-answers-input.v1", "ask_id": ask, "answers": []})
    assert ide_questions.answered_from_file(tmp_path, RUN, f, answered_by="eng-4f2a") == []
    assert ide_questions.load(tmp_path, RUN)["asks"][0]["close_reason"] == "skipped"


@pytest.mark.parametrize(
    ("body", "pointer"),
    [
        ("not json", "/"),
        ({"schema": "x", "ask_id": "ASK-01", "answers": []}, "/schema"),
        ({"schema": "ide-answers-input.v1", "ask_id": "ASK-09", "answers": []}, "/ask_id"),
        ({"schema": "ide-answers-input.v1", "ask_id": "ASK-01", "answers": {}}, "/answers"),
        ({"schema": "ide-answers-input.v1", "ask_id": "ASK-01", "answers": ["Yes"]}, "/answers/0"),
        (
            {
                "schema": "ide-answers-input.v1",
                "ask_id": "ASK-01",
                "answers": [{"id": "Q-07", "answer": "x"}],
            },
            "/answers/0/id",
        ),
        (
            {
                "schema": "ide-answers-input.v1",
                "ask_id": "ASK-01",
                "answers": [{"id": "Q-01", "answer": "a"}, {"id": "Q-01", "answer": "b"}],
            },
            "/answers/1/id",
        ),
        (
            {
                "schema": "ide-answers-input.v1",
                "ask_id": "ASK-01",
                "answers": [{"id": "Q-01", "answer": " "}],
            },
            "/answers/0/answer",
        ),
    ],
)
def test_a_bad_answers_file_is_refused_with_where(tmp_path: Path, body: Any, pointer: str) -> None:
    ide_questions.raised(tmp_path, RUN, "req", 1, QS, source="next")
    f = _answers_file(tmp_path, body)
    with pytest.raises(TslError) as exc:
        ide_questions.answered_from_file(tmp_path, RUN, f, answered_by="eng-4f2a")
    assert exc.value.code == "E-CFG-01" and f" {pointer} " in str(exc.value), str(exc.value)
    assert not (tmp_path / f"runs/{RUN}/ide-answers.md").exists()


def test_a_closed_ask_takes_no_answers_file(tmp_path: Path) -> None:
    ask = ide_questions.raised(tmp_path, RUN, "req", 1, QS, source="next")
    ide_questions.closed(tmp_path, RUN, ask, reason="dismissed")
    f = _answers_file(
        tmp_path,
        {
            "schema": "ide-answers-input.v1",
            "ask_id": ask,
            "answers": [{"id": "Q-01", "answer": "Yes"}],
        },
    )
    with pytest.raises(TslError, match="closed, not open"):
        ide_questions.answered_from_file(tmp_path, RUN, f, answered_by="eng-4f2a")


# ----------------------------------------------------------------- review of #67 (Ekjot, 26 Nov)


def test_an_ask_between_steps_is_answered_not_dismissed(world: World) -> None:
    # After state start and before the first tsl next the run has no open step: the pre-tool
    # hook records the ask under "run", and the post-tool hook must finish that same ask.
    run_id = start_run(world)
    qs = ["Q-01: Which window?"]
    hook(world, "pre-tool", _pre_ask(qs))
    out, code = hook(world, "post-write", _post_ask(qs, {qs[0]: "Yes"}))
    assert code == 0 and "A-01" in out
    [ask] = _asks(world, run_id)
    assert (ask["step"], ask["status"], ask["answers"]) == ("run", "answered", ["A-01"])
    assert _progress(world)["questions"]["open_ide"] == 0


def test_parallel_writers_keep_every_ask(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Parallel agents' hooks at once: each load, change and save is locked, so no ask is lost
    # and no two get the same id. This checks that writers exclude each other, not how fast a
    # slow CI disk is, so the wait limit is raised here; giving up at the limit is tested below.
    monkeypatch.setattr(ide_questions, "LOCK_WAIT_S", 60.0)
    errors: list[BaseException] = []
    # How many writers are between their load and their save at once: 1 when the lock holds.
    inside, most = [0], [0]
    load, save = ide_questions._load_for_write, ide_questions._save

    def counted_load(root: Path, run_id: str) -> dict[str, Any]:
        inside[0] += 1
        most[0] = max(most[0], inside[0])
        return load(root, run_id)

    def counted_save(root: Path, run_id: str, obj: dict[str, Any]) -> None:
        save(root, run_id, obj)
        inside[0] -= 1

    monkeypatch.setattr(ide_questions, "_load_for_write", counted_load)
    monkeypatch.setattr(ide_questions, "_save", counted_save)

    def ask(n: int) -> None:
        try:
            ide_questions.raised(
                tmp_path,
                RUN,
                "ut",
                1,
                QS[:1],
                source="hook",
                tool_use_id=f"t{n}",
                agent_id=f"ag{n}",
            )
        except BaseException as exc:  # a thread's error would otherwise be lost
            errors.append(exc)

    threads = [threading.Thread(target=ask, args=(n,)) for n in range(12)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
    assert most[0] == 1, f"{most[0]} writers held the record at once: the lock did not exclude"
    asks = ide_questions.load(tmp_path, RUN)["asks"]
    assert sorted(a["tool_use_id"] for a in asks) == sorted(f"t{n}" for n in range(12))
    assert len({a["ask_id"] for a in asks}) == 12


def test_a_busy_record_times_out_instead_of_hanging(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ide_questions, "LOCK_WAIT_S", 0.05)
    with ide_questions._locked(tmp_path, RUN), pytest.raises(TimeoutError):
        err: list[BaseException] = []

        def other() -> None:
            try:
                ide_questions.closed(tmp_path, RUN, "ASK-01", reason="skipped")
            except BaseException as exc:
                err.append(exc)

        t = threading.Thread(target=other)
        t.start()
        t.join()
        raise err[0]


def test_answering_an_ask_twice_records_it_once(tmp_path: Path) -> None:
    a = ide_questions.raised(tmp_path, RUN, "req", 1, QS[:1], source="hook", tool_use_id="t1")
    item = [{"question": "Q-01: Which window?", "options": [], "answer": "x"}]
    first = ide_questions.answered(tmp_path, RUN, a, item, answered_by="eng-4f2a")
    assert ide_questions.answered(tmp_path, RUN, a, item, answered_by="eng-4f2a") == first
    assert len(ide_answers.read(tmp_path / "runs" / RUN / "ide-answers.md")) == 1


def test_questions_with_the_same_id_each_get_their_own() -> None:
    got = ide_questions.questions_of(_tool_input(["Q-01: x?", "Q-01: y?", "Q-02: z?"]))
    assert [q["id"] for q in got] == ["Q-01", "ASK-2", "Q-02"]


def test_an_ended_run_stops_counting_an_ask_left_open(world: World) -> None:
    from tsl.core.clock import iso

    run_id = start_run(world)
    next_action(world, run_id)
    ide_questions.raised(
        world.companion,
        run_id,
        "req",
        1,
        QS[:1],
        source="hook",
        at=iso(world.clock()),
        tool_use_id="t1",
        agent_id="ag1",  # a subagent's dialog, dismissed, then it ended
    )
    world.clock.advance(seconds=60)
    code, _, _, err = world.cli(["state", "cancel", run_id, "--reason", "test", "--json"])
    assert code == 0, err
    world.clock.advance(hours=1)
    code, env, _, err = world.cli(["state", "show", run_id, "--progress", "--json"])
    assert code == 0 and env is not None, err
    assert env["data"]["progress"]["wait"]["total_s"] == 60


# ----------------------------------------------------------------- review of #74 (Ekjot, 26 Nov)


def test_answers_between_steps_are_cited_not_listed(world: World) -> None:
    # Listed under answers they fail the first step's answers.logged check (logged for "run",
    # not that step); the step gets them in data.prior_answers, so the model cites them.
    start_run(world)
    qs = ["Q-01: Which window?"]
    hook(world, "pre-tool", _pre_ask(qs))
    out, _ = hook(world, "post-write", _post_ask(qs, {qs[0]: "Yes"}))
    msg = json.loads(out)["hookSpecificOutput"]["additionalContext"]
    assert "do not list them under answers" in msg and "list it under answers" not in msg


def test_answers_in_a_step_are_still_listed(world: World) -> None:
    run_id = start_run(world)
    next_action(world, run_id)
    qs = ["Q-01: Which window?"]
    hook(world, "pre-tool", _pre_ask(qs))
    out, _ = hook(world, "post-write", _post_ask(qs, {qs[0]: "Yes"}))
    assert "list it under answers in the artifact" in out


def test_the_lock_folder_is_the_users_own(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import tempfile

    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(tmp_path / "tmp"))
    with ide_questions._locked(tmp_path, RUN):
        pass
    [folder] = (tmp_path / "tmp").iterdir()
    uid = getattr(os, "getuid", lambda: None)()
    assert folder.name == ("tsl-locks" if uid is None else f"tsl-locks-{uid}")


def test_a_missed_record_is_noted_for_doctor(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    def busy(*_a: Any, **_k: Any) -> str:
        raise TimeoutError("busy")

    monkeypatch.setattr(ide_questions, "raised", busy)
    run_id = start_run(world)
    next_action(world, run_id)
    assert hook(world, "pre-tool", _pre_ask(["Q-01: Which window?"])) == ("", 0)
    [line] = ide_questions.recent_failures(world.rt().home.root)
    assert (line["run_id"], line["hook"], line["error"]) == (run_id, "pre-tool", "TimeoutError")
    _, env, _, err = world.cli(["doctor", "--json"])
    assert env is not None, err
    [chk] = [c for c in env["data"]["checks"] if c["id"] == "ide-questions"]
    assert chk["status"] == "warn" and "1 IDE question records missed" in chk["detail"]


def test_a_doctor_without_missed_records_shows_no_check(world: World) -> None:
    _, env, _, err = world.cli(["doctor", "--json"])
    assert env is not None, err
    assert not [c for c in env["data"]["checks"] if c["id"] == "ide-questions"]


def test_windows_retries_a_save_while_a_reader_has_the_file_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # On Windows os.replace fails while another process (the panel's tsl state show) has the
    # record open; the save waits a moment and tries again instead of losing the change.
    from tsl.core import jsonio

    real, tries = os.replace, []

    def flaky(src: str, dst: Any) -> None:
        tries.append(dst)
        if len(tries) < 3:
            raise PermissionError(13, "in use")
        real(src, dst)

    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(os, "replace", flaky)
    monkeypatch.setattr(time, "sleep", lambda _s: None)
    ide_questions._save(tmp_path, RUN, {"schema": "ide-questions.v1", "run_id": RUN, "asks": []})
    assert len(tries) == 3 and ide_questions.load(tmp_path, RUN)["run_id"] == RUN
    monkeypatch.setattr(sys, "platform", "linux")  # elsewhere it is a real error
    tries.clear()
    with pytest.raises(PermissionError):
        jsonio.write_json(tmp_path / "x.json", {})


# ------------------------------------------------- notes 4 and 8 of the #74 review (Ekjot, 26 Nov)


def _stop(agent: str | None) -> dict[str, Any]:
    d: dict[str, Any] = {"hook_event_name": "SubagentStop", "stop_hook_active": False}
    if agent:
        d["agent_id"] = agent
    return d


def test_a_subagent_that_ends_closes_the_ask_it_left_open(world: World) -> None:
    # Dismissed, then the subagent ended: no later tool call of that agent would close it.
    run_id = start_run(world)
    next_action(world, run_id)
    hook(world, "pre-tool", _pre_ask(["Q-01: Which window?"], "toolu_a", agent_id="ag1"))
    hook(world, "pre-tool", _pre_ask(["Q-02: Page size?"], "toolu_m"))  # the main session's
    assert hook(world, "subagent-stop", _stop(None)) == ("", 0)  # no agent id: nothing to do
    assert len(ide_questions.open_asks(world.companion, run_id)) == 2
    assert hook(world, "subagent-stop", _stop("ag1")) == ("", 0)
    a, m = _asks(world, run_id)
    assert (a["status"], a["close_reason"]) == ("closed", "dismissed")
    assert m["status"] == "open"  # another agent's dialog stays


def test_subagent_stop_sends_no_hook_decision_event(world: World) -> None:
    # hook.decision's hook enum has no subagent-stop: the service would reject the event.
    start_run(world)
    hook(world, "subagent-stop", _stop("ag1"))
    events = [e for e in world.rt().outbox().events() if e["type"] == "hook.decision"]
    assert all(e["body"]["hook"] != "subagent-stop" for e in events)


def test_the_run_ending_closes_every_open_ask_so_repair_cannot_move_its_wait(
    world: World,
) -> None:
    from tsl.core.clock import iso

    run_id = start_run(world)
    next_action(world, run_id)
    ide_questions.raised(
        world.companion,
        run_id,
        "req",
        1,
        QS[:1],
        source="hook",
        at=iso(world.clock()),
        tool_use_id="t1",
        agent_id="ag1",
    )
    world.clock.advance(seconds=60)
    code, _, _, err = world.cli(["state", "cancel", run_id, "--reason", "test", "--json"])
    assert code == 0, err
    [ask] = _asks(world, run_id)
    assert (ask["status"], ask["close_reason"]) == ("closed", "run-ended")
    world.clock.advance(hours=1)
    world.cli(["state", "repair", run_id, "--json"])  # moves updated_at; the wait stays
    code, env, _, err = world.cli(["state", "show", run_id, "--progress", "--json"])
    assert code == 0 and env is not None, err
    assert env["data"]["progress"]["wait"]["total_s"] == 60


def test_a_writer_never_saves_over_a_record_it_cannot_read(tmp_path: Path) -> None:
    # load() reads a broken record as empty (a view); a writer saving that would drop every
    # ask in it. It stops instead, and the hook notes the failure for tsl doctor.
    ide_questions.raised(tmp_path, RUN, "req", 1, QS[:1], source="hook", tool_use_id="t1")
    p = tmp_path / f"runs/{RUN}/ide-questions.json"
    p.write_text(p.read_text(encoding="utf-8")[:-5], encoding="utf-8")  # cut short
    broken = p.read_text(encoding="utf-8")
    with pytest.raises(ValueError):
        ide_questions.raised(tmp_path, RUN, "req", 1, QS[1:], source="hook", tool_use_id="t2")
    assert p.read_text(encoding="utf-8") == broken


# ------------------------------------------- the lock file (Windows CI: the old lock did not hold)


def test_the_lock_name_does_not_depend_on_the_record_existing(tmp_path: Path) -> None:
    # On Windows the resolved name of a file that does not exist yet can differ from the name
    # once it exists, which gave writers different locks. The name comes from the root now.
    before = ide_questions._lock_file(tmp_path, RUN)
    ide_questions.raised(tmp_path, RUN, "req", 1, QS[:1], source="hook", tool_use_id="t1")
    assert ide_questions._lock_file(tmp_path, RUN) == before
    assert ide_questions._lock_file(tmp_path, "run_other") != before
    assert not before.exists()  # removed by the writer that held it


def test_a_lock_left_by_a_writer_that_died_is_broken(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ide_questions, "LOCK_WAIT_S", 0.5)
    lock = ide_questions._lock_file(tmp_path, RUN)
    lock.write_bytes(b"dead")
    assert ide_questions.close_open(tmp_path, RUN, reason="x") == 0  # no record: never locks
    ide_questions._save(tmp_path, RUN, {"schema": "ide-questions.v1", "run_id": RUN, "asks": []})
    with pytest.raises(TimeoutError):  # a fresh lock is someone's: wait, then give up
        ide_questions.raised(tmp_path, RUN, "req", 1, QS[:1], source="hook", tool_use_id="t1")
    old = time.time() - ide_questions.LOCK_STALE_S - 5
    os.utime(lock, (old, old))
    ide_questions.raised(tmp_path, RUN, "req", 1, QS[:1], source="hook", tool_use_id="t1")
    assert len(ide_questions.load(tmp_path, RUN)["asks"]) == 1 and not lock.exists()


def test_a_writer_removes_only_its_own_lock(tmp_path: Path) -> None:
    # Its lock was broken as stale and another writer took a new one: that one stays.
    lock = ide_questions._lock_file(tmp_path, RUN)
    with ide_questions._locked(tmp_path, RUN):
        lock.write_bytes(b"another writer")
    assert lock.read_bytes() == b"another writer"


def test_windows_waits_while_the_last_lock_file_is_being_deleted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Windows refuses to create a file that is still being deleted (PermissionError): that is
    # a busy lock there. Elsewhere it means the folder is not writable, a real error.
    real, refused = os.open, list[Any]()

    def deleting(path: Any, flags: int, mode: int = 0o777) -> int:
        if str(path).endswith(".lock") and len(refused) < 2:
            refused.append(path)
            raise PermissionError(13, "delete pending")
        return real(path, flags, mode)

    monkeypatch.setattr(os, "open", deleting)
    monkeypatch.setattr(sys, "platform", "win32")
    with ide_questions._locked(tmp_path, RUN):
        pass
    assert len(refused) == 2
    refused.clear()
    monkeypatch.setattr(sys, "platform", "linux")
    with pytest.raises(PermissionError), ide_questions._locked(tmp_path, RUN):
        pass
