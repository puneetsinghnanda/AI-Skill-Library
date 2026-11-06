"""Pieces of the pull-request body built from run artifacts (pilot feedback: say what changed).

All text here is model-written or engineer-written, so it is treated as untrusted: one line,
truncated, markdown-escaped, and @mentions defanged (SEC-01 §6.2). Nothing is executed or fetched.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from tsl.approvals import questions_md
from tsl.core.frontmatter import FrontMatterError, split

# A default that asks for work is flagged "needs action before merge" when it contains one of
# these (case-insensitive). Deliberately simple: a false flag costs a look. Plain verbs such as
# "add" or "must" are left out: defaults use them to describe the design choice itself (HMS-7 Q-03
# "Add to GET /api/doctors/:id as a read-only field"), not extra work.
ACTION_RULE = re.compile(
    r"before merg(?:e|ing)|on this branch|should be added|\btodo\b|\bfollow[- ]up\b",
    re.IGNORECASE,
)
# The backslash is escaped too, so "\<" cannot turn an escape back into live markup.
_SPECIAL = re.compile(r"([\\`*_{}\[\]<>()#+!|~])")
MAX_BULLETS = 8
FINDING_CHARS = 200


def md(text: Any, limit: int = 200) -> str:
    """One line, truncated, markdown-escaped, @mentions defanged."""
    s = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(s) > limit:
        s = s[: limit - 1].rstrip() + "…"
    s = _SPECIAL.sub(lambda m: "\\" + m.group(1), s.replace("&", "&amp;"))
    # zero-width space: no @mentions and no autolinked URLs
    return s.replace("@", "@​").replace("://", ":​//")


def _section(body: str, title: str) -> list[str]:
    out: list[str] = []
    on = False
    for line in body.split("\n"):
        if line.startswith("## "):
            on = line[3:].strip().lower() == title.lower()
            continue
        if on and line.startswith("- "):
            out.append(line[2:].strip())
    return out


def what_changed(comp_root: Path, impl_rel: str | None, design_rel: str | None) -> list[str]:
    """Bullets from the implement change record and the design; [] when neither is readable."""
    lines: list[str] = []
    front: dict[str, Any] = {}
    if impl_rel and (comp_root / impl_rel).is_file():
        try:
            doc = split((comp_root / impl_rel).read_text(encoding="utf-8"))
        except (FrontMatterError, OSError, UnicodeDecodeError):
            doc = None
        if doc is not None:
            front = dict(doc.front)
            if front.get("summary"):
                lines.append("- " + md(front["summary"], 400))
            files = _section(doc.body, "Changes")
            for f in files[:MAX_BULLETS]:
                path, sep, why = f.partition(" — ")
                lines.append(
                    f"- `{path.strip().replace('`', '')[:120]}`" + (f": {md(why)}" if sep else "")
                )
            if len(files) > MAX_BULLETS:
                lines.append(f"- … and {len(files) - MAX_BULLETS} more files in the change record")
            if not files:
                listed = [
                    x.get("files") or [] for x in front.get("code") or [] if isinstance(x, dict)
                ]
                flat = [str(p) for fl in listed for p in fl]
                lines += [f"- `{p.replace('`', '')[:120]}`" for p in flat[:MAX_BULLETS]]
    if design_rel and (comp_root / design_rel).is_file():
        try:
            dbody = split((comp_root / design_rel).read_text(encoding="utf-8")).body
        except (FrontMatterError, OSError, UnicodeDecodeError):
            dbody = ""
        eps = _endpoints(dbody)
        lines += [
            f"- API {md(e, 240)}" for e in eps[:MAX_BULLETS] if " — new" in e or " — changed" in e
        ]
    return lines


def _endpoints(dbody: str) -> list[str]:
    out: list[str] = []
    on = False
    for line in dbody.split("\n"):
        if line.startswith("## "):
            on = line[3:].strip().lower() == "components"
        elif on and line.strip() == "Endpoints:":
            out, on = [], True
            continue
        if on and line.startswith("- ") and re.match(r"^- (GET|POST|PUT|PATCH|DELETE) ", line):
            out.append(line[2:].strip())
        elif on and out and not line.strip():
            break
    return out


def pack_line(pack: dict[str, Any], repo: str | None, fresh_status: dict[str, Any] | None) -> str:
    """'built at abc1234, 3 commits behind' / 'up to date'; never 'fresh' when behind."""
    signed = pack.get("signed_at") or "never"
    if not fresh_status:
        return f"signed {signed} · distance from the code not checked"
    sb = fresh_status.get("state_block") or {}
    sha = (sb.get("source_sha") or {}).get(repo or "")
    behind = (sb.get("commits_behind") or {}).get(repo or "")
    at = f"built at {str(sha)[:7]}" if sha else "built"
    if behind is None:
        return f"signed {signed} · {at}, distance from the base not checked"
    state = "stale" if not sb.get("fresh") else ("up to date" if behind == 0 else "")
    if behind == 0:
        return f"signed {signed} · {at}, {state} (as of the last fetch)"
    tail = f"{behind} commit{'s' * (behind != 1)} behind" + (", stale" if state == "stale" else "")
    return f"signed {signed} · {at}, {tail} (as of the last fetch)"


def default_actions(text: str | None) -> bool:
    return bool(text and ACTION_RULE.search(text))


def unanswered(path: Path) -> list[dict[str, Any]]:
    """Non-blocking questions with no answer, latest revision of each."""
    if not path.is_file():
        return []
    try:
        qs = questions_md.parse(path.read_text(encoding="utf-8")).get("questions", [])
    except Exception:  # a broken file must not stop the PR
        return []
    return [
        q
        for q in questions_md.effective(qs).values()
        if not q.get("blocking") and not q.get("answer")
    ]


def question_lines(qs: list[dict[str, Any]]) -> list[str]:
    out = []
    for q in qs:
        d = q.get("proposed_default")
        flag = " ⚠ needs action before merge" if default_actions(d) else ""
        out.append(
            f"- {q['id']}: {md(q.get('question'), 200)} → default: "
            f"{md(d, 300) if d else 'no default'}{flag}"
        )
    return out


def finding_line(step: str, f: dict[str, Any]) -> str:
    text = md(f.get("text"), FINDING_CHARS)
    return f"- [{md(f.get('severity'), 20)}] {md(step, 20)}: {md(f.get('id'), 20)}" + (
        f" {text}" if text else ""
    )
