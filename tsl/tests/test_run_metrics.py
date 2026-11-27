"""Run metrics per step attempt (roadmap D1): tokens from the Claude Code session transcripts,
the engineer's wait on IDE questions (B2) and the AI time, written by tsl decide to state.json
and sent with step.decided; `tsl state show <run> --metrics` reports them."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

from e2e_steps import SESSION, do_req_step, hook, start_run
from helpers import World
from tsl.approvals import ide_questions
from tsl.core.clock import iso
from tsl.core.paths import Home
from tsl.state import metrics

RUN = "run_01JA0B3C4D5E6F7G8H9JKMNPQR"

T0 = dt.datetime(2026, 11, 25, 10, 0, tzinfo=dt.UTC)


def _line(at: dt.datetime, mid: str, out: int = 100, model: str = "claude-opus-5-5") -> str:
    return json.dumps(
        {
            "type": "assistant",
            "timestamp": at.isoformat().replace("+00:00", "Z"),
            "message": {
                "id": mid,
                "model": model,
                "content": [{"type": "text", "text": "never read"}],
                "usage": {
                    "input_tokens": 2,
                    "output_tokens": out,
                    "cache_read_input_tokens": 1000,
                    "cache_creation_input_tokens": 50,
                },
            },
        }
    )


def _transcript(base: Path, session: str, main: list[str], sub: list[str]) -> Path:
    p = base / "projects" / "-home-x-companion" / f"{session}.jsonl"
    (p.parent / session / "subagents").mkdir(parents=True)
    p.write_text("\n".join(main) + "\n", encoding="utf-8")
    (p.parent / session / "subagents" / "agent-a1.jsonl").write_text(
        "\n".join(sub) + "\n", encoding="utf-8"
    )
    return p


# ---------------------------------------------------------------------------------- the reader


def test_calls_are_counted_once_and_only_from_usage(tmp_path: Path) -> None:
    t = T0 + dt.timedelta(minutes=1)
    main = [
        _line(t, "msg_1", out=100),
        _line(t, "msg_1", out=100),  # one message streamed as two lines
        "not json {",
        json.dumps({"type": "user", "message": {"content": "usage"}}),
        _line(t + dt.timedelta(minutes=1), "msg_2", out=7, model="bad model!"),
    ]
    p = _transcript(tmp_path, "s1", main, [_line(t, "rev_1", out=40)])
    calls = metrics.read_calls(metrics.files(p))
    assert [(c.tokens["output"], c.subagent, c.model) for c in calls] == [
        (100, False, "claude-opus-5-5"),
        (40, True, "claude-opus-5-5"),
        (7, False, ""),
    ]
    got = metrics.tokens(calls, T0, T0 + dt.timedelta(minutes=2))
    assert got["tokens"] == {
        "input": 4,
        "output": 140,
        "cache_read": 2000,
        "cache_write": 100,
        "calls": 2,
        "subagent_calls": 1,
    }
    assert got["models"] == ["claude-opus-5-5"]
    assert metrics.read_calls([(tmp_path / "missing.jsonl", False)]) == []


def test_the_transcript_is_found_from_the_hook_or_the_default_place(tmp_path: Path) -> None:
    home = Home(tmp_path / "truminds")
    p = _transcript(tmp_path / "claude", "s-1", [], [])
    env = {"CLAUDE_CONFIG_DIR": str(tmp_path / "claude")}
    assert metrics.transcript(home, "s-1", env) == p  # Claude Code's default place
    kept = tmp_path / "elsewhere.jsonl"
    kept.write_text("", encoding="utf-8")
    home.sessions.mkdir(parents=True)
    home.session_transcript("s-1").write_text(str(kept), encoding="utf-8")
    assert metrics.transcript(home, "s-1", env) == kept  # what the session-start hook kept
    assert metrics.transcript(home, "../etc", env) is None
    assert metrics.transcript(home, "s-2", env) is None


def test_session_start_keeps_the_transcript_path(world: World) -> None:
    hook(
        world,
        "session-start",
        {"hook_event_name": "SessionStart", "transcript_path": "/x/projects/p/sess-0001.jsonl"},
    )
    kept = world.rt().home.session_transcript(SESSION)
    assert kept.read_text(encoding="utf-8") == "/x/projects/p/sess-0001.jsonl"


# ------------------------------------------------------------------------------------- decide


def _decided(world: World, run_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    st = json.loads((world.companion / "runs" / run_id / "state.json").read_text("utf-8"))
    att = st["steps"][0]["attempts"][-1]
    ev = [e for e in world.rt().outbox().events() if e["type"] == "step.decided"][-1]
    return att, ev["body"]


def test_decide_records_tokens_wait_and_ai_time(world: World, tmp_path: Path) -> None:
    run_id = start_run(world)
    art = do_req_step(world, run_id, until="recorded")[
        "artifact"
    ]  # the attempt started at the clock's now
    t0 = world.clock()
    m = dt.timedelta(minutes=1)
    main = [_line(t0 - m, "before"), _line(t0 + m, "in-1"), _line(t0 + 4 * m, "in-2", out=300)]
    p = _transcript(tmp_path / "claude", SESSION, main, [_line(t0 + 2 * m, "rev-1", out=50)])
    world.rt().home.session_transcript(SESSION).write_text(str(p), encoding="utf-8")
    # One IDE question in this attempt, answered after a minute (B2).
    ask = ide_questions.raised(
        world.companion,
        run_id,
        "req",
        1,
        [{"id": "Q-01", "text": "Q-01: x?"}],
        source="hook",
        at=iso(t0 + m),
    )
    ide_questions.closed(world.companion, run_id, ask, reason="skipped", at=iso(t0 + 2 * m))
    world.clock.advance(minutes=5)
    with open(p, "a", encoding="utf-8") as fh:  # after the decision: not this attempt's
        fh.write(_line(t0 + 6 * m, "after") + "\n")
    code, dec, _, err = world.cli(["decide", art, "--json"], session=SESSION)
    assert dec is not None and code in (0, 4), err
    att, body = _decided(world, run_id)
    want = {
        "tokens": {
            "input": 6,
            "output": 450,
            "cache_read": 3000,
            "cache_write": 150,
            "calls": 3,
            "subagent_calls": 1,
        },
        "models": ["claude-opus-5-5"],
        "wait_s": 60,
        "active_ms": 240_000,
        "source": "transcript",
    }
    assert att["metrics"] == want
    assert body["metrics"] == want and body["duration_ms"] == 240_000  # was always 0


def test_no_transcript_still_decides_with_wait_and_time(world: World) -> None:
    run_id = start_run(world)
    art = do_req_step(world, run_id, until="recorded")["artifact"]
    world.rt().env = {**world.rt().env, "CLAUDE_CONFIG_DIR": "/nonexistent"}
    world.clock.advance(seconds=90)
    code, dec, _, err = world.cli(["decide", art, "--json"], session=SESSION)
    assert dec is not None and code in (0, 4), err
    att, body = _decided(world, run_id)
    assert att["metrics"] == {"tokens": None, "wait_s": 0, "active_ms": 90_000, "source": "none"}
    assert body["metrics"] == att["metrics"]


def test_a_metrics_failure_never_stops_a_decision(world: World, monkeypatch: Any) -> None:
    def boom(*_a: Any, **_k: Any) -> None:
        raise OSError("transcript unreadable")

    monkeypatch.setattr(metrics, "for_attempt", boom)
    run_id = start_run(world)
    res = do_req_step(world, run_id)
    assert res["code"] == 0, res["env"]
    att, body = _decided(world, run_id)
    assert "metrics" not in att and "metrics" not in body and body["duration_ms"] == 0


# ------------------------------------------------------------------------------------- report


def test_state_show_metrics_reports_attempts_steps_and_the_run(
    world: World, tmp_path: Path
) -> None:
    run_id = start_run(world)
    t0 = world.clock()
    p = _transcript(
        tmp_path / "claude",
        SESSION,
        [_line(t0 + dt.timedelta(seconds=30), "loop"), _line(t0 + dt.timedelta(minutes=2), "s1")],
        [],
    )
    world.rt().home.sessions.mkdir(parents=True, exist_ok=True)
    world.rt().home.session_transcript(SESSION).write_text(str(p), encoding="utf-8")
    world.clock.advance(minutes=1)
    art = do_req_step(world, run_id, until="recorded")["artifact"]
    world.clock.advance(minutes=3)
    code, dec, _, err = world.cli(["decide", art, "--json"], session=SESSION)
    assert dec is not None, err
    code, env, _, err = world.cli(["state", "show", run_id, "--metrics", "--json"])
    assert code == 0 and env is not None, err
    rep = env["data"]["metrics"]
    [row] = rep["attempts"]
    assert (row["step"], row["attempt"], row["tokens"]["calls"]) == ("req", 1, 1)
    assert rep["steps"]["req"]["retries"] == 0 and rep["total"]["attempts"] == 1
    assert rep["total"]["tokens"]["calls"] == 2
    assert rep["total"]["loop_tokens"]["calls"] == 1  # the call before the attempt started
    code, _, text, _ = world.cli(["state", "show", run_id, "--metrics"])
    assert code == 0 and text.splitlines()[0].startswith("ABC-142 · brownfield-change")
    assert any(x.startswith("req ") for x in text.splitlines()) and "run loop" in text
    code, env, _, _ = world.cli(["state", "show", "--metrics", "--json"])
    assert code != 0 and env is not None and env["code"] == "E-USE-01"


def test_a_message_copied_into_another_transcript_is_one_call(tmp_path: Path) -> None:
    # Review of #71 (Gaurav): a resumed or forked session copies earlier messages into its own
    # file. Message ids are unique, so the copy is the same call, at its first time.
    t = T0 + dt.timedelta(minutes=1)
    p = _transcript(tmp_path, "s1", [_line(t, "msg_1", out=100)], [_line(t, "rev_1", out=40)])
    resumed = tmp_path / "projects" / "-home-x-companion" / "s2.jsonl"
    resumed.write_text(
        "\n".join([_line(t + dt.timedelta(hours=1), "msg_1", out=100), _line(t, "rev_1", out=40)])
        + "\n",
        encoding="utf-8",
    )
    calls = metrics.read_calls([*metrics.files(p), (resumed, False)])
    assert [(c.tokens["output"], c.subagent, c.at) for c in calls] == [
        (100, False, t),
        (40, True, t),  # still the reviewer's call, as where it was first seen
    ]
    assert metrics.tokens(calls, T0, T0 + dt.timedelta(minutes=2))["tokens"]["calls"] == 2


def test_the_wait_is_the_time_a_question_was_open_inside_the_attempt(tmp_path: Path) -> None:
    # Review of #71 (Gaurav): two questions open at once are one wait, and a wait is clipped
    # to the attempt, or active_ms comes out low.
    def at(m: int) -> str:
        return iso(T0 + dt.timedelta(minutes=m))

    for tid, agent, t0, t1 in (("t1", None, 2, 6), ("t2", "ag1", 4, 8), ("t3", None, -3, 1)):
        ask = ide_questions.raised(
            tmp_path,
            RUN,
            "req",
            1,
            [{"id": "Q-01", "text": "Q-01: x?"}],
            source="hook",
            at=at(t0),
            tool_use_id=tid,
            agent_id=agent,
        )
        ide_questions.closed(tmp_path, RUN, ask, reason="skipped", at=at(t1))
    # Asked before the attempt started (t3): only the minute inside counts. t1 and t2 overlap
    # from 4 to 6: 2 to 8 is one 6-minute wait. The attempt runs 0 to 10.
    assert metrics.attempt_wait_s(tmp_path, RUN, "req", 1, at(10), at(0)) == (1 + 6) * 60
    assert metrics.attempt_wait_s(tmp_path, RUN, "req", 1, at(5), at(0)) == (1 + 3) * 60
    assert metrics.attempt_wait_s(tmp_path, RUN, "req", 2, at(10), at(0)) == 0
