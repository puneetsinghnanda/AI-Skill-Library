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
    """A name or pseudonym, and no email address (Doc 4 section 3; SDD-02 open item 6).

    open-questions.md is committed to the companion repo, whose content check rejects email
    addresses (E-COMP-04), so an answer that needs one could never pass that check.
    """
    if not v or EMAIL.search(v):
        return False
    return bool(re.sub(r"[<>()\s,]", "", v))


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


def unanswered(path: Path, run_id: str) -> list[dict[str, Any]]:
    """The run's questions still open (no answer yet), oldest first, for the writer and the
    duplicate check. Each carries the cite a writer uses for it. [] when there is no file."""
    if not path.is_file():
        return []
    try:
        qs = parse(path.read_text(encoding="utf-8")).get("questions", [])
    except Exception:  # a hand-edited, broken file must not stop tsl next or decide
        return []
    first = originals(qs)
    out: list[dict[str, Any]] = []
    for qid, q in effective(qs).items():
        if (q.get("answer") or "").strip():
            continue
        o = first.get(qid, q)
        text = q["question"] if q.get("question") != "(revision)" else o.get("question", "")
        out.append(
            {
                "id": qid,
                "ask": q.get("ask") or o.get("ask") or "tech lead",
                "blocking": bool(q.get("blocking")),
                "question": str(text)[:300],
                "evidence": list(q.get("evidence") or o.get("evidence") or []),
                "cite": f"runs/{run_id}/open-questions.md#{qid.lower()}",
            }
        )
    return out


_IDS = re.compile(r"(?<![\w/-])(?!Q-)[A-Z]{1,5}-?[0-9]+(?![\w-])")
_WORD = re.compile(r"[a-z0-9]{4,}")
_STOP = frozenset(
    [
        "this",
        "that",
        "with",
        "what",
        "when",
        "which",
        "should",
        "would",
        "could",
        "does",
        "have",
        "from",
        "into",
        "they",
        "them",
        "their",
        "there",
        "these",
        "those",
        "than",
        "then",
        "also",
        "only",
        "about",
        "other",
        "some",
        "such",
        "will",
        "been",
        "being",
        "were",
        "your",
        "every",
        "each",
        "more",
        "most",
        "must",
        "need",
        "needs",
        "make",
        "made",
        "please",
        "answer",
        "question",
    ]
)


def _terms(q: dict[str, Any], ignore: set[str]) -> tuple[set[str], set[str]]:
    """Item ids named in the question or in its evidence anchors (never in paths, which all
    hold the ticket id), and its content words."""
    anchors = " ".join(str(e).split("#", 1)[1] for e in q.get("evidence") or [] if "#" in str(e))
    ids = set(_IDS.findall(f"{q.get('question', '')} {anchors}")) - ignore
    words = set(_WORD.findall(str(q.get("question", "")).lower())) - _STOP
    return ids, words


def duplicate_of(
    new: dict[str, Any], open_qs: list[dict[str, Any]], ignore: frozenset[str] = frozenset()
) -> str | None:
    """Id of an open question that `new` repeats, else None (HMS-21: Q-06 re-asked Q-05).

    Same recipient, and the same items (T-2, REQ-5 ...; `ignore` drops the ticket id) with
    some shared wording, or mostly the same wording. A warning only: decide still writes it."""
    skip = set(ignore)
    ids, words = _terms(new, skip)
    for q in open_qs:
        if str(q.get("ask")) != str(new.get("ask")):
            continue
        qids, qwords = _terms(q, skip)
        union = words | qwords
        jac = len(words & qwords) / len(union) if union else 0.0
        if (ids & qids and jac >= 0.15) or jac >= 0.5:
            return str(q["id"])
    return None


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
