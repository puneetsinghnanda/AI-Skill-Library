"""Stuck runs (roadmap D2): a RUNNING run where nothing has happened for longer than the open
phase allows. Read only: detection never changes a run, it says so and names the command.

Last activity is the newest of: a state.json save (`updated_at`), the run's last tool-log line
(every Write, Edit and Bash of the run), the action `tsl next` handed out (A2
`current_action.started_at`) and an IDE question asked or answered (B2). While an IDE question
is open the run waits on the engineer, which is not stuck; nor is a run a tsl command (a long
verifier) is working on.

Limits, from `gates.stuck_after_min` in tsl.yaml (default 30):
- a step (`run_step`, `fix`): the limit;
- the reviewer (`run_reviewer`): half of it;
- between steps: a third of it; at least 5 minutes each.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

from tsl.core.paths import tool_log_path

OPEN = ("RUNNING",)
TAIL_BYTES = 16384  # the last tool-log lines; the file only grows


def _ts(s: Any) -> dt.datetime | None:
    try:
        t = dt.datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=dt.UTC)


def _iso(t: dt.datetime) -> str:
    return t.astimezone(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _last_tool(root: Path, run_id: str) -> dt.datetime | None:
    p = Path(root) / tool_log_path(run_id)
    try:
        with p.open("rb") as fh:
            fh.seek(0, 2)
            size = fh.tell()
            fh.seek(max(0, size - TAIL_BYTES))
            lines = fh.read().decode("utf-8", errors="replace").splitlines()
    except OSError:
        return None
    for line in reversed(lines):
        try:
            t = _ts(json.loads(line).get("ts"))
        except (ValueError, AttributeError):
            continue
        if t is not None:
            return t
    return None


def _tsl_busy(root: Path, run_id: str) -> bool:
    """A live tsl process holds the run's .local.lock: tsl verify holds it for the whole
    verifier run, which writes no tool-log line until it ends."""
    from tsl.state.store import _pid_alive

    try:
        pid = int((Path(root) / "runs" / run_id / ".local.lock").read_text().strip() or "0")
    except (OSError, ValueError):
        return False
    return _pid_alive(pid)


def last_activity(root: Path, run_id: str, state: dict[str, Any]) -> dt.datetime | None:
    """The newest sign of life of the run, from the sources above."""
    from tsl.approvals import ide_questions

    seen = [
        _ts(state.get("updated_at")),
        _ts((state.get("current_action") or {}).get("started_at")),
        _last_tool(root, run_id),
    ]
    for a in ide_questions.load(root, run_id)["asks"]:
        seen += [_ts(a.get("asked_at")), _ts(a.get("answered_at") or a.get("closed_at"))]
    known = [t for t in seen if t is not None]
    return max(known) if known else None


def phase(state: dict[str, Any]) -> str:
    """What is open: run_step, fix or run_reviewer (A2's current_action when it is for the
    step at the cursor), run_step for an open attempt without it, else between."""
    cur = state.get("cursor") or {}
    act = state.get("current_action") or {}
    if cur.get("step") and act.get("step") == cur.get("step") and act.get("action"):
        return str(act["action"])
    if cur.get("step"):
        return "run_step"
    return "between"


def limit_min(state: dict[str, Any], after_min: int) -> int:
    p = phase(state)
    if p == "run_reviewer":
        return max(5, after_min // 2)
    if p == "between":
        return max(5, after_min // 3)
    return max(5, after_min)


def stuck(
    root: Path, run_id: str, state: dict[str, Any], now: dt.datetime, after_min: int = 30
) -> dict[str, Any] | None:
    """{since, minutes, phase, limit_min, command} when the run is stuck, else None."""
    from tsl.approvals import ide_questions

    if state.get("status") not in OPEN or ide_questions.open_asks(root, run_id):
        return None
    if _tsl_busy(root, run_id):  # a tsl command (a long verifier) is running on the run
        return None
    last = last_activity(root, run_id, state)
    if last is None:
        return None
    minutes = int((now - last).total_seconds() // 60)
    lim = limit_min(state, after_min)
    if minutes < lim:
        return None
    return {
        "since": _iso(last),
        "minutes": minutes,
        "phase": phase(state),
        "limit_min": lim,
        "command": f"/truminds:resume {run_id}",
        "cancel": f'tsl state cancel {run_id} --reason "stuck"',
    }
