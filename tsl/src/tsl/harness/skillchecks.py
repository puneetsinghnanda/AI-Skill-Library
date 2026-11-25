"""Skill-declared checks (skill-checks.v1): the SDD-01 §9 library form (`uses`) and the
SDD-03 §5.2 kind form. Skills select reviewed functions; they never ship code."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import cache
from importlib import resources
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
    answered: frozenset[str] = frozenset()  # question ids answered in this run (state.json)
    # Lines a code step added, by repo-relative path (`values-in-code`); None when the step
    # changed no product code or the clones are not here (eval, CI). Called at most once.
    code_added: Callable[[], dict[str, str]] | None = None


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


def c_cites_present(env: CheckEnv, w: dict[str, Any]) -> str | None:
    items = list(env.front.get("requirements", [])) + list(env.front.get("claims", []))
    allowed = set(env.input_paths)
    ide = _ide_answers_rel(env)
    if ide and (env.root / ide).is_file():
        allowed.add(ide)  # the user's own answers, recorded by the post-tool hook
    run_id = str(env.front.get("run_id") or "")
    if run_id:
        from tsl.core.paths import questions_path

        oq = questions_path(run_id)
        if (env.root / oq).is_file():
            allowed.add(oq)  # the run's open questions, written by tsl decide
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
    from tsl.approvals import questions_md
    from tsl.harness.citations import LINES, OPEN_QUESTIONS, QUESTION_ANCHOR

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
            elif OPEN_QUESTIONS.match(path):
                # Only the cited question's answer counts: never its text or proposed default
                # (a value the skill proposed is not known), never another question.
                qm = QUESTION_ANCHOR.match(anchor)
                qid = f"Q-{int(qm.group(1)):02d}" if qm else ""
                try:
                    eff = questions_md.effective(questions_md.parse(text).get("questions", []))
                except Exception:
                    eff = {}
                cited += str((eff.get(qid) or {}).get("answer") or "") + "\n"
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
    "named-in",
    "values-named",
    "values-in-code",
}
# Kinds that run outside `_kind_check`: container steps in the verifier (H3), diff limits in H6.
# Every other kind in KINDS must have a branch in `_kind_check`; one without fails, never skips,
# because gates count `skip` as a pass.
RUNS_ELSEWHERE = {"container", "diff-limit"}
WHERE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*(==|!=)\s*'([^']*)'\s*$")


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


ALLOWLIST_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\.txt")


@cache
def allowlist(name: str) -> dict[str, str] | None:
    """An `enum-file` allowlist shipped in tsl (harness/rules/<name>) as {value: tag}, or None when
    tsl ships no such file. One value per line: the value is the first word, the tag the last word
    (empty when the line holds only the value). Blank and `#` lines are skipped."""
    if not ALLOWLIST_NAME.fullmatch(name):
        return None
    f = resources.files("tsl.harness").joinpath("rules", name)
    if not f.is_file():
        return None
    rows = (ln.split() for ln in f.read_text(encoding="utf-8").splitlines())
    return {r[0]: r[-1] if len(r) > 1 else "" for r in rows if r and not r[0].startswith("#")}


def _count_files(env: CheckEnv, c: dict[str, Any]) -> int | str:
    """Files under root matching `count_files` (JSON), filtered by `where` (`field == 'value'` or
    `!=`). Returns the count, or failure detail as a str."""
    pattern = str(c["count_files"])
    if pattern.startswith(("/", "\\")) or ".." in Path(pattern).parts:
        return f"count_files {pattern} must stay inside the repo"
    cond = None
    if c.get("where"):
        cond = WHERE.match(str(c["where"]))
        if not cond:
            return f"where {c['where']!r} is not `field == 'value'`"
    n = 0
    for p in sorted(env.root.glob(pattern)):
        if not p.is_file():
            continue
        if cond is None:
            n += 1
            continue
        try:
            doc = json.loads(p.read_text(encoding="utf-8"))
        except ValueError:
            return f"{p.relative_to(env.root).as_posix()} is not valid JSON"
        field, op, want = cond.groups()
        have = doc.get(field) if isinstance(doc, dict) else None
        if (str(have) == want) == (op == "=="):
            n += 1
    return n


def _enum_file_problem(c: dict[str, Any]) -> str | None:
    """Why an `enum-file` check cannot run: no `file`, or tsl ships no such allowlist."""
    if not c.get("file"):
        return "enum-file check needs a `file`"
    if allowlist(str(c["file"])) is None:
        return f"allowlist {c['file']} is not shipped in tsl"
    return None


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


def _keyed(items: list[Any], spec: dict[str, Any]) -> list[str]:
    """Join each object's `prefix` field with every value `select` finds under it:
    stories[] + acceptance_criteria[].id -> S-1/AC1; results[] + covers[] -> TP-1/S-1/AC1."""
    sep = str(spec.get("sep", "/"))
    keys: list[str] = []
    for it in items:
        if isinstance(it, dict):
            keys.extend(f"{it.get(spec['prefix'])}{sep}{v}" for v in select(it, spec["select"]))
    return keys


def _select_from(
    env: CheckEnv, input_name: Any, path: str, key: dict[str, Any] | None
) -> list[Any] | str:
    """`path` over the artifact, or over a step input's front matter when `input_name` is set;
    keyed with `key` (see _keyed). Returns failure detail as a str."""
    src: dict[str, Any] | None = env.front
    if input_name:
        src = _input_front(env, str(input_name))
        if src is None:
            return f"input {input_name} missing or has no front matter"
    items = select(src, path)
    return _keyed(items, key) if key else items


def _names(spec: Any) -> list[str]:
    return [str(n) for n in spec] if isinstance(spec, list) else [str(spec)]


def _first_bound(env: CheckEnv, spec: Any) -> str | None:
    """`each_input` names one step input, or a list of which the first one the step has is used
    (threat-model: design, else architecture). A step has an input when the workflow binds it,
    whether or not its file exists: a bound design whose file is missing must fail, not fall back
    to the architecture. Only a step without a design (security-review) falls back."""
    for name in _names(spec):
        if env.named_inputs.get(name):
            return name
    return None


def _coverage_items(env: CheckEnv, c: dict[str, Any]) -> list[Any] | str:
    """Items `each` selects (keyed by `each_key`), from a step input when `each_input` is set.
    With `nonempty`, selecting nothing fails: an input with nothing to cover cannot pass.
    Returns failure detail as a str."""
    name = None
    if c.get("each_input"):
        name = _first_bound(env, c["each_input"])
        if name is None:
            return f"input {' or '.join(_names(c['each_input']))} missing or has no front matter"
    ek = c.get("each_key")
    items = _select_from(env, name, c["each"], ek)
    if isinstance(items, str):
        return items
    if c.get("nonempty") and not items:
        where = f"input {name}" if name else "the artifact"
        at = f"{c['each']} {ek['select']}" if ek else c["each"]
        return f"{where} has nothing to cover at {at}"
    return items


def _blocking_open(env: CheckEnv) -> bool:
    """The artifact asks a blocking question not yet answered in this run (questions[] or
    unknown[] with blocking: true), the same items `tsl decide` counts as S4."""
    qs = [q for q in env.front.get("questions") or [] if isinstance(q, dict)]
    us = [u for u in env.front.get("unknown") or [] if isinstance(u, dict)]
    return any(q.get("blocking") is True and q.get("id") not in env.answered for q in qs + us)


def _input_absent(env: CheckEnv, c: dict[str, Any]) -> bool:
    """`optional_input`: the step has none of the `each_input` inputs (a defect run's unit-test has
    no stories), so the check does not apply. Without it a missing input fails, as before."""
    return bool(
        c.get("optional_input") and c.get("each_input") and not _first_bound(env, c["each_input"])
    )


def _section_text(env: CheckEnv, titles: list[str]) -> str:
    """The text of the body's level-2 sections with these titles (case and spacing ignored)."""
    from tsl.core.frontmatter import section_text

    want = {norm_title(t) for t in titles}
    hs = headings(env.body)
    return "\n".join(
        section_text(env.body, h, hs) for h in hs if h.level == 2 and norm_title(h.title) in want
    )


def _word_in(word: str, text: str) -> bool:
    return re.search(rf"(?<![\w-]){re.escape(word)}(?![\w])", text) is not None


# An id with a letter part and a number (AC3), optionally a range up to another (AC1-AC3, AC1 to 3).
_RANGE_TAIL = r"(?:\s*(?:[-–]|\bto\b)\s*(?:{p})?(?P<hi>\d+)\b)?"


def named_keys(text: str, prefixes: set[str], suffix_letters: set[str], sep: str = "/") -> set[str]:
    """Keys '<prefix><sep><suffix>' named in text. A suffix belongs to the prefix named last before
    it in the same bullet or paragraph (a wrapped line continues it), so "S-2 AC1/AC3", "S-2/AC1",
    "S-3 AC1 to AC3", "(S-4 AC1, S-5 AC2)" and "S-1: column shown (AC1), cut at 60 (AC2)" all
    count. A range names every id in it."""
    if not prefixes or not suffix_letters:
        return set()
    pre = "|".join(re.escape(x) for x in sorted(prefixes, key=len, reverse=True))
    letters = "|".join(re.escape(x) for x in sorted(suffix_letters, key=len, reverse=True))
    tok = re.compile(
        rf"(?<![\w-])(?P<pre>{pre})(?![\w])|(?<![A-Za-z])(?P<let>{letters})(?P<n>\d+)\b"
        + _RANGE_TAIL.format(p=letters)
    )
    out: set[str] = set()
    cur: str | None = None
    for line in text.splitlines():
        if not line.strip() or re.match(r"\s*(?:[-*+]|\d+[.)])\s", line):
            cur = None  # a new bullet or paragraph starts
        for m in tok.finditer(line):
            if m.group("pre"):
                cur = m.group("pre")
                continue
            if cur is None:
                continue
            lo = int(m.group("n"))
            hi = int(m.group("hi")) if m.group("hi") else lo
            if not 0 <= hi - lo <= 20:
                hi = lo
            out.update(f"{cur}{sep}{m.group('let')}{i}" for i in range(lo, hi + 1))
    return out


def named_set(items: list[str], sep: str, text: str) -> set[str]:
    """The items named in text: a plain item (REQ-3) as a word, a keyed one (S-1/AC2) when
    named_keys finds its prefix named before its suffix in one bullet. S-1/AC01 names S-1/AC1."""
    keys = [k for k in items if sep in k]
    prefixes = {k.split(sep, 1)[0] for k in keys}
    letters = {re.sub(r"\d+$", "", k.split(sep, 1)[1]) for k in keys} - {""}
    found = named_keys(text, prefixes, letters, sep)
    out: set[str] = set()
    for k in items:
        if sep not in k:
            if _word_in(k, text):
                out.add(k)
            continue
        pre, sfx = k.split(sep, 1)
        m = re.match(r"^(\D*)0*(\d+)$", sfx)
        if k in found or (m is not None and f"{pre}{sep}{m.group(1)}{int(m.group(2))}" in found):
            out.add(k)
    return out


# A value list after a word: "Status is SCHEDULED, COMPLETED, CANCELLED or NO_SHOW" (data model of
# the sample system). Upper or Title case values, three or more.
_VALUE = r"(?:[A-Z][A-Z0-9_]{2,}|[A-Z][a-z]+(?:-[a-z]+)?)"
_VSEP = r"\s*(?:,\s*(?:or\s+|and\s+)?|\s+or\s+|\s+and\s+|\s*\|\s*|\s*/\s*)"


def lists_after(text: str, word: str) -> list[list[str]]:
    """Value lists that follow `word` (or its plural) in text, three values or more; a list inside
    a longer one is dropped."""
    return [v for v, _owner in owned_lists_after(text, word)]


def owned_lists_after(text: str, word: str) -> list[tuple[list[str], str]]:
    """lists_after, each with its owner: the title of the heading the list sits under, as a
    singular lower-case noun ("## Appointments" -> "appointment"; "" when there is none)."""
    rx = re.compile(
        rf"\b{re.escape(word)}(?:e?s)?\b[^.;:\n]{{0,40}}?(?:\bis\b|\bare\b|\bone of\b|:)\s*"
        rf"((?:{_VALUE}{_VSEP})+{_VALUE})",
        re.I,
    )
    out: list[tuple[list[str], str]] = []
    owner = ""
    for block in re.split(r"(?m)^(?=#{1,6}\s)", text):
        h = re.match(r"#{1,6}\s+([^{\n]*)", block)
        if h:
            words = re.findall(r"[A-Za-z]+", h.group(1))
            owner = _singular(words[-1].lower()) if words else ""
        for m in rx.finditer(re.sub(r"\s+", " ", block)):
            vals = list(dict.fromkeys(v for v in re.split(_VSEP, m.group(1)) if v))
            if len(vals) >= 3 and all(vals != o[0] for o in out):
                out.append((vals, owner))
    keys = [{_vnorm(v) for v in vals} for vals, _ in out]
    return [o for o, k in zip(out, keys, strict=True) if not any(k < x for x in keys)]


def _singular(w: str) -> str:
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 3 and w.endswith("s") and not w.endswith(("ss", "us", "is")):
        return w[:-1]
    return w


def _vnorm(v: str) -> str:
    return re.sub(r"[^a-z0-9]", "", v.lower())


def value_pattern(value: str, *, code: bool = False) -> re.Pattern[str]:
    """NO_SHOW matches No-show, NO_SHOW and No show. In prose the first letter must be upper case,
    so the word "scheduled" in a sentence is not the status Scheduled; in code any case counts."""
    parts = re.findall(r"[A-Za-z0-9]+", value)
    if not parts:
        return re.compile(r"(?!x)x")
    first = parts[0]
    head = (
        f"(?i:{re.escape(first)})"
        if code
        else re.escape(first[0].upper()) + (f"(?i:{re.escape(first[1:])})" if first[1:] else "")
    )
    rest = "".join(rf"[\s_-]?(?i:{re.escape(x)})" for x in parts[1:])
    return re.compile(rf"(?<![A-Za-z0-9]){head}{rest}(?![A-Za-z0-9])")


_CLOCK = re.compile(r"\b\d{1,2}:\d{2}\b")
_IDS = re.compile(r"\b(?:S|REQ|AC|A|Q|U|C|T|TP|D|CO|F)-?\d+\b")
_NUMBER = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)(?:st|nd|rd|th)?(?![\w.])")


def values_of(text: str) -> list[str]:
    """The values an AC fixes: clock times, and numbers of two digits or more (ids such as S-2,
    AC1 and REQ-4 left out). Test data that builds the AC's case holds at least one of them."""
    t = _IDS.sub(" ", text)
    out = _CLOCK.findall(t)
    t = _CLOCK.sub(" ", t)
    out += [n for n in _NUMBER.findall(t) if len(n.split(".")[0]) >= 2 or "." in n]
    return list(dict.fromkeys(out))


def _value_in_code(value: str, code: str) -> bool:
    if ":" in value:
        h, m = value.split(":")
        return re.search(rf"(?<!\d)0?{int(h)}:{m}(?!\d)", code) is not None
    return re.search(rf"(?<![\d.]){re.escape(value)}(?!\d)", code) is not None


def _values_named(env: CheckEnv, c: dict[str, Any]) -> tuple[str, str]:
    """Every value of a list named in a context file (`values`: file + the word the list
    follows) appears in the `text` of at least one `each` object. With `when`, only objects
    linked to an input item that is about those values count: an item whose `text` names one of
    the values, or the word together with the list's owner (the heading it sits under:
    "appointment statuses"). story-split: stories whose REQ is about appointment statuses."""
    spec = c["values"]
    rel = _expand(env, str(spec["file"]))
    p = env.root / rel
    if not p.is_file():
        return "skip", f"{rel} missing"
    lists = owned_lists_after(p.read_text(encoding="utf-8", errors="replace"), str(spec["after"]))
    if not lists:
        return "skip", f"no {spec['after']} list in {rel}"
    groups = [g for g in select(env.front, c["each"]) if isinstance(g, dict)]
    when = c.get("when")
    word = re.compile(rf"\b{re.escape(str(spec['after']))}(?:e?s)?\b", re.I)
    problems: list[str] = []
    for values, owner in lists:
        # About these values: the item names one of them, or the word together with the list's
        # owner ("appointment statuses"); "status filter" on a doctor list is another status.
        own = re.compile(rf"\b{re.escape(owner)}(?:e?s)?\b", re.I) if owner else None
        about = groups
        if when:
            src = _input_front(env, str(when["input"]))
            if src is None:
                return "skip", f"no {when['input']} input in this step"
            linked: set[str] = set()
            for it in select(src, when["each"]):
                if not isinstance(it, dict):
                    continue
                t = str(it.get(when.get("text", "statement")) or "")
                named = any(value_pattern(v).search(t) for v in values)
                if named or (word.search(t) and (own is None or own.search(t))):
                    linked.add(str(it.get("id")))
            link = str(when.get("link", "trace"))
            about = [g for g in groups if linked & {str(x) for x in (g.get(link) or [])}]
        if not about:
            continue
        text = "\n".join(str(t) for g in about for t in select(g, c["text"]))
        gone = [v for v in values if not value_pattern(v).search(text)]
        if gone:
            ids = ", ".join(str(g.get("id")) for g in about)
            problems.append(f"{', '.join(gone)} (from {rel}) named by none of {ids}")
    return ("fail", "; ".join(problems)) if problems else ("pass", "")


def _values_in_code(env: CheckEnv, c: dict[str, Any]) -> tuple[str, str]:
    """For each item named in `named_in` sections (an AC a Tests line says is covered), at least
    one value it fixes (values_of its text) appears in the lines the step added to files matching
    `files` (its tests). A 21st row on page 2 needs 21 rows; a fixture of 5 cannot hold it."""
    each, items_path = c["each"], c["items"]  # a declaration without them fails, never skips
    if _input_absent(env, c):
        return "skip", f"no {' or '.join(_names(c['each_input']))} input in this step"
    if env.code_added is None:
        return "skip", "no product code change to read"
    src = _first_bound(env, c["each_input"]) if c.get("each_input") else None
    groups = _select_from(env, src, each, None)
    if isinstance(groups, str):
        return "fail", groups
    sep = " "
    named_text = _section_text(env, _names(c.get("named_in") or ["Tests"]))
    keys = [
        f"{g.get('id')}{sep}{a.get('id')}"
        for g in groups
        if isinstance(g, dict)
        for a in select(g, items_path)
        if isinstance(a, dict)
    ]
    found = named_set(keys, sep, named_text)
    fx = re.compile(str(c.get("files") or r"."))
    code = "\n".join(t for path, t in env.code_added().items() if fx.search(path))
    code = re.sub(r"(?<=\d)_(?=\d)", "", code)  # 50_000 is 50000
    missing: list[str] = []
    for g in groups:
        if not isinstance(g, dict):
            continue
        for a in select(g, items_path):
            if not isinstance(a, dict):
                continue
            key = f"{g.get('id')}{sep}{a.get('id')}"
            if key not in found:
                continue
            vals = values_of(str(a.get("text") or ""))
            if vals and not any(_value_in_code(v, code) for v in vals):
                missing.append(f"{key} ({', '.join(vals[:4])})")
    if missing:
        return "fail", "no added test line holds a value of " + "; ".join(missing[:10])
    return "pass", ""


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
            # A step that stops to ask cannot cover everything yet; `tsl decide` sends it to
            # NEEDS-INPUT on the open question, and the check runs again after the answer.
            if c.get("defer_on_blocking") and _blocking_open(env):
                return "skip", "blocking question open; checked after the answer"
            if _input_absent(env, c):
                return "skip", f"no {' or '.join(_names(c['each_input']))} input in this step"
            items = _coverage_items(env, c)
            if isinstance(items, str):
                return "fail", items
            refs = _select_from(
                env, c.get("covered_by_input"), c["covered_by"], c.get("covered_by_key")
            )
            if isinstance(refs, str):
                return "fail", refs
            link = c.get("link", "id")
            need = int(c.get("min", 1))
            # `link` names the id field: on the covering objects when covered_by selects objects
            # (stories[].trace), else on the items (results[].covers). List values hold several ids.
            refs_are_objects = any(isinstance(r, dict) for r in refs)
            flat: list[Any] = []
            for r in refs:
                v = r.get(link) if refs_are_objects and isinstance(r, dict) else r
                flat.extend(v if isinstance(v, list) else [v])
            # `or_named_in`: an item named in one of these body sections (Unknown) is accounted
            # for, with its reason there, instead of covered.
            excused = _section_text(env, _names(c["or_named_in"])) if c.get("or_named_in") else ""
            short: list[str] = []
            for it in items:
                ident = it.get(link) if isinstance(it, dict) and not refs_are_objects else it
                for one in ident if isinstance(ident, list) else [ident]:
                    if sum(1 for r in flat if r == one) >= need:
                        continue
                    if excused and _word_in(str(one), excused):
                        continue
                    if not c.get("or_named_in"):  # as before: the first item short
                        return "fail", f"{one} covered fewer than {need} times"
                    short.append(str(one))
            if short:
                # With or_named_in, every short item at once, so the skill fixes them together.
                short = list(dict.fromkeys(short))
                where = f" and not named under {' or '.join(_names(c['or_named_in']))}"
                return "fail", f"{', '.join(short)} covered fewer than {need} times{where}"
            return "pass", ""
        if kind == "named-in":
            if _input_absent(env, c):
                return "skip", f"no {' or '.join(_names(c['each_input']))} input in this step"
            items = _coverage_items(env, c)
            if isinstance(items, str):
                return "fail", items
            sections = _names(c["sections"])
            text = _section_text(env, sections)
            sep = str((c.get("each_key") or {}).get("sep", "/"))
            keys = [str(i) for i in items]
            found = named_set(keys, sep, text)
            missing = [k for k in keys if k not in found]
            if missing:
                shown = ", ".join(m.replace(sep, " ") for m in missing[:20])
                more = f" and {len(missing) - 20} more" if len(missing) > 20 else ""
                return "fail", f"{shown}{more} not named in {' or '.join(sections)}"
            return "pass", ""
        if kind == "values-named":
            return _values_named(env, c)
        if kind == "values-in-code":
            return _values_in_code(env, c)
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
        if kind == "enum-file":
            problem = _enum_file_problem(c)
            if problem:
                return "fail", problem
            allowed = allowlist(str(c["file"])) or {}
            field, tag = c.get("value"), c.get("tag")
            for it in select(env.front, c["select"]):
                # With `value`, select picks objects: their `value` field must be in the list, and
                # their `tag` field (if set) must equal the last word on that value's line.
                v = it.get(field) if field and isinstance(it, dict) else it
                if str(v) not in allowed:
                    return "fail", f"value {v!r} is not in {c['file']}"
                if tag and isinstance(it, dict) and str(it.get(tag)) != allowed[str(v)]:
                    return "fail", (
                        f"{v}: {tag} {it.get(tag)!r}, but {c['file']} lists {allowed[str(v)]!r}"
                    )
            return "pass", ""
        if kind == "count-match":
            claimed = select(env.front, c["select"])
            if len(claimed) != 1 or not isinstance(claimed[0], int) or isinstance(claimed[0], bool):
                return "fail", f"{c['select']} must select one whole number"
            counted = _count_files(env, c)
            if isinstance(counted, str):
                return "fail", counted
            if claimed[0] != counted:
                where = f" where {c['where']}" if c.get("where") else ""
                return "fail", f"{c['select']} is {claimed[0]}, but {counted} files match{where}"
            return "pass", ""
    except (PathError, KeyError, TypeError, ValueError, re.error) as exc:
        return "fail", f"check error: {type(exc).__name__}"
    if kind in RUNS_ELSEWHERE:
        return "skip", f"kind {kind} runs elsewhere"
    return "fail", f"kind {kind} has no check in tsl"


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


def validate_declared(checks_doc: dict[str, Any], inputs: set[str] | None = None) -> list[str]:
    """tsl validate rules for checks.yaml (SDD-03 §5.3, SKL-V08). With `inputs` (the skill.yaml
    input names), every input a check reads must be one the skill declares."""
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
            problem = _enum_file_problem(c) if c.get("kind") == "enum-file" else None
            if problem:
                errs.append(f"{cid}: {problem}")
            if not cid.startswith(skill.split("-")[0]) and cid.split(".")[0] not in skill:
                errs.append(f"{cid}: id must be prefixed by the skill")
            need = {
                "named-in": ("each", "sections"),
                "values-named": ("values", "each", "text"),
                "values-in-code": ("each", "items"),
            }.get(str(c.get("kind")), ())
            for k in need:
                if not c.get(k):
                    errs.append(f"{cid}: kind {c['kind']} needs {k}")
            if c.get("files"):
                try:
                    re.compile(str(c["files"]))
                except re.error as exc:
                    errs.append(f"{cid}: files is not a valid regex: {exc}")
            if inputs is not None:
                for k in ("each_input", "covered_by_input"):
                    for name in _names(c[k]) if c.get(k) else []:
                        if name not in inputs:
                            errs.append(f"{cid}: {k} {name} is not an input of the skill")
                when_input = (c.get("when") or {}).get("input")
                if when_input and when_input not in inputs:
                    errs.append(f"{cid}: when.input {when_input} is not an input of the skill")
            paths = [c[k] for k in ("select", "each", "covered_by", "text", "items") if k in c]
            if isinstance(c.get("when"), dict) and "each" in c["when"]:
                paths.append(c["when"]["each"])
            for k in ("each_key", "covered_by_key"):
                if isinstance(c.get(k), dict) and "select" in c[k]:
                    paths.append(c[k]["select"])
            for path in paths:
                try:
                    compile_path(path)
                except PathError as exc:
                    errs.append(f"{cid}: {exc}")
    return errs
