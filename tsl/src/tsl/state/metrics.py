"""Run metrics (roadmap D1): model tokens, engineer wait and AI time per step attempt.

Tokens come from the Claude Code session transcripts of the sessions that ran the run: the main
session's `<session>.jsonl` and its subagents' `<session>/subagents/*.jsonl` (the reviewer, and a
step run as a subagent). Every assistant message carries `message.usage`; a message streamed as
several lines is counted once (by message id). A call belongs to the attempt whose window
(started_at to decided_at) holds its timestamp. Only the four counts and the model id are read,
never prompt or response text, and the transcript paths stay on the laptop.

The engineer's wait comes from ide-questions.json (B2); the AI time is the attempt's window less
that wait. Everything here is best effort: no transcript gives `tokens: null`, and a failure never
stops tsl decide.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tsl.core.paths import Home, tool_log_path
from tsl.core.repo import Companion

TOKEN_KEYS = ("input", "output", "cache_read", "cache_write")
USAGE = {
    "input": "input_tokens",
    "output": "output_tokens",
    "cache_read": "cache_read_input_tokens",
    "cache_write": "cache_creation_input_tokens",
}
MODEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@-]{0,63}$")
SESSION = re.compile(r"^[A-Za-z0-9-]{1,128}$")
MAX_MODELS = 8


@dataclass(frozen=True)
class Call:
    at: dt.datetime
    model: str
    subagent: bool
    tokens: dict[str, int]


def _ts(s: Any) -> dt.datetime | None:
    try:
        t = dt.datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=dt.UTC)


def _int(v: Any) -> int:
    return v if isinstance(v, int) and not isinstance(v, bool) and v > 0 else 0


def run_sessions(comp: Companion, run_id: str, state: dict[str, Any]) -> list[str]:
    """The Claude sessions that worked on the run: every session in its tool log, and the one
    bound now (a resumed run has more than one)."""
    out: list[str] = []
    p = comp.path(tool_log_path(run_id))
    if p.is_file():
        try:
            for line in p.read_text(encoding="utf-8").splitlines():
                try:
                    sid = str(json.loads(line).get("session_id") or "")
                except ValueError:
                    continue
                if sid and sid != "unknown" and sid not in out:
                    out.append(sid)
        except OSError:
            pass
    act = str((state.get("active_session") or {}).get("session_id") or "")
    if act and act not in out:
        out.append(act)
    return out


def transcript(home: Home, session_id: str, env: Mapping[str, str] | None = None) -> Path | None:
    """The session's transcript: the path the session-start hook kept, else Claude Code's
    default place (`$CLAUDE_CONFIG_DIR` or `~/.claude`, `projects/<project>/<session>.jsonl`)."""
    if not SESSION.match(session_id):
        return None
    kept = home.session_transcript(session_id)
    try:
        if kept.is_file():
            t = Path(kept.read_text(encoding="utf-8").strip())
            if t.is_file():
                return t
    except OSError:
        pass
    env = os.environ if env is None else env
    base = Path(env.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude") / "projects"
    hits = sorted(base.glob(f"*/{session_id}.jsonl")) if base.is_dir() else []
    return hits[0] if hits else None


def files(main: Path) -> list[tuple[Path, bool]]:
    """The main transcript and its subagents' transcripts, each with `is subagent`."""
    subs = main.with_suffix("") / "subagents"
    out = [(main, False)]
    if subs.is_dir():
        out += [(p, True) for p in sorted(subs.glob("*.jsonl"))]
    return out


def read_calls(paths: Iterable[tuple[Path, bool]]) -> list[Call]:
    """One Call per model message with usage; unreadable lines and files are skipped."""
    calls: dict[tuple[str, str], Call] = {}
    for path, sub in paths:
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for line in lines:
            if '"usage"' not in line:
                continue
            try:
                d = json.loads(line)
            except ValueError:
                continue
            m = d.get("message") if isinstance(d, dict) else None
            if d.get("type") != "assistant" or not isinstance(m, dict):
                continue
            u, at = m.get("usage"), _ts(d.get("timestamp"))
            if not isinstance(u, dict) or at is None:
                continue
            mid = str(m.get("id") or d.get("requestId") or d.get("uuid") or len(calls))
            model = str(m.get("model") or "")
            calls[(str(path), mid)] = Call(
                at=at,
                model=model if MODEL.match(model) else "",
                subagent=sub,
                tokens={k: _int(u.get(v)) for k, v in USAGE.items()},
            )
    return sorted(calls.values(), key=lambda c: c.at)


def run_calls(
    home: Home,
    comp: Companion,
    run_id: str,
    state: dict[str, Any],
    env: Mapping[str, str] | None = None,
) -> list[Call] | None:
    """Every model call of the run's sessions; None when no transcript was found."""
    paths: list[tuple[Path, bool]] = []
    for sid in run_sessions(comp, run_id, state):
        t = transcript(home, sid, env)
        if t is not None:
            paths += files(t)
    return read_calls(paths) if paths else None


def tokens(calls: Iterable[Call], start: dt.datetime, end: dt.datetime) -> dict[str, Any]:
    """Token counts of the calls in [start, end), with the models used (most output first)."""
    tot = dict.fromkeys(TOKEN_KEYS, 0)
    n = subs = 0
    by_model: dict[str, int] = {}
    for c in calls:
        if not start <= c.at < end:
            continue
        n += 1
        subs += c.subagent
        for k in TOKEN_KEYS:
            tot[k] += c.tokens[k]
        if c.model:
            by_model[c.model] = by_model.get(c.model, 0) + c.tokens["output"]
    models = sorted(by_model, key=lambda m: (-by_model[m], m))[:MAX_MODELS]
    return {"tokens": {**tot, "calls": n, "subagent_calls": subs}, "models": models}


def attempt_wait_s(root: Path, run_id: str, step: str, attempt: int, now: str) -> int:
    """The engineer's wait on IDE questions of this step attempt, in seconds (B2)."""
    from tsl.approvals import ide_questions

    t_now = _ts(now)
    total = 0
    for a in ide_questions.load(root, run_id)["asks"]:
        if (a.get("step"), a.get("attempt")) != (step, attempt):
            continue
        t0 = _ts(a.get("asked_at"))
        t1 = _ts(a.get("answered_at") or a.get("closed_at")) or t_now
        if t0 is not None and t1 is not None:
            total += max(0, int((t1 - t0).total_seconds()))
    return total


def for_attempt(
    home: Home,
    comp: Companion,
    run_id: str,
    state: dict[str, Any],
    step: str,
    attempt: dict[str, Any],
    decided_at: str,
    calls: list[Call] | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """The metrics object (run-state.v1 attempts[].metrics, step.decided metrics)."""
    t0, t1 = _ts(attempt.get("started_at")), _ts(decided_at)
    wait = attempt_wait_s(comp.root, run_id, step, int(attempt["n"]), decided_at)
    span_ms = int((t1 - t0).total_seconds() * 1000) if t0 and t1 and t1 > t0 else 0
    out: dict[str, Any] = {
        "tokens": None,
        "wait_s": wait,
        "active_ms": max(0, span_ms - wait * 1000),
        "source": "none",
    }
    if calls is None:
        calls = run_calls(home, comp, run_id, state, env)
    if calls is not None and t0 and t1:
        out.update(tokens(calls, t0, t1), source="transcript")
    return out


def safe_for_attempt(*args: Any, **kwargs: Any) -> dict[str, Any] | None:
    """for_attempt, or None on any error: metrics never stop a decision."""
    try:
        return for_attempt(*args, **kwargs)
    except Exception:
        return None


def _add(a: dict[str, int], b: dict[str, Any] | None) -> None:
    for k in (*TOKEN_KEYS, "calls", "subagent_calls"):
        a[k] = a.get(k, 0) + int((b or {}).get(k) or 0)


def report(
    home: Home,
    comp: Companion,
    run_id: str,
    state: dict[str, Any],
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """`tsl state show <run> --metrics`: every decided attempt and the totals per step and run.

    An attempt decided before D1 has no stored metrics: they are worked out from the
    transcripts now, if those are still on this laptop. The run total covers the whole run, so
    `loop` is what the run loop spent between attempts (tsl next, decide, the status text)."""
    calls = run_calls(home, comp, run_id, state, env)
    rows: list[dict[str, Any]] = []
    steps: dict[str, dict[str, Any]] = {}
    attempts_tok: dict[str, int] = {}
    for s in state.get("steps", []):
        for a in s.get("attempts", []):
            if not a.get("decided_at"):
                continue
            m = a.get("metrics") or for_attempt(
                home, comp, run_id, state, s["id"], a, a["decided_at"], calls, env
            )
            rows.append(
                {
                    "step": s["id"],
                    "attempt": int(a["n"]),
                    "cause": a.get("cause"),
                    "outcome": a.get("outcome"),
                    "band": a.get("band"),
                    **m,
                }
            )
            agg = steps.setdefault(
                s["id"], {"attempts": 0, "retries": 0, "active_ms": 0, "wait_s": 0, "tokens": {}}
            )
            agg["attempts"] += 1
            agg["retries"] = agg["attempts"] - 1
            agg["active_ms"] += m["active_ms"]
            agg["wait_s"] += m["wait_s"]
            _add(agg["tokens"], m["tokens"])
            _add(attempts_tok, m["tokens"])
    total: dict[str, Any] = {
        "attempts": len(rows),
        "retries": sum(v["retries"] for v in steps.values()),
        "active_ms": sum(v["active_ms"] for v in steps.values()),
        "wait_s": sum(v["wait_s"] for v in steps.values()),
        "tokens": None,
        "loop_tokens": None,
    }
    t0, t1 = _ts(state.get("created_at")), _ts(state.get("updated_at"))
    if calls is not None and t0 and t1:
        run_tok = tokens(calls, t0, t1 + dt.timedelta(seconds=1))["tokens"]
        total["tokens"] = run_tok
        total["loop_tokens"] = {k: max(0, run_tok[k] - attempts_tok.get(k, 0)) for k in run_tok}
    return {
        "run_id": run_id,
        "ticket": state.get("ticket"),
        "workflow": state.get("workflow"),
        "status": state.get("status"),
        "source": "transcript" if calls is not None else "none",
        "attempts": rows,
        "steps": steps,
        "total": total,
    }


def _n(v: Any) -> str:
    if v is None:
        return "-"
    n = float(v)
    for div, unit in ((1e6, "M"), (1e3, "k")):
        if n >= div:
            return f"{n / div:.1f}{unit}"
    return str(int(n))


def _min(ms: int | None) -> str:
    return "-" if ms is None else f"{ms / 60000:.1f}m"


def render(r: dict[str, Any]) -> str:
    """The report as a plain table: one line per attempt, then the totals."""
    head = f"{'step':<10} {'att':>3} {'outcome':<19} {'band':<6} {'AI':>6} {'wait':>6} "
    head += f"{'calls':>5} {'out':>7} {'cache rd':>8} {'cache wr':>8}"
    wf = str(r.get("workflow") or "").split("@")[0]
    lines = [f"{r.get('ticket')} · {wf} · {r.get('status')} · {r['run_id']}", head]

    def row(
        name: str, att: str, out: str, band: str, ms: int | None, wait: int | None, t: Any
    ) -> str:
        t = t or {}
        w = None if wait is None else wait * 1000
        return (
            f"{name:<10} {att:>3} {out:<19} {band:<6} {_min(ms):>6} {_min(w):>6} "
            f"{_n(t.get('calls')):>5} {_n(t.get('output')):>7} "
            f"{_n(t.get('cache_read')):>8} {_n(t.get('cache_write')):>8}"
        )

    for a in r["attempts"]:
        lines.append(
            row(
                a["step"],
                str(a["attempt"]),
                str(a.get("outcome") or ""),
                str(a.get("band") or "-"),
                a["active_ms"],
                a["wait_s"],
                a["tokens"],
            )
        )
    t = r["total"]
    lines.append(
        row(
            "attempts",
            str(t["attempts"]),
            f"{t['retries']} retries",
            "",
            t["active_ms"],
            t["wait_s"],
            None if t["tokens"] is None else _sum_attempts(r),
        )
    )
    if t["tokens"] is not None:
        lines.append(row("run loop", "", "between attempts", "", None, None, t["loop_tokens"]))
        lines.append(row("run", "", "", "", t["active_ms"], t["wait_s"], t["tokens"]))
    else:
        lines.append("Tokens: no Claude Code transcript found for this run's sessions.")
    return "\n".join(lines)


def _sum_attempts(r: dict[str, Any]) -> dict[str, int]:
    out: dict[str, int] = {}
    for a in r["attempts"]:
        _add(out, a["tokens"])
    return out
