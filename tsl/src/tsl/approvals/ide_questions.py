"""ide-questions.json: the questions a step asked in the IDE, with when each was asked and answered.

One entry ("ask") per AskUserQuestion call. The pre-tool hook records it when the dialog opens,
the post-tool hook marks it answered and links the A-nn entries it wrote to ide-answers.md, and
an ask nobody answered (dismissed, skipped) is closed. `tsl state show --progress` shows the
open ones, so the panel shows a question while the engineer is asked it, and the engineer's
wait is `answered_at` (or `closed_at`) minus `asked_at` (roadmap B2, D1).

Only tsl writes the file (the pre-tool hook refuses Write and Edit on it). Recording is best
effort everywhere: a failure here never changes a hook decision or a run.

    {"schema": "ide-questions.v1", "run_id": "run_...",
     "asks": [{"ask_id": "ASK-01", "tool_use_id": "toolu_...", "agent_id": null,
               "step": "req", "attempt": 1, "source": "hook",
               "asked_at": "2026-11-25T10:00:00Z", "status": "open | answered | closed",
               "answered_at": null, "closed_at": null, "close_reason": null,
               "answers": ["A-01"],
               "questions": [{"id": "Q-01", "text": "...", "options": ["..."], "blocking": true}]}]}

On a host without AskUserQuestion (Copilot, Cursor) the model asks in plain chat and writes the
answers to a file for `tsl next <run_id> --answers <file>`, read by answered_from_file():

    {"schema": "ide-answers-input.v1", "ask_id": "ASK-01",
     "answers": [{"id": "Q-01", "answer": "Extend retention to 30 days"}]}
"""

from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path
from typing import Any

from tsl.approvals import ide_answers
from tsl.core.errors import TslError
from tsl.core.jsonio import write_json
from tsl.core.paths import ide_answers_path, ide_questions_path

SCHEMA = "ide-questions.v1"
ANSWERS_SCHEMA = "ide-answers-input.v1"
TEXT = 1000
# The id a question's text starts with: "Q-01: ...", "C7: ...", "REQ-9 - ...".
QID = re.compile(r"^\s*(?P<id>[A-Z]{1,6}-?[0-9]{1,3})\b\s*[:.)\-–]")


def _now() -> str:
    return dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _ts(s: Any) -> dt.datetime | None:
    try:
        t = dt.datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=dt.UTC)


def _path(root: Path, run_id: str) -> Path:
    return Path(root) / ide_questions_path(run_id)


def load(root: Path, run_id: str) -> dict[str, Any]:
    """The record, or an empty one when the file is missing or unreadable (a view)."""
    p = _path(root, run_id)
    empty: dict[str, Any] = {"schema": SCHEMA, "run_id": run_id, "asks": []}
    if not p.is_file():
        return empty
    try:
        obj = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return empty
    if not isinstance(obj, dict) or not isinstance(obj.get("asks"), list):
        return empty
    return obj


def _save(root: Path, run_id: str, obj: dict[str, Any]) -> None:
    write_json(_path(root, run_id), obj)


def question_id(text: str, n: int) -> str:
    m = QID.match(text or "")
    return m.group("id") if m else f"ASK-{n}"


def questions_of(tool_input: dict[str, Any]) -> list[dict[str, Any]]:
    """AskUserQuestion's questions as [{id, text, options, blocking}]."""
    out = []
    for i, q in enumerate(tool_input.get("questions") or [], start=1):
        if not isinstance(q, dict):
            continue
        text = ide_answers.one_line(q.get("question"), TEXT)
        opts = [
            ide_answers.one_line(o.get("label"), 300)
            for o in q.get("options") or []
            if isinstance(o, dict)
        ]
        # The run waits for the engineer while the dialog is open: every IDE question blocks.
        out.append({"id": question_id(text, i), "text": text, "options": opts, "blocking": True})
    return out


def _find(obj: dict[str, Any], ask_id: str) -> dict[str, Any] | None:
    return next((a for a in obj["asks"] if a.get("ask_id") == ask_id), None)


def find(root: Path, run_id: str, tool_use_id: str) -> str | None:
    """The ask recorded for this AskUserQuestion call, if any."""
    if not tool_use_id:
        return None
    a = next((a for a in load(root, run_id)["asks"] if a.get("tool_use_id") == tool_use_id), None)
    return str(a["ask_id"]) if a else None


def raised(
    root: Path,
    run_id: str,
    step: str,
    attempt: int,
    questions: list[dict[str, Any]],
    *,
    source: str,
    at: str | None = None,
    tool_use_id: str = "",
    agent_id: str | None = None,
) -> str:
    """Record questions put to the engineer; returns the ask_id.

    Idempotent: the same tool_use_id, or the same open questions of the same step attempt,
    give back the ask already recorded (`tsl next` and the hooks may both report one ask)."""
    obj = load(root, run_id)
    ids = [str(q.get("id")) for q in questions]
    for a in obj["asks"]:
        if tool_use_id and a.get("tool_use_id") == tool_use_id:
            return str(a["ask_id"])
        same = (a.get("step"), a.get("attempt")) == (step, int(attempt))
        if same and a.get("status") == "open" and [q["id"] for q in a["questions"]] == ids:
            if tool_use_id and not a.get("tool_use_id"):  # tsl next raised it, the dialog shows it
                a["tool_use_id"], a["asked_at"] = tool_use_id, at or _now()
                _save(root, run_id, obj)
            return str(a["ask_id"])
    ask_id = f"ASK-{len(obj['asks']) + 1:02d}"
    obj["asks"].append(
        {
            "ask_id": ask_id,
            "tool_use_id": tool_use_id or None,
            "agent_id": agent_id or None,
            "step": step,
            "attempt": int(attempt),
            "source": source,
            "asked_at": at or _now(),
            "status": "open",
            "answered_at": None,
            "closed_at": None,
            "close_reason": None,
            "answers": [],
            "questions": [
                {
                    "id": str(q.get("id")),
                    "text": ide_answers.one_line(q.get("text"), TEXT),
                    "options": [ide_answers.one_line(o, 300) for o in q.get("options") or []],
                    "blocking": bool(q.get("blocking", True)),
                }
                for q in questions
            ],
        }
    )
    _save(root, run_id, obj)
    return ask_id


def answered(
    root: Path,
    run_id: str,
    ask_id: str,
    answers: list[dict[str, Any]],
    *,
    answered_by: str,
    at: str | None = None,
) -> list[str]:
    """Record the engineer's answers ({question, options, answer}) in ide-answers.md, with the
    ask's real asked_at, and mark the ask answered; returns the new A-nn ids."""
    obj = load(root, run_id)
    a = _find(obj, ask_id)
    if a is None:
        raise KeyError(ask_id)
    at = at or _now()
    ids = ide_answers.append(
        Path(root) / ide_answers_path(run_id),
        run_id,
        str(a["step"]),
        int(a["attempt"]),
        str(a["asked_at"]),
        answered_by,
        str(a.get("tool_use_id") or ""),
        answers,
        answered_at=at,
    )
    a["status"], a["answered_at"] = "answered", at
    a["answers"] = [*a.get("answers", []), *ids]
    _save(root, run_id, obj)
    return ids


def _bad(path: Path, pointer: str, reason: str) -> TslError:
    return TslError("E-CFG-01", file=path.name, pointer=pointer, reason=reason)


def answered_from_file(
    root: Path, run_id: str, path: Path, *, answered_by: str, at: str | None = None
) -> list[str]:
    """Record an answers file (ide-answers-input.v1) against its ask; returns the A-nn ids.

    Every answer must name a question of that ask, once, with a non-empty answer; questions
    left out stay unanswered. A file that answers none closes the ask as skipped. An ask
    already answered returns its A-ids again, so a repeated `tsl next --answers` adds nothing."""
    try:
        obj = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise _bad(path, "/", f"not readable JSON ({type(exc).__name__})") from None
    if not isinstance(obj, dict) or obj.get("schema") != ANSWERS_SCHEMA:
        raise _bad(path, "/schema", f"must be {ANSWERS_SCHEMA}")
    ask = _find(load(root, run_id), str(obj.get("ask_id") or ""))
    if ask is None:
        raise _bad(path, "/ask_id", f"no ask {obj.get('ask_id')!r} in this run")
    if ask.get("status") == "answered":
        return list(ask.get("answers") or [])
    if ask.get("status") != "open":
        raise _bad(path, "/ask_id", f"{ask['ask_id']} is {ask.get('status')}, not open")
    raw = obj.get("answers")
    if not isinstance(raw, list):
        raise _bad(path, "/answers", "must be a list")
    by_id = {str(q["id"]): q for q in ask["questions"]}
    seen: set[str] = set()
    items: list[dict[str, Any]] = []
    for i, a in enumerate(raw):
        ptr = f"/answers/{i}"
        if not isinstance(a, dict):
            raise _bad(path, ptr, "must be an object {id, answer}")
        qid, ans = str(a.get("id") or ""), a.get("answer")
        if qid not in by_id:
            raise _bad(path, f"{ptr}/id", f"{qid!r} is not a question of {ask['ask_id']}")
        if qid in seen:
            raise _bad(path, f"{ptr}/id", f"{qid} answered twice")
        if not isinstance(ans, str) or not ans.strip() or len(ans) > TEXT:
            raise _bad(path, f"{ptr}/answer", f"a non-empty text of at most {TEXT} characters")
        seen.add(qid)
        q = by_id[qid]
        items.append({"question": q["text"], "options": q["options"], "answer": ans})
    if not items:
        closed(root, run_id, str(ask["ask_id"]), reason="skipped", at=at)
        return []
    return answered(root, run_id, str(ask["ask_id"]), items, answered_by=answered_by, at=at)


def closed(root: Path, run_id: str, ask_id: str, *, reason: str, at: str | None = None) -> None:
    """An open ask nobody answered (dismissed or skipped): its wait ends now."""
    obj = load(root, run_id)
    a = _find(obj, ask_id)
    if a is None or a.get("status") != "open":
        return
    a["status"], a["closed_at"], a["close_reason"] = "closed", at or _now(), reason
    _save(root, run_id, obj)


def close_open(
    root: Path,
    run_id: str,
    *,
    reason: str,
    agent_id: str | None = None,
    older_than_s: float = 0,
    at: str | None = None,
) -> int:
    """Close the open asks of this agent (None: the main session) asked at least older_than_s
    ago: the agent went on to another tool, so the dialog is gone. Returns how many closed."""
    if not _path(root, run_id).is_file():
        return 0
    obj = load(root, run_id)
    now = at or _now()
    t_now = _ts(now)
    n = 0
    for a in obj["asks"]:
        if a.get("status") != "open" or (a.get("agent_id") or None) != (agent_id or None):
            continue
        t = _ts(a.get("asked_at"))
        if t is not None and t_now is not None and (t_now - t).total_seconds() < older_than_s:
            continue  # a parallel tool call of the same message: the dialog may still be open
        a["status"], a["closed_at"], a["close_reason"] = "closed", now, reason
        n += 1
    if n:
        _save(root, run_id, obj)
    return n


def open_asks(root: Path, run_id: str) -> list[dict[str, Any]]:
    return [a for a in load(root, run_id)["asks"] if a.get("status") == "open"]


def waits(root: Path, run_id: str, now: str | None = None) -> dict[str, Any]:
    """The engineer's wait in seconds: per step, and in total. An open ask counts up to now."""
    t_now = _ts(now or _now())
    steps: dict[str, int] = {}
    for a in load(root, run_id)["asks"]:
        t0 = _ts(a.get("asked_at"))
        t1 = _ts(a.get("answered_at") or a.get("closed_at")) or t_now
        if t0 is None or t1 is None:
            continue
        sid = str(a.get("step"))
        steps[sid] = steps.get(sid, 0) + max(0, int((t1 - t0).total_seconds()))
    return {"total_s": sum(steps.values()), "steps": steps}
