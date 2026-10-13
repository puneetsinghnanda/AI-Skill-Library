"""Skill-declared checks (skill-checks.v1): the SDD-01 §9 library form (`uses`) and the
SDD-03 §5.2 kind form. Skills select reviewed functions; they never ship code."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tsl.core.frontmatter import headings, norm_title
from tsl.harness.jsonpath import PathError, select


@dataclass
class CheckOutcome:
    id: str
    gate: str  # H1..H7 or soft
    status: str  # pass | fail | skip
    detail: str = ""


@dataclass
class CheckEnv:
    front: dict[str, Any]
    body: str
    root: Path
    input_paths: list[str]
    input_texts: dict[str, str]


Fn = Callable[[CheckEnv, dict[str, Any]], str | None]  # returns failure detail or None
VAGUE = ["fast", "easy", "user-friendly", "etc.", "as appropriate", "quickly", "simple"]
NUM = re.compile(
    r"\b\d+(?:\.\d+)?\s?(?:ms|s|sec|seconds?|minutes?|mins?|hours?|h|days?|weeks?|"
    r"months?|%|percent|mb|gb|kb|items?|per page|requests?|p\d\d)?\b",
    re.I,
)


def _ids_seq(ids: list[str], prefix: str) -> str | None:
    nums = []
    for i in ids:
        m = re.match(rf"^{prefix}-(\d+)$", i)
        if not m:
            return f"id {i} does not match {prefix}-n"
        nums.append(int(m.group(1)))
    if len(set(nums)) != len(nums):
        return f"duplicate {prefix} ids"
    if sorted(nums) != list(range(1, len(nums) + 1)) and prefix == "REQ":
        return f"{prefix} ids have gaps"
    return None


def c_sections_present(env: CheckEnv, w: dict[str, Any]) -> str | None:
    want = [norm_title(s) for s in w.get("sections", [])]
    got = [norm_title(h.title) for h in headings(env.body) if h.level == 2]
    missing = [s for s in want if s not in got]
    if missing:
        return f"missing sections: {', '.join(missing)}"
    order = [g for g in got if g in want]
    if order != want:
        return "sections out of order"
    return None


def c_ids_sequence(env: CheckEnv, w: dict[str, Any]) -> str | None:
    f = env.front
    return (
        _ids_seq([r["id"] for r in f.get("requirements", [])], "REQ")
        or _ids_seq([u["id"] for u in f.get("unknowns", [])], "U")
        or _ids_seq([q["id"] for q in f.get("questions", [])], "Q")
    )


def c_ids_consistent(env: CheckEnv, w: dict[str, Any]) -> str | None:
    f = env.front
    reqs = f.get("requirements", [])
    by = {s: sorted(r["id"] for r in reqs if r.get("status") == s) for s in ("known", "assumed")}
    for s in ("known", "assumed"):
        if sorted(f.get(s, [])) != by[s]:
            return f"{s} list does not match requirements with status {s}"
    unk = sorted([u if isinstance(u, str) else u["id"] for u in f.get("unknown", [])])
    want_unk = sorted(u["id"] for u in f.get("unknowns", []))
    if unk != want_unk:
        return "unknown list does not match unknowns[]"
    trace = f.get("trace", [])
    if sorted(trace) != sorted(r["id"] for r in reqs):
        return "trace does not list every requirement"
    for i in [r["id"] for r in reqs] + want_unk:
        if not re.search(rf"(?<![\w-]){re.escape(i)}(?![\w])", env.body):
            return f"{i} not mentioned in the body"
    return None


def _cite_path(c: Any) -> str:
    ref = c["ref"] if isinstance(c, dict) else str(c)
    left = ref.split("#", 1)[0]
    return left.split(":", 1)[1] if ":" in left and not left.startswith("context/") else left


def c_cites_present(env: CheckEnv, w: dict[str, Any]) -> str | None:
    items = list(env.front.get("requirements", [])) + list(env.front.get("claims", []))
    allowed = set(env.input_paths)
    for it in items:
        cites = it.get("cites") or []
        if not cites:
            return f"{it.get('id')} has no citation"
        for c in cites:
            p = _cite_path(c)
            if not (p in allowed or p.startswith("context/")):
                return f"{it.get('id')} cites {p}, not a declared input"
    return None


def _norm_num(s: str) -> str:
    return re.sub(r"\s+", "", s.lower())


def c_values_sourced(env: CheckEnv, w: dict[str, Any]) -> str | None:
    from tsl.harness.citations import LINES

    for r in env.front.get("requirements", []):
        if r.get("status") != "known":
            continue
        cited = ""
        for c in r.get("cites", []):
            ref = c["ref"] if isinstance(c, dict) else str(c)
            path = _cite_path(c)
            text = env.input_texts.get(path)
            if text is None and (env.root / path).is_file():
                text = (env.root / path).read_text(encoding="utf-8", errors="replace")
            if text is None:
                continue
            anchor = ref.split("#", 1)[1] if "#" in ref else ""
            m = LINES.match(anchor)
            if m:
                lines = text.split("\n")
                lo, hi = int(m.group(1)), int(m.group(2) or m.group(1))
                cited += "\n".join(lines[max(0, lo - 1) : hi]) + "\n"
            else:
                cited += text
        for v in NUM.findall(str(r.get("statement", ""))):
            if v.strip() and _norm_num(v) not in _norm_num(cited):
                return f"{r['id']}: value '{v.strip()}' not in a cited line"
    return None


def c_questions_linked(env: CheckEnv, w: dict[str, Any]) -> str | None:
    qs = {q["id"]: q for q in env.front.get("questions", [])}
    for u in env.front.get("unknowns", []):
        if u.get("question") not in qs:
            return f"{u['id']} links to no question"
    for q in qs.values():
        if not q.get("ask") or not q.get("why") or not q.get("evidence"):
            return f"{q['id']} lacks ask, why or evidence"
        if q.get("blocking") and q.get("default") is not None:
            return f"{q['id']} is blocking but has a default"
    return None


def c_assumed_basis(env: CheckEnv, w: dict[str, Any]) -> str | None:
    for r in env.front.get("requirements", []):
        if r.get("status") == "assumed" and (not r.get("basis") or not r.get("cites")):
            return f"{r['id']} assumed without basis and cite"
    return None


def c_glossary_terms(env: CheckEnv, w: dict[str, Any]) -> str | None:
    p = env.root / "context" / "glossary.md"
    if not p.is_file():
        return None
    titles = {norm_title(h.title) for h in headings(p.read_text(encoding="utf-8"))}
    for g in env.front.get("glossary", []):
        if g.get("found") and norm_title(str(g["term"])) not in titles:
            return f"term '{g['term']}' not in glossary"
    return None


def c_vague_terms(env: CheckEnv, w: dict[str, Any]) -> str | None:
    for r in env.front.get("requirements", []):
        s = str(r.get("statement", "")).lower()
        for t in VAGUE:
            if re.search(rf"(?<![\w-]){re.escape(t)}(?![\w-])", s):
                return f"{r['id']} uses vague term '{t}'"
    return None


def c_size_limits(env: CheckEnv, w: dict[str, Any]) -> str | None:
    n = len(env.front.get("requirements", []))
    if not 1 <= n <= 60:
        return f"{n} requirements (1..60)"
    hs = headings(env.body)
    for h in hs:
        if norm_title(h.title) == "summary":
            from tsl.core.frontmatter import section_text

            sentences = [
                s
                for s in re.split(r"[.!?](\s|$)", section_text(env.body, h, hs))
                if s and s.strip()
            ]
            if len(sentences) > 5:
                return "summary longer than 5 sentences"
    return None


LIBRARY: dict[str, Fn] = {
    "sections.present": c_sections_present,
    "ids.sequence": c_ids_sequence,
    "ids.consistent": c_ids_consistent,
    "cites.present": c_cites_present,
    "values.sourced": c_values_sourced,
    "questions.linked": c_questions_linked,
    "assumed.basis": c_assumed_basis,
    "glossary.terms": c_glossary_terms,
    "text.vague_terms": c_vague_terms,
    "size.limits": c_size_limits,
}
# Checks that report through another mechanism, never run here.
DELEGATED = {"schema.valid": "H1", "cites.resolve": "S1"}
KINDS = {
    "lookup",
    "no-clash",
    "coverage",
    "count-match",
    "enum-file",
    "regex",
    "cites-required",
    "container",
    "diff-limit",
}


def _load_json(root: Path, rel: str) -> Any:
    p = root / rel
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except ValueError:
        return None


def _kind_check(env: CheckEnv, c: dict[str, Any]) -> tuple[str, str]:
    kind = c["kind"]
    try:
        if kind == "lookup":
            data = _load_json(env.root, c["in"]["file"])
            if data is None:
                return "fail", f"{c['in']['file']} missing"
            have = {json.dumps(v, sort_keys=True) for v in select(data, c["in"]["path"])}
            for v in select(env.front, c["select"]):
                if json.dumps(v, sort_keys=True) not in have:
                    return "fail", f"value {v!r} not found"
            return "pass", ""
        if kind == "no-clash":
            data = _load_json(env.root, c["against"]["file"])
            if data is None:
                return "fail", f"{c['against']['file']} missing"
            keys = c.get("key") or []

            def k(v: Any) -> str:
                return json.dumps(
                    [v.get(x) for x in keys] if keys and isinstance(v, dict) else v, sort_keys=True
                )

            have = {k(v) for v in select(data, c["against"]["path"])}
            for v in select(env.front, c["select"]):
                if k(v) in have:
                    return "fail", f"{k(v)} already exists"
            return "pass", ""
        if kind == "coverage":
            items = select(env.front, c["each"])
            refs = select(env.front, c["covered_by"])
            link = c.get("link", "id")
            need = int(c.get("min", 1))
            flat: list[Any] = []
            for r in refs:
                flat.extend(r if isinstance(r, list) else [r])
            for it in items:
                ident = it.get(link) if isinstance(it, dict) else it
                if sum(1 for r in flat if r == ident) < need:
                    return "fail", f"{ident} covered fewer than {need} times"
            return "pass", ""
        if kind == "regex":
            for v in select(env.front, c["select"]):
                s = str(v)
                if c.get("must") and not re.search(c["must"], s):
                    return "fail", f"value does not match {c['must']}"
                if c.get("must_not") and re.search(c["must_not"], s):
                    return "fail", f"value matches {c['must_not']}"
            return "pass", ""
        if kind == "cites-required":
            for v in select(env.front, c["select"]):
                if not (isinstance(v, dict) and v.get("cites")):
                    return "fail", "item without citation"
            return "pass", ""
    except (PathError, KeyError, TypeError) as exc:
        return "fail", f"check error: {type(exc).__name__}"
    return "skip", f"kind {kind} runs elsewhere"


def run_declared(env: CheckEnv, checks_doc: dict[str, Any] | None) -> list[CheckOutcome]:
    out: list[CheckOutcome] = []
    if not checks_doc:
        return out
    for c in checks_doc.get("checks", []):
        cid = str(c["id"])
        if "uses" in c:
            gate = "soft" if c.get("soft") else str(c.get("gate"))
            if c["uses"] in DELEGATED:
                continue
            fn = LIBRARY.get(str(c["uses"]))
            if fn is None:
                out.append(CheckOutcome(cid, gate, "fail", f"unknown library check {c['uses']}"))
                continue
            detail = fn(env, dict(c.get("with") or {}))
            out.append(CheckOutcome(cid, gate, "fail" if detail else "pass", detail or ""))
        else:
            gate = str(c.get("gate", "soft"))
            status, detail = _kind_check(env, c)
            out.append(CheckOutcome(cid, gate, status, detail))
    return out


def validate_declared(checks_doc: dict[str, Any]) -> list[str]:
    """tsl validate rules for checks.yaml (SDD-03 §5.3, SKL-V08)."""
    from tsl.harness.jsonpath import compile_path

    errs: list[str] = []
    seen: set[str] = set()
    skill = str(checks_doc.get("skill", ""))
    for c in checks_doc.get("checks", []):
        cid = str(c.get("id"))
        if cid in seen:
            errs.append(f"duplicate check id {cid}")
        seen.add(cid)
        if "uses" in c:
            if c["uses"] not in LIBRARY and c["uses"] not in DELEGATED:
                errs.append(f"{cid}: unknown library check {c['uses']}")
        else:
            if c.get("kind") not in KINDS:
                errs.append(f"{cid}: unknown kind")
            if not cid.startswith(skill.split("-")[0]) and cid.split(".")[0] not in skill:
                errs.append(f"{cid}: id must be prefixed by the skill")
            for k in ("select", "each", "covered_by"):
                if k in c:
                    try:
                        compile_path(c[k])
                    except PathError as exc:
                        errs.append(f"{cid}: {exc}")
    return errs
