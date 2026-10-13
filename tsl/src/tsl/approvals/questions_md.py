"""open-questions.md: render rounds and parse answers (Doc 4 §3, SDD-02 §9.1, open-questions.v1)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from tsl.core.errors import TslError
from tsl.core.frontmatter import FrontMatterError, split
from tsl.core.hashing import sha256_text
from tsl.core.jsonio import atomic_write, dump_yaml

HEAD = re.compile(r"^## (?P<id>Q-[0-9]{2,})(?P<rest>.*)$")
LABEL = re.compile(
    r"^\*\*(?P<k>Question|Why it matters|Evidence|Options|Proposed default):\*\*\s?(?P<v>.*)$"
)
FIELD = re.compile(r"^(?P<k>answer|answered_by|decision|reason):\s?(?P<v>.*)$")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+")


def answer_hash(q: dict[str, Any]) -> str:
    return sha256_text(
        "\n".join(str(q.get(k) or "") for k in ("answer", "answered_by", "decision"))
    )


def valid_answered_by(v: str | None) -> bool:
    """US-04 AC1: a name and an email address (SDD-02 open item 6)."""
    if not v:
        return False
    m = EMAIL.search(v)
    if m is None:
        return False
    return bool(re.sub(r"[<>()\s,]", "", v.replace(m.group(0), "")))


def _strip_comment(v: str) -> str:
    return re.sub(r"\s+#.*$", "", v).strip()


def parse(text: str) -> dict[str, Any]:
    try:
        doc = split(text)
    except FrontMatterError as exc:
        raise TslError("E-CFG-01", file="open-questions.md", pointer="/", reason=str(exc)) from exc
    obj: dict[str, Any] = dict(doc.front)
    qs: list[dict[str, Any]] = []
    cur: dict[str, Any] | None = None
    last: str | None = None
    for line in doc.body.split("\n"):
        m = HEAD.match(line)
        if m:
            parts = [p.strip() for p in m.group("rest").split("·") if p.strip()]
            cur = {
                "id": m.group("id"),
                "round": 1,
                "blocking": False,
                "ask": "tech lead",
                "question": "(revision)",
                "answer": None,
                "answered_by": None,
                "decision": None,
            }
            for p in parts:
                if p in ("blocking", "non-blocking"):
                    cur["blocking"] = p == "blocking"
                elif p.startswith("ask:"):
                    cur["ask"] = p.split(":", 1)[1].strip()
                elif p.startswith("round"):
                    cur["round"] = int(p.split()[1])
                elif p.startswith("revision"):
                    cur["revision"] = int(p.split()[1])
            qs.append(cur)
            last = None
            continue
        if cur is None:
            continue
        lm = LABEL.match(line)
        if lm:
            k, v = lm.group("k"), lm.group("v").strip()
            last = k
            if k == "Question":
                cur["question"] = v or cur["question"]
            elif k == "Why it matters":
                cur["why"] = v
            elif k == "Evidence":
                cur["evidence"] = [x.strip().split(" ")[0] for x in v.split(",") if x.strip()]
            elif k == "Options":
                cur["options"] = []
            elif k == "Proposed default":
                cur["proposed_default"] = None if v.lower().startswith("none") else v
            continue
        fm = FIELD.match(line)
        if fm:
            k, v = fm.group("k"), _strip_comment(fm.group("v"))
            last = k
            cur[k] = v or None
            continue
        s = line.strip()
        if not s:
            continue
        if last == "Options" and re.match(r"^[A-Z]\.\s", s):
            cur.setdefault("options", []).append(s[3:].strip()[:300])
        elif last == "answer" and not s.startswith("<!--"):
            cur["answer"] = ((cur.get("answer") or "") + "\n" + s).strip()
        elif last == "Question":
            cur["question"] = (cur["question"] + " " + s).strip()
    obj["questions"] = qs
    return obj


def load(path: Path) -> dict[str, Any]:
    obj = parse(path.read_text(encoding="utf-8"))
    from tsl.schemas.registry import errors

    errs = errors("open-questions.v1", obj)
    if errs:
        raise TslError(
            "E-CFG-01", file="open-questions.md", pointer=errs[0].pointer, reason=errs[0].message
        )
    return obj


def effective(qs: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Question id -> latest revision block."""
    out: dict[str, dict[str, Any]] = {}
    for q in qs:
        prev = out.get(q["id"])
        if prev is None or int(q.get("revision", 1)) >= int(prev.get("revision", 1)):
            out[q["id"]] = q
    return out


def originals(qs: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for q in qs:
        if "revision" not in q and q["id"] not in out:
            out[q["id"]] = q
    return out


def append_round(
    path: Path,
    front: dict[str, Any],
    ticket: str,
    step: str,
    run_id: str,
    round_: int,
    questions: list[dict[str, Any]],
) -> None:
    if path.is_file():
        old = path.read_text(encoding="utf-8")
        doc = split(old)
        fm = dict(doc.front)
        fm.update({"status": "open", "step": front["step"]})
        body = doc.body.rstrip("\n")
    else:
        fm = front
        body = (
            f"\n# Open questions — {ticket} ({step} step)\n\nAnswer each question below the line "
            f"`answer:`. Keep the ids. Then run:\n`/truminds:resume {run_id}`"
        )
    lines = [body, ""]
    for q in questions:
        tag = "blocking" if q["blocking"] else "non-blocking"
        rnd = f" · round {round_}" if round_ > 1 else ""
        lines += [f"## {q['id']} · {tag} · ask: {q['ask']}{rnd}", f"**Question:** {q['question']}"]
        if q.get("why"):
            lines.append(f"**Why it matters:** {q['why']}")
        if q.get("evidence"):
            lines.append(f"**Evidence:** {', '.join(q['evidence'])}")
        if q.get("options"):
            lines.append("**Options:**")
            lines += [f"  {chr(65 + i)}. {o}" for i, o in enumerate(q["options"])]
        default = q.get("proposed_default")
        lines.append(f"**Proposed default:** {default if default else 'none'}")
        lines += ["answer:", "answered_by:", "decision:", ""]
    atomic_write(path, "---\n" + dump_yaml(fm) + "---\n" + "\n".join(lines))


def set_status(path: Path, status: str) -> None:
    doc = split(path.read_text(encoding="utf-8"))
    fm = dict(doc.front)
    fm["status"] = status
    atomic_write(path, "---\n" + dump_yaml(fm) + "---\n" + doc.body)
