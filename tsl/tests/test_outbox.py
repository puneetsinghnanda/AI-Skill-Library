"""Local outbox and `tsl events flush` (SDD-04 §8, SDD-08 POST /v1/events)."""

from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from helpers import START, World
from tsl.core.clock import FrozenClock
from tsl.core.errors import TslError
from tsl.core.ids import IdFactory
from tsl.insights.client import HttpResult, InsightsUnavailable
from tsl.telemetry.outbox import MAX_BACKOFF, Outbox

BODY = {"hook": "pre-tool", "decision": "allow", "code": None}


@pytest.fixture
def box(tmp_path: Path) -> Outbox:
    clock = FrozenClock(START)
    return Outbox(tmp_path / "outbox.db", clock, IdFactory(clock, seed=1), strict=True)


def _fill(box: Outbox, n: int) -> list[str]:
    return [str(box.enqueue("hook.decision", dict(BODY))) for _ in range(n)]


def _tok(force: bool) -> str:
    return "tok"


def test_enqueue_validates(box: Outbox, tmp_path: Path) -> None:
    with pytest.raises(TslError) as e:
        box.enqueue("hook.decision", {"hook": "pre-tool"})
    assert e.value.code == "E-INT-01"
    lenient = Outbox(tmp_path / "o2.db", box.clock, box.ids, strict=False)
    assert lenient.enqueue("no.such.type", {}) is None
    assert lenient.stats()["pending"] == 0


def test_schema_and_wal(box: Outbox) -> None:
    _fill(box, 1)
    c = sqlite3.connect(box.path)
    assert c.execute("PRAGMA user_version").fetchone()[0] == 1
    assert c.execute("PRAGMA journal_mode").fetchone()[0] == "wal"


def test_flush_accepted_duplicates_rejected(box: Outbox) -> None:
    ids = _fill(box, 3)
    sent: list[list[dict[str, Any]]] = []

    def post(tok: str, events: list[dict[str, Any]]) -> HttpResult:
        sent.append(events)
        return HttpResult(
            202,
            {
                "accepted": 1,
                "duplicates": [ids[1]],
                "rejected": [{"event_id": ids[2], "code": "E-ING-03"}],
            },
        )

    res = box.flush(_tok, post, 5)
    assert (res.sent, res.duplicates, res.rejected, res.pending, res.dead) == (1, 1, 1, 0, 1)
    assert {e["event_id"] for e in sent[0]} == set(ids)
    dead = box.events("dead")[0]
    assert dead["event_id"] == ids[2]


def test_unknown_schema_version_stays_queued(box: Outbox) -> None:
    # SDD-08 §4.3: E-ING-02 is "keep queued; upgrade tsl"; every other E-ING code is dead
    ids = _fill(box, 2)

    def post(tok: str, events: list[dict[str, Any]]) -> HttpResult:
        return HttpResult(
            202,
            {
                "duplicates": [],
                "rejected": [
                    {"event_id": ids[0], "code": "E-ING-02"},
                    {"event_id": ids[1], "code": "E-ING-01"},
                ],
            },
        )

    res = box.flush(_tok, post, 5)
    assert (res.rejected, res.pending, res.dead) == (2, 1, 1)
    pending = box.events("pending")
    assert [e["event_id"] for e in pending] == [ids[0]]
    c = sqlite3.connect(box.path)
    assert c.execute("SELECT last_error FROM event WHERE event_id=?", (ids[0],)).fetchone() == (
        "E-ING-02",
    )
    c.close()
    assert [e["event_id"] for e in box.events("dead")] == [ids[1]]
    # a later flush against a newer service sends it
    box.clock.advance(seconds=MAX_BACKOFF + 1)  # type: ignore[attr-defined]
    res = box.flush(_tok, lambda t, e: HttpResult(202, {"duplicates": [], "rejected": []}), 5)
    assert (res.sent, res.pending, res.dead) == (1, 0, 1)


def test_offline_keeps_events(box: Outbox) -> None:
    _fill(box, 2)

    def down(tok: str, events: list[dict[str, Any]]) -> HttpResult:
        raise InsightsUnavailable("x")

    res = box.flush(_tok, down, 5)
    assert res.offline and res.pending == 2 and res.sent == 0
    # backoff: not due again immediately
    called: list[int] = []
    box.flush(_tok, lambda t, e: called.append(1) or HttpResult(202, {}), 5)  # type: ignore[func-returns-value]
    assert called == []
    box.clock.advance(seconds=10)  # type: ignore[attr-defined]
    res = box.flush(_tok, lambda t, e: HttpResult(202, {"duplicates": [], "rejected": []}), 5)
    assert res.sent == 2 and res.pending == 0


def test_429_and_5xx_back_off(box: Outbox) -> None:
    _fill(box, 1)
    res = box.flush(_tok, lambda t, e: HttpResult(429, None, {"Retry-After": "120"}), 5)
    assert res.pending == 1
    box.clock.advance(seconds=60)  # type: ignore[attr-defined]
    called: list[int] = []
    box.flush(_tok, lambda t, e: called.append(1) or HttpResult(503, None), 5)  # type: ignore[func-returns-value]
    assert called == []
    box.clock.advance(seconds=61)  # type: ignore[attr-defined]
    res = box.flush(_tok, lambda t, e: HttpResult(503, None), 5)
    attempts = sqlite3.connect(box.path).execute("SELECT attempts FROM event").fetchone()[0]
    assert res.pending == 1 and attempts == 2


def test_413_splits_batch(box: Outbox) -> None:
    _fill(box, 4)
    sizes: list[int] = []

    def post(tok: str, events: list[dict[str, Any]]) -> HttpResult:
        sizes.append(len(events))
        if len(events) > 1:
            return HttpResult(413, None)
        return HttpResult(202, {"duplicates": [], "rejected": []})

    res = box.flush(_tok, post, 5)
    assert res.sent == 4 and sizes[0] == 4 and sizes.count(1) == 4


def test_401_refreshes_once_then_auth_error(box: Outbox) -> None:
    _fill(box, 1)
    forced: list[bool] = []

    def tok(force: bool) -> str:
        forced.append(force)
        return "t2" if force else "t1"

    res = box.flush(
        tok, lambda t, e: HttpResult(202, {}) if t == "t2" else HttpResult(401, None), 5
    )
    assert forced == [False, True] and res.sent == 1
    _fill(box, 1)
    res = box.flush(tok, lambda t, e: HttpResult(401, None), 5)
    assert res.auth_failed and res.pending == 1

    def no_token(force: bool) -> str:
        raise TslError("E-AUTH-01")

    res = box.flush(no_token, lambda t, e: HttpResult(202, {}), 5)
    assert res.auth_failed and res.pending == 1


def test_lease_expiry_recovers_crashed_sender(box: Outbox) -> None:
    _fill(box, 1)
    c = sqlite3.connect(box.path)
    lease = "2026-01-01T00:01:00Z"
    c.execute("UPDATE event SET status='sending', lease_until=?", (lease,))
    c.commit()
    ok = lambda t, e: HttpResult(202, {"duplicates": [], "rejected": []})  # noqa: E731
    assert box.flush(_tok, ok, 5).sent == 0
    box.clock.advance(seconds=61)  # type: ignore[attr-defined]
    assert box.flush(_tok, ok, 5).sent == 1


def test_never_drops_pending_and_housekeeps_sent(box: Outbox) -> None:
    _fill(box, 2)
    box.flush(_tok, lambda t, e: HttpResult(202, {"duplicates": [], "rejected": []}), 5)
    _fill(box, 1)
    box.clock.advance(days=30)  # type: ignore[attr-defined]
    box.flush(_tok, lambda t, e: (_ for _ in ()).throw(InsightsUnavailable("x")), 5)
    s = box.stats()
    assert s["pending"] == 1 and s["sent"] == 0


def test_retry_dead(box: Outbox) -> None:
    ids = _fill(box, 1)
    box.flush(
        _tok, lambda t, e: HttpResult(202, {"rejected": [{"event_id": ids[0], "code": "E"}]}), 5
    )
    assert box.stats()["dead"] == 1
    assert box.retry_dead() == 1 and box.stats()["pending"] == 1


def test_concurrent_writers(tmp_path: Path) -> None:
    db = tmp_path / "outbox.db"
    script = (
        "import sys\n"
        "from datetime import UTC, datetime\n"
        "from pathlib import Path\n"
        "from tsl.core.clock import FrozenClock\n"
        "from tsl.core.ids import IdFactory\n"
        "from tsl.telemetry.outbox import MAX_BACKOFF, Outbox\n"
        "c = FrozenClock(datetime(2026, 1, 1, tzinfo=UTC))\n"
        "b = Outbox(Path(sys.argv[1]), c, IdFactory(c, seed=int(sys.argv[2])), strict=True)\n"
        "for _ in range(25):\n"
        "    b.enqueue('hook.decision', {'hook': 'pre-tool', 'decision': 'allow', 'code': None})\n"
    )
    procs = [subprocess.Popen([sys.executable, "-c", script, str(db), str(i)]) for i in range(4)]
    assert [p.wait(timeout=60) for p in procs] == [0, 0, 0, 0]
    clock = FrozenClock(START)
    assert Outbox(db, clock, IdFactory(clock)).stats()["pending"] == 100


# ------------------------------------------------------------------------- CLI
def test_events_flush_command(world: World) -> None:
    rt = world.rt()
    rt.outbox().enqueue("hook.decision", dict(BODY))
    code, env, _, _ = world.cli(["events", "flush", "--json"])
    assert (
        code == 0 and env is not None and env["data"]["sent"] >= 1 and env["data"]["pending"] == 0
    )
    assert any(e["type"] == "hook.decision" for e in world.insights.events)
    assert all(
        set(e) >= {"event_id", "type", "schema_version", "occurred_at", "body"}
        for e in world.insights.events
    )


def test_events_flush_offline_is_a_warning(world: World) -> None:
    world.rt().outbox().enqueue("hook.decision", dict(BODY))
    world.insights.offline = True
    code, env, _, _ = world.cli(["events", "flush", "--json"])
    assert code == 0 and env is not None
    assert env["warnings"][0]["code"] == "E-NET-01" and env["data"]["pending"] >= 1


def test_events_flush_logged_out(world: World) -> None:
    world.rt().outbox().enqueue("hook.decision", dict(BODY))
    world.identities["eng"].logged_in = False
    code, env, _, _ = world.cli(["events", "flush", "--json"])
    assert code == 10 and env is not None and env["code"] == "E-AUTH-01"
    assert env["data"]["pending"] >= 1


def test_events_flush_retry_dead(world: World) -> None:
    box = world.rt().outbox()
    eid = box.enqueue("hook.decision", dict(BODY))
    world.insights.event_responses.append(
        HttpResult(202, {"duplicates": [], "rejected": [{"event_id": eid, "code": "E-ING-01"}]})
    )
    code, env, _, _ = world.cli(["events", "flush", "--json"])
    assert env is not None and env["data"]["dead"] >= 1
    code, env, _, _ = world.cli(["events", "flush", "--retry-dead", "--json"])
    assert code == 0 and env is not None and env["data"]["dead"] == 0
    assert json.dumps(world.insights.events).count(str(eid)) == 1
