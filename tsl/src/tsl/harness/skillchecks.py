"""Skill-declared checks (skill-checks.v1): the SDD-01 §9 library form (`uses`) and the
SDD-03 §5.2 kind form. Skills select reviewed functions; they never ship code."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
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
    named_inputs: dict[str, str] = field(default_factory=dict)  # step input name -> rel path


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


def _ide_answers_rel(env: CheckEnv) -> str | None:
    from tsl.core.paths import ide_answers_path

    run_id = str(env.front.get("run_id") or "")
    return ide_answers_path(run_id) if run_id else None


def _prior_answer_log(env: CheckEnv, path: str) -> bool:
    """runs/<run_id>/ide-answers.md of another run (data.prior_answers, B3). Only the post-tool
    hook writes these files, so a cite of one is the user's own earlier answer."""
    from tsl.harness.citations import IDE_ANSWERS

    return bool(IDE_ANSWERS.match(path)) and (env.root / path).is_file()


def c_cites_present(env: CheckEnv, w: dict[str, Any]) -> str | None:
    items = list(env.front.get("requirements", [])) + list(env.front.get("claims", []))
    allowed = set(env.input_paths)
    ide = _ide_answers_rel(env)
    if ide and (env.root / ide).is_file():
        allowed.add(ide)  # the user's own answers, recorded by the post-tool hook
    for it in items:
        cites = it.get("cites") or []
        if not cites:
            return f"{it.get('id')} has no citation"
        for c in cites:
            p = _cite_path(c)
            if not (p in allowed or p.startswith("context/") or _prior_answer_log(env, p)):
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
            elif path == _ide_answers_rel(env):
                # Only the cited answer counts, never another answer in the same log.
                from tsl.approvals import ide_answers

                cited += "".join(
                    f"{e.get('question', '')}\n{e.get('answer', '')}\n"
                    for e in ide_answers.parse(text)
                    if e["id"].lower() == anchor.lower()
                )
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


def c_answers_logged(env: CheckEnv, w: dict[str, Any]) -> str | None:
    """Answers the artifact says the user gave match ide-answers.md, and none were dropped.

    - every answers[] entry is in the log for this step, at this or an earlier attempt, with
      the same answer text;
    - every answer logged for this step and attempt is listed in answers[];
    - every requirement an answer names exists and cites that answer, and every cite of the
      log points at an answer listed in answers[];
    - every answer is used: it decides at least one requirement (an answered assumption
      decides its own REQ), unless the answer left its question open ("don't know"), in
      which case it decides none and the question stays in questions[].
    An item may also cite an answer logged for an earlier step of the same run (a decision
    already made upstream); it must exist in the log and is not listed in answers[].
    Every failure is reported, joined by "; ", so one write can fix them all.
    The answer wins over the ticket and baseline; the artifact records any difference in
    the answer's `mismatch`, which is not checked here.

    `with` (all optional; the defaults are the intent.v1 form used by requirement-review):
    targets: front-matter lists whose items an answer may decide (default ["requirements"]);
      items without an `id` are skipped;
    field: the key on each answer that lists the ids it decided (default "requirements");
    noun: the word for one decided item in failure messages (default "requirement").
    """
    from tsl.approvals import ide_answers

    f = env.front
    targets = [str(t) for t in (w.get("targets") or ["requirements"])]
    field_name = str(w.get("field") or "requirements")
    noun = str(w.get("noun") or "requirement")
    a_noun = f"an {noun}" if noun[:1].lower() in "aeiou" else f"a {noun}"
    ide = _ide_answers_rel(env)
    log = ide_answers.read(env.root / ide) if ide else []
    step, attempt = str(f.get("step") or ""), int(f.get("attempt") or 1)
    logged = {e["id"]: e for e in log if e.get("step") == step and e["attempt"] <= attempt}
    answers = list(f.get("answers") or [])
    listed = {str(a.get("id")) for a in answers}
    reqs: dict[str, dict[str, Any]] = {}
    for t in targets:  # with one target this is the original {r["id"]: r} map, last one wins
        for r in f.get(t) or []:
            # Items without an id (design.v1 components and endpoints may omit one) cannot be
            # decided by an answer; an answer that names them fails below as an unknown id.
            if isinstance(r, dict) and r.get("id"):
                reqs[str(r["id"])] = r
    open_q = {q["id"] for q in f.get("questions", [])}

    def cites_answer(r: dict[str, Any], aid: str) -> bool:
        want = f"{ide}#{aid}".lower()
        return any(
            str(c["ref"] if isinstance(c, dict) else c).lower() == want for c in r.get("cites", [])
        )

    fails: list[str] = []
    for a in answers:
        aid = str(a.get("id"))
        e = logged.get(aid)
        if e is None:
            fails.append(f"{aid} is not an answer the user gave for step {step} (see {ide})")
            continue
        if ide_answers.norm(a.get("answer")) != ide_answers.norm(e.get("answer")):
            fails.append(f"{aid} answer differs from the recorded answer")
        about, decided = a.get("about"), [str(x) for x in (a.get(field_name) or [])]
        if about in open_q and decided:
            fails.append(f"{about} was answered in {aid} but is still an open question")
        if about not in open_q and not decided:
            fails.append(f"{aid} is not used: it decides no {noun} and {about} is not kept open")
        if a.get("kind") == "assumption" and about not in decided:
            fails.append(f"{aid} answers the assumption in {about} but does not decide it")
        for rid in decided:
            if rid not in reqs:
                fails.append(f"{aid} names {rid}, which is not {a_noun}")
            elif not cites_answer(reqs[rid], aid):
                fails.append(f"{rid} does not cite {ide}#{aid.lower()}")
    for e in log:
        if e.get("step") == step and e["attempt"] == attempt and e["id"] not in listed:
            fails.append(f"{e['id']} was answered by the user but is not in answers")
    # Cites of the log: an answer of this step must be listed in answers[]; an answer logged
    # for an earlier step of the same run may be cited as a decision already made (B2).
    by_id = {str(e["id"]).upper(): e for e in log}
    prefix = f"{ide}#".lower() if ide else None
    for r in reqs.values():
        for c in r.get("cites") or []:
            ref = str(c["ref"] if isinstance(c, dict) else c)
            if not (prefix and ref.lower().startswith(prefix)):
                continue
            aid = ref.split("#", 1)[1].upper()
            if aid in listed:
                continue
            e = by_id.get(aid)
            if e is None:
                fails.append(f"{r['id']} cites {aid}, which is not in {ide}")
            elif e.get("step") == step:
                fails.append(f"{r['id']} cites {aid}, which is not listed in answers")
    return "; ".join(dict.fromkeys(fails)) or None


def c_assumed_basis(env: CheckEnv, w: dict[str, Any]) -> str | None:
    for r in env.front.get("requirements", []):
        if r.get("status") == "assumed" and (not r.get("basis") or not r.get("cites")):
            return f"{r['id']} assumed without basis and cite"
    return None


def c_contract_stated(env: CheckEnv, w: dict[str, Any]) -> str | None:
    """Every endpoint whose change is new or changed states its contract: at least one entry in
    `fields` (design.v1 endpoints[].fields). Existing and removed endpoints need none."""
    items, key = str(w.get("items", "endpoints")), str(w.get("field", "fields"))
    changes = list(w.get("change") or ["new", "changed"])
    for e in env.front.get(items) or []:
        if isinstance(e, dict) and e.get("change") in changes and not e.get(key):
            name = f"{e.get('method', '')} {e.get('path', '')}".strip() or str(e.get("name"))
            return f"{name} is {e.get('change')} but states no {key}"
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
    "answers.logged": c_answers_logged,
    "assumed.basis": c_assumed_basis,
    "contract.stated": c_contract_stated,
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


def _expand(env: CheckEnv, rel: str) -> str:
    """Fill {run_id} and {ticket} in a checks.yaml file path from the artifact being checked."""
    run_id = str(env.front.get("run_id") or "")
    ticket = ""
    for path in env.input_paths:
        m = re.match(rf"artifacts/([^/]+)/{re.escape(run_id)}/", path.replace("\\", "/"))
        if run_id and m:
            ticket = m.group(1)
            break
    return rel.replace("{run_id}", run_id).replace("{ticket}", ticket)


def _load_json(root: Path, rel: str) -> Any:
    p = root / rel
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except ValueError:
        return None


def _input_front(env: CheckEnv, name: str) -> dict[str, Any] | None:
    from tsl.core.frontmatter import FrontMatterError, split

    rel = env.named_inputs.get(name)
    p = env.root / rel if rel else None
    if p is None or not p.is_file():
        return None
    try:
        return dict(split(p.read_text(encoding="utf-8")).front)
    except (FrontMatterError, TypeError, ValueError):
        return None


def _coverage_items(env: CheckEnv, c: dict[str, Any]) -> list[Any] | str:
    """Items `each` selects, from the named input's front matter when `each_input` is set.
    `each_key` joins each item's `prefix` field with every value `select` finds under it
    (stories[] + acceptance_criteria[].id -> S-1/AC1). Returns failure detail as a str."""
    src: dict[str, Any] | None = env.front
    if c.get("each_input"):
        src = _input_front(env, str(c["each_input"]))
        if src is None:
            return f"input {c['each_input']} missing or has no front matter"
    items = select(src, c["each"])
    ek = c.get("each_key")
    if not ek:
        return items
    sep = str(ek.get("sep", "/"))
    keys: list[Any] = []
    for it in items:
        if isinstance(it, dict):
            keys.extend(f"{it.get(ek['prefix'])}{sep}{v}" for v in select(it, ek["select"]))
    return keys


def _kind_check(env: CheckEnv, c: dict[str, Any]) -> tuple[str, str]:
    kind = c["kind"]
    try:
        if kind == "lookup":
            data = _load_json(env.root, _expand(env, c["in"]["file"]))
            if data is None:
                return "fail", f"{_expand(env, c['in']['file'])} missing"
            have = {json.dumps(v, sort_keys=True) for v in select(data, c["in"]["path"])}
            for v in select(env.front, c["select"]):
                if json.dumps(v, sort_keys=True) not in have:
                    return "fail", f"value {v!r} not found"
            return "pass", ""
        if kind == "no-clash":
            data = _load_json(env.root, _expand(env, c["against"]["file"]))
            if data is None:
                return "fail", f"{_expand(env, c['against']['file'])} missing"
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
            items = _coverage_items(env, c)
            if isinstance(items, str):
                return "fail", items
            refs = select(env.front, c["covered_by"])
            link = c.get("link", "id")
            need = int(c.get("min", 1))
            # `link` names the id field: on the covering objects when covered_by selects objects
            # (stories[].trace), else on the items (results[].covers). List values hold several ids.
            refs_are_objects = any(isinstance(r, dict) for r in refs)
            flat: list[Any] = []
            for r in refs:
                v = r.get(link) if refs_are_objects and isinstance(r, dict) else r
                flat.extend(v if isinstance(v, list) else [v])
            for it in items:
                ident = it.get(link) if isinstance(it, dict) and not refs_are_objects else it
                for one in ident if isinstance(ident, list) else [ident]:
                    if sum(1 for r in flat if r == one) < need:
                        return "fail", f"{one} covered fewer than {need} times"
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
            paths = [c[k] for k in ("select", "each", "covered_by") if k in c]
            if isinstance(c.get("each_key"), dict) and "select" in c["each_key"]:
                paths.append(c["each_key"]["select"])
            for path in paths:
                try:
                    compile_path(path)
                except PathError as exc:
                    errs.append(f"{cid}: {exc}")
    return errs
