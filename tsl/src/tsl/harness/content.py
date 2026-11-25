"""Content self-check for story-split (stories.v1) and unit-test (ut-result.v1): roadmap A3.

The gates check an artifact's shape; the reviewer checks its content. In the eight brownfield
lite runs on 0.1.7, `split` and `ut` each retried in 6 of 7 team runs, almost always on a
reviewer finding the step could have found itself: a status partition with no AC or test
(HMS-23, 24, 31), no AC on the boundary (HMS-23, 30), a "most recent" rule checked with one
candidate (HMS-24, 26), a default value that a hard-coded constant also passes (HMS-26), an AC
named as covered whose test data cannot reach it (HMS-30: 21 rows needed, fixture has 5;
HMS-33), a REQ dropped from the ut trace (HMS-28), a changed page with no test (HMS-24), a
user's decision no test guards (HMS-26).

`tsl verify --self-check` turns the artifact, its inputs and the run's answers into two lists:

- fix: definite gaps that code can prove (an AC of the stories that no Tests line names, a REQ
  traced by the stories missing from the ut trace). The skill fixes each one.
- check: targeted questions, one per REQ, story, AC or answer, naming the exact case the
  reviewer looks for. Text heuristics find them, so the skill answers each: when the artifact
  already covers it, nothing changes; otherwise it adds or tightens an AC or a test.

Never raises on odd input: a key that is missing or of the wrong type gives no items. Pure
functions take parsed data; `gather` reads it from the companion and product repos."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tsl.core.frontmatter import headings, norm_title, section_text

MAX_CHECK = 25  # check items per self-check; the first ones by priority are kept
TEST_FILE = re.compile(r"(^|/)(test|tests|__tests__)/|\.(test|spec)\.[a-z]+$")
SOURCE_EXT: tuple[str, ...] = (
    *(".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".py", ".java", ".kt", ".go"),
    *(".rb", ".cs", ".scala", ".vue", ".svelte"),
)
# Stems too generic to tell whether a test exercises the file.
GENERIC_STEMS = frozenset({"index", "main", "types", "type", "constants", "config", "app"})

# A list of status values after the word "status": "Status is SCHEDULED, COMPLETED, CANCELLED or
# NO_SHOW" (data-model.md of the sample system). Upper case or Title-case values, three or more.
_VALUE = r"(?:[A-Z][A-Z0-9_]{2,}|[A-Z][a-z]+(?:-[a-z]+)?)"
_SEP = r"\s*(?:,\s*(?:or\s+|and\s+)?|\s+or\s+|\s+and\s+|\s*\|\s*|\s*/\s*)"
STATUS_LIST = re.compile(
    rf"\b[Ss]tatus(?:es)?\b[^.;:\n]{{0,40}}?(?:\bis\b|\bare\b|\bone of\b|:)\s*"
    rf"((?:{_VALUE}{_SEP})+{_VALUE})"
)

# Keyword families in a REQ statement and what the reviewer then looks for.
CHECKS: tuple[tuple[str, re.Pattern[str], str], ...] = (
    (
        "boundary",
        re.compile(
            r"\b((?:after|before|until|since)\s+(?:now|today|midnight|noon|the (?:start|end|date|"
            r"time|deadline)|\d+)|at most|at least|(?<!add )up to|more than|less than|"
            r"fewer than|within|limit|maximum|minimum|per page|page size|older than|newer than|"
            r"between|range|"
            r"expir\w*|in the past|in the future|overdue|exceed\w*)\b",
            re.I,
        ),
        "an AC exactly on the limit and one just past it, each with its result, so >= "
        "instead of > (or an exclusive end date) fails",
    ),
    (
        "order",
        re.compile(
            r"\b(latest|most recent|newest|oldest|earliest|next(?!\s+to\b)|previous|"
            r"(?:last|first)(?!\s+\d)|"
            r"ordered|sorted|sort|in (?:the )?order|order by|order of)\b",
            re.I,
        ),
        "an AC with at least two candidates, where picking the wrong one (first loaded, "
        "earliest, any status) gives a different Then",
    ),
    (
        "unchanged",
        re.compile(
            r"\b(unchanged|as before|same as before|still|no change|not change|keeps?|"
            r"regression|as today)\b",
            re.I,
        ),
        "one AC per partition (each status; with and without the new item), not one example",
    ),
    (
        "exclusion",
        re.compile(r"\b(never|not shown|exclud\w*|except|hidden|hide|omit\w*|no longer)\b", re.I),
        "an AC where the excluded item is the most tempting one (most recent, same day, "
        "same owner)",
    ),
    (
        "default",
        re.compile(r"\b(default|setting|configur\w*|time ?zone|locale|currency)\b", re.I),
        "an AC with a non-default value, so a hard-coded default fails",
    ),
    (
        "count",
        re.compile(r"\b(counts?(?!\s+as\b)|counted|total|sum|number of|how many)\b", re.I),
        "an AC where a naive count differs (other statuses, other owners, rows beyond "
        "the first page)",
    ),
    (
        "filter",
        re.compile(r"\b(filter\w*|search\w*|combin\w*)\b", re.I),
        "one AC per filter it combines with, and one where an item matches twice (two "
        "child rows), so a join that repeats rows fails",
    ),
)
LOCAL_DATE = re.compile(r"\b(local|time ?zone|utc|midnight|today|yesterday|tomorrow)\b", re.I)
# A REQ whose result depends on the status partition: counts, unchanged behaviour, filters.
PARTITION = re.compile(
    r"\b(counts?(?!\s+as\b)|counted|total|number of|unchanged|as before|still|filter\w*|"
    r"booked|free|upcoming|closed|open)\b",
    re.I,
)
CLOCK = re.compile(r"\b\d{1,2}:\d{2}\b")
ORDER_AC = re.compile(
    r"\b(latest|most recent|newest|oldest|earliest|next(?!\s+to\b)|previous)\b", re.I
)
ERROR_PATH = re.compile(
    r"\b(errors?|invalid|fail\w*|reject\w*|edge|empty|missing|not found|[45]\d\d|"
    r"unauthori[sz]ed|forbidden|denied|boundary|limit|none|zero|null|no|without|exactly|"
    r"one past|just past|over|exceed\w*|too long|negative|duplicate\w*|conflict\w*|cannot)\b",
    re.I,
)
# A story id, or an AC id with an optional range end: S-2, AC1, AC1-AC3, AC1–3, AC1 to AC3
_AC_TOKEN = re.compile(
    r"\bS-(?P<s>\d+)\b|\bAC(?P<ac>\d+)\b(?:\s*(?:[-–]|\bto\b)\s*(?:AC)?(?P<hi>\d+)\b)?"
)
_IDS = re.compile(r"\b(?:S|REQ|AC|A|Q|U|C|T|TP|D|CO|F)-?\d+\b")
_NUMBER = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)(?:st|nd|rd|th)?(?![\w.])")
_LIST = re.compile(
    r"((?:[A-Za-z][\w-]*(?: [A-Za-z][\w-]*){0,2}, )+[A-Za-z][\w-]*(?: [A-Za-z][\w-]*){0,2},? "
    r"(?:and|or) [A-Za-z][\w-]*(?: [A-Za-z][\w-]*){0,2})"
)
# "doctor and patient", "date and time": one word each side, not inside a longer list
_PAIR = re.compile(r"(?<!, )\b([A-Za-z][\w-]{2,}) and ([A-Za-z][\w-]{2,})\b(?!,)")
_STOP = frozenset(
    re.findall(
        r"\w+",
        "a an the of to in on at by for with and or is are be it its this that these those as "
        "from into per each any all both not no than then when what which who whom whose same new",
    )
)


@dataclass
class TestCode:
    """The unit-test step's test files: full text by path, and the lines it added."""

    files: dict[str, str] = field(default_factory=dict)
    added: str = ""


@dataclass
class Facts:
    """What the content checks read, gathered by `gather`."""

    schema: str
    front: dict[str, Any]
    body: str
    intent: dict[str, Any] | None = None
    stories: dict[str, Any] | None = None
    change: dict[str, Any] | None = None
    answers: list[dict[str, Any]] = field(default_factory=list)
    status_sets: list[list[str]] = field(default_factory=list)
    tests: TestCode | None = None


# ------------------------------------------------------------------------------ helpers
def _list(x: Any) -> list[Any]:
    return x if isinstance(x, list) else []


def _dicts(x: Any) -> list[dict[str, Any]]:
    return [i for i in _list(x) if isinstance(i, dict)]


def _short(s: str, n: int = 120) -> str:
    s = re.sub(r"\s+", " ", str(s)).strip()
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def _section(body: str, title: str) -> str:
    hs = headings(body)
    h = next((x for x in hs if norm_title(x.title) == title), None)
    return section_text(body, h, hs) if h else ""


def status_sets(texts: list[str]) -> list[list[str]]:
    """Status value lists named in the context or the inputs ("Status is A, B, C or D")."""
    out: list[list[str]] = []
    seen: set[tuple[str, ...]] = set()
    for text in texts:
        flat = re.sub(r"\s+", " ", text)
        for m in STATUS_LIST.finditer(flat):
            vals = [v for v in re.split(_SEP, m.group(1)) if v]
            vals = list(dict.fromkeys(vals))
            key = tuple(sorted(_norm(v) for v in vals))
            if len(vals) >= 3 and key not in seen:
                seen.add(key)
                out.append(vals)
    keys = [{_norm(v) for v in vals} for vals in out]
    return [v for v, k in zip(out, keys, strict=True) if not any(k < o for o in keys)]


def _norm(v: str) -> str:
    return re.sub(r"[^a-z0-9]", "", v.lower())


def status_pattern(value: str, *, code: bool = False) -> re.Pattern[str]:
    """NO_SHOW matches No-show, NO_SHOW, No show and noShow. In prose the first letter must be
    upper case, so the plain word "scheduled" in a sentence does not count as the status; in
    code any case counts ('no_show', NoShow)."""
    parts = re.findall(r"[A-Za-z0-9]+", value)
    if not parts:
        return re.compile(r"(?!x)x")
    first = parts[0]
    if code:
        head = f"(?i:{re.escape(first)})"
    else:
        head = re.escape(first[0].upper()) + (f"(?i:{re.escape(first[1:])})" if first[1:] else "")
    rest = "".join(rf"[\s_-]?(?i:{re.escape(p)})" for p in parts[1:])
    return re.compile(rf"(?<![A-Za-z0-9]){head}{rest}(?![A-Za-z0-9])")


def statuses_in(text: str, values: list[str]) -> list[str]:
    return [v for v in values if status_pattern(v).search(text)]


def ac_refs(text: str) -> set[tuple[str, str]]:
    """{("S-2", "AC1"), ...} named in text. An AC belongs to the story named last before it in
    the same bullet (a wrapped line continues it): "S-2 AC1/AC3", "S-2 AC1-AC3", "S-3 AC1 to
    AC3" and "S-1: column shown (AC1), cut at 60 (AC2)" all count."""
    out: set[tuple[str, str]] = set()
    story: str | None = None
    for line in text.splitlines():
        if not line.strip() or re.match(r"\s*(?:[-*+]|\d+[.)])\s", line):
            story = None  # a new bullet or paragraph starts
        for m in _AC_TOKEN.finditer(line):
            if m.group("s"):
                story = f"S-{int(m.group('s'))}"
                continue
            if story is None:
                continue
            lo = int(m.group("ac"))
            hi = int(m.group("hi")) if m.group("hi") else lo
            if not 0 <= hi - lo <= 20:
                hi = lo
            out.update((story, f"AC{i}") for i in range(lo, hi + 1))
    return out


def _stem(word: str) -> str:
    """Plural to singular, enough to match a listed term with the same word in an AC:
    specializations, cases, statuses, searches, categories."""
    w = word.lower()
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if w.endswith(("sses", "ches", "shes", "xes", "zes", "uses")):
        return w[:-2]
    if len(w) > 3 and w.endswith("s") and not w.endswith(("ss", "us", "is")):
        return w[:-1]
    return w


def _words(text: str) -> set[str]:
    return {_stem(w) for w in re.findall(r"[A-Za-z][A-Za-z-]+", text)}


def listed_terms(statement: str) -> list[str]:
    """Items of an "A, B, C and D" list in a statement (three or more items), or of a short
    "A and B" pair ("doctor and patient filters"). A two-item "or" is usually prose."""
    out: list[str] = []
    found = [m.group(1) for m in _LIST.finditer(statement)]
    found += [f"{m.group(1)} and {m.group(2)}" for m in _PAIR.finditer(statement)]
    for lst in found:
        items = [i.strip() for i in re.split(r",\s*(?:and\s+|or\s+)?|\s+(?:and|or)\s+", lst)]
        items = [i for i in items if i and any(w.lower() not in _STOP for w in i.split())]
        out += items
    return list(dict.fromkeys(out))


def _covered(term: str, words: set[str]) -> bool:
    content = [w for w in re.findall(r"[A-Za-z][A-Za-z-]+", term) if w.lower() not in _STOP]
    return any(_stem(w) in words for w in content)


def values_of(text: str) -> list[str]:
    """Concrete values an AC fixes: clock times and numbers of two or more digits (ids such as
    S-2, AC1 and REQ-4 left out). Test data that builds the case holds at least one of them."""
    t = _IDS.sub(" ", text)
    out = CLOCK.findall(t)
    t = CLOCK.sub(" ", t)
    out += [n for n in _NUMBER.findall(t) if len(n.split(".")[0]) >= 2 or "." in n]
    return list(dict.fromkeys(out))


def _in_code(value: str, code: str) -> bool:
    if ":" in value:
        h, m = value.split(":")
        return re.search(rf"(?<!\d)0?{int(h)}:{m}(?!\d)", code) is not None
    return re.search(rf"(?<![\d.]){re.escape(value)}(?![\d])", code) is not None


def _answer_options(a: dict[str, Any]) -> tuple[str, list[str]]:
    ans = str(a.get("answer") or "").strip()
    opts = [o.strip() for o in str(a.get("options") or "").split("|") if o.strip()]
    return ans, [o for o in opts if o != ans]


def _answer_item(a: dict[str, Any], what: str) -> dict[str, str]:
    ans, others = _answer_options(a)
    q = _short(str(a.get("question") or ""), 160)
    step = f" ({a.get('step')})" if a.get("step") else ""
    head = f'{a["id"]}{step}: "{q}" was answered "{_short(ans, 80)}"'
    if others:
        alt = "; ".join(f'"{_short(o, 60)}"' for o in others[:3])
        detail = f"{head}, not {alt}. Name the {what} whose result differs if a not-chosen option "
        detail += "were built; if there is none, add one."
    else:
        detail = f"{head}. Name the {what} that follows from this answer; if there is none, "
        detail += "add one."
    return {"kind": "check", "id": str(a["id"]), "detail": detail}


def _stories(front: dict[str, Any] | None) -> list[dict[str, Any]]:
    return [s for s in _dicts((front or {}).get("stories")) if isinstance(s.get("id"), str)]


def _acs(story: dict[str, Any]) -> list[dict[str, Any]]:
    return [a for a in _dicts(story.get("acceptance_criteria")) if isinstance(a.get("id"), str)]


def _ac_text(story: dict[str, Any]) -> str:
    return "\n".join(str(a.get("text") or "") for a in _acs(story))


def _cap(items: list[dict[str, str]]) -> list[dict[str, str]]:
    if len(items) <= MAX_CHECK:
        return items
    more = len(items) - (MAX_CHECK - 1)
    last = {
        "kind": "check",
        "id": "more",
        "detail": f"{more} more check item(s) not shown; apply the same questions to the "
        "remaining REQs and stories",
    }
    return [*items[: MAX_CHECK - 1], last]


# --------------------------------------------------------------------------- story-split
def story_split(f: Facts) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """(fix, check) for a stories.v1 artifact. All items are checks: the gates already prove
    coverage and AC form; these name the discriminating cases the reviewer looks for."""
    stories = _stories(f.front)
    reqs = {
        str(r.get("id")): r
        for r in _dicts((f.intent or {}).get("requirements"))
        if r.get("status") in ("known", "assumed")
    }
    check: list[dict[str, str]] = []
    for values in f.status_sets:
        for s in stories:
            named = statuses_in(_ac_text(s), values)
            missing = [v for v in values if v not in named]
            stmts = " ".join(
                str(reqs[r].get("statement") or "") for r in _list(s.get("trace")) if r in reqs
            )
            partitions = PARTITION.search(stmts) or statuses_in(stmts, values)
            if named and missing and (partitions or not reqs):
                check.append(
                    {
                        "kind": "check",
                        "id": s["id"],
                        "detail": f"{s['id']} names status {', '.join(named)} in its ACs; "
                        f"{', '.join(missing)} {'has' if len(missing) == 1 else 'have'} none. "
                        "Each status is its own partition: "
                        "add an AC for each that the story's REQs touch, or write "
                        '"covered by S-n ACm" in the story\'s body block.',
                    }
                )
    check += [_answer_item(a, "AC") for a in f.answers if a.get("id")]
    for rid, r in reqs.items():
        tracing = [s for s in stories if rid in _list(s.get("trace"))]
        if not tracing:
            continue  # H5 reports an untraced REQ
        statement = str(r.get("statement") or "")
        acs = "\n".join(_ac_text(s) for s in tracing)
        words = _words(acs)
        ids = ", ".join(s["id"] for s in tracing)
        asks: list[str] = []
        absent = [t for t in listed_terms(statement) if not _covered(t, words)]
        if absent:
            asks.append(
                "it names " + ", ".join(f"`{t}`" for t in absent) + f", which no AC of {ids} "
                "mentions: add an AC for each"
            )
        for name, rx, ask in CHECKS:
            m = rx.search(statement)
            if m:
                asks.append(f'{name} ("{m.group(0)}"): {ask}')
        lm = LOCAL_DATE.search(statement)
        if lm and not CLOCK.search(acs):
            asks.append(
                f'local date ("{lm.group(0)}"): an AC whose instant has a different local '
                "and UTC date, with clock times (no AC of these stories has one)"
            )
        if asks:
            check.append(
                {
                    "kind": "check",
                    "id": rid,
                    "detail": f'{rid} ("{_short(statement)}", traced by {ids}). Find the AC '
                    "for each, or add it: " + "; ".join(asks) + ".",
                }
            )
    return [], _cap(check)


# ----------------------------------------------------------------------------- unit-test
def unit_test(f: Facts) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """(fix, check) for a ut-result.v1 artifact."""
    fix: list[dict[str, str]] = []
    check: list[dict[str, str]] = []
    stories = _stories(f.stories)
    tests_sec = _section(f.body, "tests")
    unknown_sec = _section(f.body, "unknown")
    named = ac_refs(tests_sec)
    excused = ac_refs(unknown_sec)
    trace = {str(x) for x in _list(f.front.get("trace"))}
    code = f.tests.added if f.tests else ""
    code = re.sub(r"(?<=\d)_(?=\d)", "", code)  # 50_000 is 50000
    full = "\n".join((f.tests.files if f.tests else {}).values())

    # fix: every AC of the stories is named on a Tests line, or excused under Unknown
    for s in stories:
        miss = [a["id"] for a in _acs(s) if (s["id"], a["id"]) not in named | excused]
        if miss:
            refs = ", ".join(f"{s['id']} {x}" for x in miss)
            fix.append(
                {
                    "kind": "content",
                    "id": s["id"],
                    "detail": f"{refs}: no Tests line names it and Unknown does not list it. "
                    f"Add a test for each and name the AC on its Tests line, as `{s['id']} "
                    f"{miss[0]}` (S-n alone does not count). An existing test that really checks "
                    "it counts: name that test and the AC on a Tests line. Otherwise list it "
                    "under Unknown with the reason it cannot be unit-tested.",
                }
            )
    # fix: every REQ the stories trace is in this trace or under Unknown
    traced = {str(r): s["id"] for s in stories for r in _list(s.get("trace"))}
    for rid, sid in sorted(traced.items(), key=lambda x: _num(x[0])):
        if rid not in trace and not re.search(rf"\b{re.escape(rid)}\b", unknown_sec):
            fix.append(
                {
                    "kind": "content",
                    "id": rid,
                    "detail": f"{rid} is traced by {sid} but is not in this artifact's trace "
                    "and not under Unknown. Add a test for it and add it to trace, or list it "
                    "under Unknown with the reason.",
                }
            )

    if f.tests is not None:
        for values in f.status_sets:
            for s in stories:
                want = statuses_in(_ac_text(s), values)
                gone = [v for v in want if not status_pattern(v, code=True).search(code)]
                if gone:
                    check.append(
                        {
                            "kind": "check",
                            "id": s["id"],
                            "detail": f"{s['id']}'s ACs name status {', '.join(want)}; no line "
                            f"the tests added names {', '.join(gone)}. Each status is its own "
                            "partition: confirm a test sets up each one, or add it.",
                        }
                    )
        for s in stories:
            for a in _acs(s):
                if (s["id"], a["id"]) not in named:
                    continue
                vals = values_of(str(a.get("text") or ""))
                if vals and not any(_in_code(v, code) for v in vals):
                    check.append(
                        {
                            "kind": "check",
                            "id": f"{s['id']} {a['id']}",
                            "detail": f"{s['id']} {a['id']} is named as covered and fixes "
                            f"{', '.join(vals[:5])}; no line the tests added holds any of "
                            "them. Confirm the test data builds that case (for example the "
                            "21st row for page 2, a 300-character text), or fix the test.",
                        }
                    )
            order = [a["id"] for a in _acs(s) if ORDER_AC.search(str(a.get("text") or ""))]
            if order:
                check.append(
                    {
                        "kind": "check",
                        "id": s["id"],
                        "detail": f"{s['id']} {', '.join(order)} pick one item by order: confirm "
                        "each test has at least two candidates in an order where the wrong pick "
                        "(first loaded, earliest, any status) fails.",
                    }
                )
        if re.search(r"\bREQ-\d+\b", full):  # the strategy names tests after requirements
            for rid in sorted(trace, key=_num):
                if rid.startswith("REQ-") and not re.search(rf"\b{re.escape(rid)}\b", full):
                    check.append(
                        {
                            "kind": "check",
                            "id": rid,
                            "detail": f"{rid} is in trace but no test file this step changed "
                            "names it, while other tests are named after their REQ. Name the "
                            "test that covers it, or add one.",
                        }
                    )
        for path in _prod_files(f.change):
            stem = Path(path).name.split(".")[0]
            if stem.lower() in GENERIC_STEMS or len(stem) < 4:
                continue
            if not re.search(rf"\b{re.escape(stem)}\b", full):
                check.append(
                    {
                        "kind": "check",
                        "id": path,
                        "detail": f"{path} changed in this run, but no test file this step "
                        f"changed mentions `{stem}`. Confirm a test exercises it (extend the "
                        "existing test of that file if there is one), or say why not under "
                        "Unknown.",
                    }
                )
    if tests_sec.strip() and not ERROR_PATH.search(tests_sec):
        check.append(
            {
                "kind": "check",
                "id": "Tests",
                "detail": "No Tests line names an error or edge path (invalid input, not "
                "found, empty, limit). Every changed function or endpoint needs one.",
            }
        )
    check += [_answer_item(a, "test") for a in f.answers if a.get("id")]
    return fix, _cap(check)


def _num(rid: str) -> int:
    m = re.search(r"\d+", rid)
    return int(m.group(0)) if m else 0


def _prod_files(change: dict[str, Any] | None) -> list[str]:
    out: list[str] = []
    for c in _dicts((change or {}).get("code")):
        for p in _list(c.get("files")):
            p = str(p)
            if p.endswith(SOURCE_EXT) and not p.endswith(".d.ts") and not TEST_FILE.search(p):
                out.append(p)
    return list(dict.fromkeys(out))


CHECKERS = {"stories.v1": story_split, "ut-result.v1": unit_test}


def items(f: Facts) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    fn = CHECKERS.get(f.schema)
    return fn(f) if fn else ([], [])


# ------------------------------------------------------------------------------- gather
def gather(rt: Any, comp: Any, rel: str) -> Facts | None:
    """Facts for the artifact at rel, or None when its schema has no content checks."""
    from tsl.approvals import ide_answers
    from tsl.core.frontmatter import split
    from tsl.core.paths import ARTIFACT_RE, ide_answers_path
    from tsl.orchestrator.run import RunCtx

    m = ARTIFACT_RE.match(rel)
    if not m:
        return None
    doc = split(comp.path(rel).read_text(encoding="utf-8"))
    schema = str(doc.front.get("schema") or "")
    if schema not in CHECKERS:
        return None
    ctx = RunCtx(rt, comp, m.group("run_id"))
    step = m.group("step")
    f = Facts(schema, dict(doc.front), doc.body)
    texts: list[str] = []
    ctx_dir = comp.path("context")
    if ctx_dir.is_dir():
        for p in sorted(ctx_dir.glob("*.md")):
            texts.append(p.read_text(encoding="utf-8", errors="replace"))
    for i in ctx.resolve_inputs(step):
        p = comp.path(str(i["path"]))
        if not p.is_file() or not str(i["path"]).endswith(".md"):
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        texts.append(text)
        try:
            front = split(text).front
        except Exception:  # noqa: S112 - a broken input is H6's to report
            continue
        kind = {"intent.v1": "intent", "stories.v1": "stories", "change.v1": "change"}
        attr = kind.get(str(i.get("schema") or front.get("schema")))
        if attr:
            setattr(f, attr, dict(front))
    f.status_sets = status_sets(texts)
    # Every answer of this run so far, this attempt's own included (prior_answers leaves those
    # out because the post-tool hook hands them to the step directly).
    f.answers = ide_answers.read(comp.path(ide_answers_path(ctx.run_id)))
    if schema == "ut-result.v1":
        f.tests = test_code(ctx)
    return f


def test_code(ctx: Any) -> TestCode:
    """Test files this step changed in each product repo (since the last code step's checkpoint),
    with their full text and the lines added."""
    from tsl.gitops.git import Git, GitError, worktree_tree

    tc = TestCode()
    added: list[str] = []
    for repo, b in sorted((ctx.state.get("branch") or {}).items()):
        clone = ctx.comp.product_clone(repo)
        if clone is None:
            continue
        since = b.get("head_sha") or b.get("base_sha")
        try:
            # Explicit prefixes: a user's diff.noprefix setting must not hide the file names.
            raw = Git(clone).raw(
                "diff",
                "--no-color",
                "--no-ext-diff",
                "--src-prefix=a/",
                "--dst-prefix=b/",
                str(since),
                worktree_tree(clone),
            )
        except GitError:
            continue
        diff = (raw or b"").decode("utf-8", "replace")
        cur = ""
        for line in diff.splitlines():
            if line.startswith("+++ "):
                cur = line[4:].removeprefix("b/").strip()
                if TEST_FILE.search(cur) and (clone / cur).is_file():
                    tc.files[cur] = (clone / cur).read_text(encoding="utf-8", errors="replace")
            elif line.startswith("+") and cur in tc.files:
                added.append(line[1:])
    tc.added = "\n".join(added)
    return tc
