"""ide-answers.md: the questions a step asked the user in the IDE and what they answered.

The PostToolUse hook on AskUserQuestion appends one entry per answered question. Nothing
else may write the file (the pre-tool hook refuses Write and Edit on it), so an artifact can
cite an entry as proof of what the user said: `runs/<run_id>/ide-answers.md#a-01`.

Entry shape (one level-2 heading per answer; the heading anchors are the citation targets):

    ## A-01
    - step: req
    - attempt: 1
    - asked_at: 2026-11-02T10:00:00Z
    - answered_by: Jane Doe <jane@example.com>
    - tool_use_id: toolu_...
    - question: Q-01: Ticket asks for 30 days; the baseline keeps 24 hours. Which applies?
    - options: Extend retention to 30 days | Keep 24 hours
    - answer: Extend retention to 30 days
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

HEADER = (
    "# IDE answers: {run_id}\n\n"
    "Written by the tsl post-tool hook from AskUserQuestion. Do not edit: artifacts cite these\n"
    "entries as the user's own answers.\n"
)
HEAD = re.compile(r"^## (?P<id>A-[0-9]{2,})\s*$")
FIELD = re.compile(r"^- (?P<k>[a-z_]+): ?(?P<v>.*)$")
KEYS = (
    "step",
    "attempt",
    "asked_at",
    "answered_by",
    "tool_use_id",
    "question",
    "options",
    "answer",
)


def one_line(v: Any, limit: int = 1000) -> str:
    """Single line, no markdown heading or list syntax that could fake an entry."""
    s = re.sub(r"\s+", " ", str(v if v is not None else "")).strip()
    return s[:limit]


def parse(text: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    cur: dict[str, Any] | None = None
    for line in text.splitlines():
        m = HEAD.match(line)
        if m:
            cur = {"id": m.group("id")}
            out.append(cur)
            continue
        if cur is None:
            continue
        f = FIELD.match(line)
        if f and f.group("k") in KEYS:
            cur[f.group("k")] = f.group("v").strip()
    for e in out:
        try:
            e["attempt"] = int(e.get("attempt", 0))
        except ValueError:
            e["attempt"] = 0
    return out


def read(path: Path) -> list[dict[str, Any]]:
    return parse(path.read_text(encoding="utf-8")) if path.is_file() else []


def append(
    path: Path,
    run_id: str,
    step: str,
    attempt: int,
    asked_at: str,
    answered_by: str,
    tool_use_id: str,
    items: list[dict[str, Any]],
) -> list[str]:
    """Append one entry per {question, options, answer}; returns the new A-ids."""
    existing = read(path)
    n = max((int(e["id"][2:]) for e in existing), default=0)
    chunks: list[str] = []
    ids: list[str] = []
    for it in items:
        n += 1
        aid = f"A-{n:02d}"
        ids.append(aid)
        fields = {
            "step": one_line(step, 40),
            "attempt": str(int(attempt)),
            "asked_at": one_line(asked_at, 40),
            "answered_by": one_line(answered_by, 200),
            "tool_use_id": one_line(tool_use_id, 200),
            "question": one_line(it.get("question")),
            "options": " | ".join(one_line(o, 300) for o in it.get("options") or []),
            "answer": one_line(it.get("answer")),
        }
        chunks.append(f"\n## {aid}\n" + "".join(f"- {k}: {fields[k]}\n" for k in KEYS))
    if not chunks:
        return []
    path.parent.mkdir(parents=True, exist_ok=True)
    head = "" if path.is_file() else HEADER.format(run_id=run_id)
    with path.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(head + "".join(chunks))
    return ids


def norm(s: Any) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip().casefold()
