"""Hard gates H1-H7 and generic soft checks (SDD-03 §4, §5.1). Plain code, deterministic."""

from __future__ import annotations

import contextlib
import fnmatch
import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tsl.core.errors import TslError
from tsl.core.frontmatter import headings, norm_title, section_text
from tsl.core.hashing import sha256_bytes, sha256_file
from tsl.harness import citations, detectors, injection
from tsl.harness.artifact import Artifact
from tsl.harness.skillchecks import CheckEnv, CheckOutcome, run_declared
from tsl.orchestrator.skills import Skill

ABORT_CODES = {"E-SEC-01", "E-SEC-02", "E-POL-01", "E-POL-02", "E-POL-03", "E-POL-04", "E-POL-05"}
GATE_ORDER = ("H7", "H6", "H1", "H2", "H5", "H4", "H3")
SKILL_CODE = {"H1": "E-H1-04", "H2": "E-H2-02", "H4": "E-H4-04", "H5": "E-H5-02"}
AC_VALUE = re.compile(
    r"\b\d+(?:\.\d+)?\s?(?:ms|milliseconds?|s|sec|seconds?|minutes?|mins?|hours?|"
    r"days?|weeks?|%|percent|mb|gb|kb|items?|per page|requests?)\b",
    re.I,
)


@dataclass
class GateResult:
    id: str
    status: str = "pass"
    codes: list[str] = field(default_factory=list)
    details: list[str] = field(default_factory=list)
    check_ids: list[str] = field(default_factory=list)

    def fail(self, code: str, detail: str, check_id: str | None = None) -> None:
        self.status = "fail"
        if code not in self.codes:
            self.codes.append(code)
        self.details.append(detail)
        if check_id and check_id not in self.check_ids:
            self.check_ids.append(check_id)

    def record(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "id": self.id,
            "pass": self.status in ("pass", "skip"),
            "status": self.status,
            "codes": self.codes,
            "detail": "; ".join(self.details)[:1000],
        }
        if self.check_ids:
            d["check_ids"] = self.check_ids
        return d


@dataclass
class CheckInput:
    root: Path
    art: Artifact
    skill: Skill | None
    repos: set[str]
    clones: dict[str, Path]
    state: dict[str, Any] | None = None
    attempt: dict[str, Any] | None = None
    expected_inputs: list[dict[str, Any]] = field(default_factory=list)
    tool_log: Path | None = None
    tool_log_prior: list[str] = field(default_factory=list)
    policy: dict[str, Any] | None = None
    product_scopes: dict[str, str] = field(default_factory=dict)
    read_only: set[str] = field(default_factory=set)
    product_changes: list[dict[str, Any]] | None = None
    h4_allow: frozenset[str] = frozenset()
    key_lookup: Any = None  # callable key_id -> facts dict | None
    link_hosts: tuple[str, ...] = ()
    standalone: bool = False
    # SC-INJ-01 marker list (SEC-01 §6.5); None means no marker file, so the check is skipped
    injection_markers: injection.Markers | None = None


@dataclass
class CheckRun:
    gates: dict[str, GateResult]
    soft: list[dict[str, Any]]
    inputs: list[dict[str, Any]]
    tool_log_sha256: str
    skill_checks: list[CheckOutcome]
    injection_hits: list[injection.InjectionHit] = field(default_factory=list)


def iter_cites(front: dict[str, Any]) -> list[tuple[str, Any]]:
    """(where, cite) for every citation in the structured front matter."""
    out: list[tuple[str, Any]] = []
    for i, c in enumerate(front.get("claims", []) or []):
        for j, x in enumerate(c.get("cites", []) or []):
            out.append((f"claims/{i}/cites/{j}", x))
    for i, q in enumerate(front.get("questions", []) or []):
        for j, x in enumerate(q.get("evidence", []) or []):
            out.append((f"questions/{i}/evidence/{j}", x))
    for i, r in enumerate(front.get("requirements", []) or []):
        for j, x in enumerate(r.get("cites", []) or []):
            out.append((f"requirements/{i}/cites/{j}", x))
    return out


def ref_of(c: Any) -> str:
    return str(c["ref"]) if isinstance(c, dict) else str(c)


# ------------------------------------------------------------------------------------ H1
def h1(ci: CheckInput) -> GateResult:
    from tsl.schemas.registry import errors, index, readable

    g = GateResult("H1")
    art = ci.art
    if art.doc is None:
        g.fail("E-H1-01", f"front matter missing or not valid YAML in {art.rel}", "GEN-STRUCT-01")
        return g
    sid = art.schema
    try:
        target = readable(sid, art.rel)
    except TslError:
        g.fail("E-SCH-01", f"schema {sid} not readable by this tsl", "GEN-SCHEMA-01")
        return g
    if not target or target not in index():
        g.fail("E-H1-02", f"unknown schema {sid or '(none)'}", "GEN-SCHEMA-01")
        return g
    for e in errors("envelope.v1", art.front):
        g.fail("E-H1-04", f"envelope {e.pointer or '/'}: {e.message}", "GEN-SCHEMA-01")
    for e in errors(target, art.front):
        g.fail("E-H1-04", f"body {e.pointer or '/'}: {e.message}", "GEN-SCHEMA-01")
    from tsl.schemas.registry import body_hints

    if body_hints(target).get("x-claims-required") and not art.front.get("claims"):
        g.fail("E-H1-04", "claims required by the body schema", "GEN-SCHEMA-01")
    if ci.skill is not None:
        want = ci.skill.artifact_output.get("schema")
        if want and sid != want:
            g.fail(
                "E-H1-03", f"envelope schema {sid} does not match run state {want}", "GEN-SCHEMA-01"
            )
    if ci.state is not None and ci.attempt is not None:
        expect = {
            "run_id": ci.state["run_id"],
            "step": art.step,
            "attempt": ci.attempt["n"],
            "skill": ci.attempt["skill"],
        }
        for k, v in expect.items():
            if art.front.get(k) != v:
                g.fail(
                    "E-H1-03", f"envelope {k} {art.front.get(k)} != state {k} {v}", "GEN-SCHEMA-01"
                )
        given = {i["path"] for i in ci.expected_inputs if i.get("sha256")}
        env_in = {i.get("path") for i in art.front.get("inputs", []) or [] if isinstance(i, dict)}
        if env_in != given:
            g.fail(
                "E-H1-03", "envelope inputs differ from the inputs tsl next gave", "GEN-SCHEMA-01"
            )
    for where, c in iter_cites(art.front):
        if citations.parse(ref_of(c), ci.repos) is None:
            g.fail(
                "E-H1-05",
                f"citation {ref_of(c)[:120]} at /{where} does not match the format",
                "GEN-CITE-01",
            )
    return g


# ------------------------------------------------------------------------------------ H2
def _unknown_items(front: dict[str, Any]) -> list[tuple[str, bool | None]]:
    qs = {q.get("id"): q for q in front.get("questions", []) or []}
    links = {u.get("id"): u.get("question") for u in front.get("unknowns", []) or []}
    out: list[tuple[str, bool | None]] = []
    for u in front.get("unknown", []) or []:
        if isinstance(u, dict):
            out.append((str(u.get("id")), bool(u.get("blocking"))))
        else:
            q = qs.get(links.get(u))
            out.append((str(u), None if q is None else bool(q.get("blocking"))))
    return out


def h2(ci: CheckInput, skill_checks: list[CheckOutcome]) -> GateResult:
    from tsl.schemas.registry import body_hints, index

    g = GateResult("H2")
    art = ci.art
    if art.doc is None:
        g.status = "skip"
        return g
    body = art.doc.body
    hs = headings(body)
    sid = art.schema
    req = body_hints(sid).get("x-required-sections", []) if sid in index() else []
    for r in req:
        match = [
            h for h in hs if norm_title(h.title) == norm_title(r["title"]) and h.level == r["level"]
        ]
        if not match:
            g.fail(
                "E-H2-01",
                f"section '{r['title']}' (level {r['level']}) missing in {Path(art.rel).name}",
                "GEN-SECT-01",
            )
            continue
        text = section_text(body, match[0], hs)
        if len(re.sub(r"\s", "", text)) < int(r.get("min_chars", 1)):
            g.fail("E-H2-02", f"section '{r['title']}' is empty", "GEN-SECT-01")
    f = art.front
    lists_ok = all(isinstance(f.get(k), list) for k in ("known", "assumed", "unknown"))
    if not lists_ok or not f.get("known"):
        g.fail(
            "E-H2-03",
            "known, assumed and unknown lists required; known must not be empty",
            "GEN-SECT-01",
        )
    elif any(b is None for _, b in _unknown_items(f)):
        g.fail("E-H2-03", "every unknown item must be marked blocking or not", "GEN-SECT-01")
    _skill_into(g, "H2", skill_checks)
    return g


def _skill_into(g: GateResult, gate: str, outcomes: list[CheckOutcome]) -> None:
    for o in outcomes:
        if o.gate == gate and o.status == "fail":
            g.fail(SKILL_CODE.get(gate, "E-CHK-01"), f"{o.id}: {o.detail}", o.id)


# ------------------------------------------------------------------------------------ H4
def h4(ci: CheckInput) -> tuple[GateResult, list[detectors.Hit]]:
    g = GateResult("H4")
    hits = detectors.scan(ci.art.text, ci.h4_allow)
    for h in hits:
        if h.kind == "secret":
            g.fail("E-SEC-01", f"rule {h.rule_id} line {h.line}", "GEN-SECRET-01")
        elif h.kind == "pii":
            g.fail("E-SEC-02", f"rule {h.rule_id} line {h.line}", "GEN-PII-01")
    if ci.art.doc is not None:
        from tsl.schemas.registry import body_hints, index

        sid = ci.art.schema
        fields = body_hints(sid).get("x-acceptance-criteria", []) if sid in index() else []
        if fields:
            _invented_values(ci, g, fields)
    return g, hits


def _invented_values(ci: CheckInput, g: GateResult, fields: list[str]) -> None:
    from tsl.harness.jsonpath import select

    corpus = ""
    for i in ci.expected_inputs:
        p = ci.root / str(i.get("path", ""))
        if i.get("path") and p.is_file():
            corpus += p.read_text(encoding="utf-8", errors="replace").lower() + "\n"
    assumed = set(ci.art.front.get("assumed", []) or [])
    norm = re.sub(r"\s+", "", corpus)
    for fpath in fields:
        parent = fpath.rsplit(".", 1)[0]
        leaf = fpath.rsplit(".", 1)[1]
        for item in select(ci.art.front, parent):
            if not isinstance(item, dict):
                continue
            text = str(item.get(leaf, ""))
            linked = {str(x) for x in (item.get("assumptions") or [])} & assumed
            for v in AC_VALUE.findall(text):
                if re.sub(r"\s+", "", v.lower()) not in norm and not linked:
                    g.fail(
                        "E-H4-04",
                        f"value '{v}' in {item.get('id', fpath)} not found in inputs "
                        "and not linked to an assumption",
                        "GEN-AC-01",
                    )


# ------------------------------------------------------------------------------------ H5
def _foundation(ci: CheckInput) -> set[str]:
    ids: set[str] = {str(r["id"]) for r in ci.art.front.get("requirements", []) or []}
    base = ci.root / "context" / "intent-baseline.md"
    if base.is_file():
        ids |= set(re.findall(r"\b[A-Z]+-[0-9]+\b", base.read_text(encoding="utf-8")))
    for i in ci.expected_inputs:
        p = ci.root / str(i.get("path", ""))
        if i.get("schema") == "intent.v1" and p.is_file():
            from tsl.core.frontmatter import FrontMatterError, split

            with contextlib.suppress(FrontMatterError, KeyError, TypeError):
                ids |= {
                    str(r["id"])
                    for r in split(p.read_text(encoding="utf-8")).front.get("requirements", [])
                }
    return ids


def h5(ci: CheckInput, skill_checks: list[CheckOutcome]) -> GateResult:
    from tsl.harness.jsonpath import select
    from tsl.schemas.registry import body_hints, index

    g = GateResult("H5")
    if ci.art.doc is None:
        g.status = "skip"
        return g
    front = ci.art.front
    trace = list(front.get("trace", []) or [])
    if ci.skill is not None and ci.skill.trace_required and not trace:
        g.fail("E-H5-01", "trace is empty", "GEN-TRACE-01")
    found = _foundation(ci)
    sid = ci.art.schema
    xtrace = body_hints(sid).get("x-trace", []) if sid in index() else []
    traced: list[str] = list(trace)
    for fp in xtrace:
        for v in select(front, fp):
            traced.extend(v if isinstance(v, list) else [v])
    for t in dict.fromkeys(traced):
        if str(t) not in found:
            g.fail("E-H5-02", f"trace id {t} not found", "GEN-TRACE-01")
    if ci.skill is not None and ci.skill.harness.get("trace_coverage") == "full":
        req_ids = {i for i in found if i.startswith("REQ-")}
        for r in sorted(req_ids - {str(x) for x in traced}):
            g.fail("E-H5-01", f"{r} is not traced by any item", "GEN-TRACE-01")
    for ch in ci.product_changes or []:
        scope = ci.product_scopes.get(str(ch["repo"]))
        for f in ch.get("files", []):
            if scope is None or not (scope in (".", "") or f.startswith(scope.rstrip("/") + "/")):
                g.fail("E-POL-01", f"{ch['repo']}:{f} outside allowed scope", "GEN-SCOPE-01")
            elif ci.policy and any(
                fnmatch.fnmatch(f, d.split("/", 1)[-1]) or fnmatch.fnmatch(f, d)
                for d in ci.policy.get("deny", [])
                if d.startswith("**")
            ):
                g.fail("E-POL-01", f"{ch['repo']}:{f} matches a write deny rule", "GEN-SCOPE-01")
    if ci.policy and ci.tool_log and ci.tool_log.is_file() and ci.attempt is not None:
        for e in _log_entries(ci.tool_log):
            if e.get("step") != ci.art.step or e.get("attempt") != ci.attempt["n"]:
                continue
            is_write = e.get("tool") in ("Write", "Edit", "NotebookEdit")
            if (
                is_write
                and e.get("decision") == "allow"
                and not path_allowed(str(e.get("target", "")), ci.policy)
            ):
                g.fail(
                    "E-POL-01",
                    f"logged write outside scope: {str(e.get('target'))[:80]}",
                    "GEN-SCOPE-01",
                )
    _skill_into(g, "H5", skill_checks)
    return g


def path_allowed(target: str, policy: dict[str, Any]) -> bool:
    t = target.replace("\\", "/")
    if any(fnmatch.fnmatch(t, d) for d in policy.get("deny", [])):
        return False
    return any(fnmatch.fnmatch(t, a) for a in policy.get("allow", []))


# ------------------------------------------------------------------------------------ H6
def h6(ci: CheckInput) -> tuple[GateResult, list[dict[str, Any]]]:
    g = GateResult("H6")
    inputs: list[dict[str, Any]] = []
    if ci.standalone:
        g.status = "skip"
        return g, inputs
    declared = {
        (i.get("path"), i.get("sha256"))
        for i in ci.art.front.get("inputs", []) or []
        if isinstance(i, dict)
    }
    memo: dict[str, bool] = {}
    for i in ci.expected_inputs:
        rel = str(i.get("path") or "")
        p = ci.root / rel
        if not rel or not p.is_file():
            if i.get("required", True):
                g.fail("E-IN-01", f"required input {i['name']} missing", "GEN-INPUT-01")
            continue
        cur = sha256_file(p)
        rec_sha = next((s for (pp, s) in declared if pp == rel), None)
        if rec_sha is not None and rec_sha != cur:
            g.fail(
                "E-IN-02",
                f"input {rel} changed after use; re-run step '{i.get('step') or '?'}'",
                "GEN-INPUT-01",
            )
            continue
        if i.get("step"):
            vrel = rel[:-3] + ".verification.json" if rel.endswith(".md") else ""
            ok, why, vsha = _record_ok(ci, vrel, cur, memo)
            if not ok:
                g.fail(
                    "E-H6-03",
                    f"upstream record for {i['name']} {why}; re-run step '{i.get('step')}'",
                    "GEN-INPUT-01",
                )
                continue
            inputs.append({"path": rel, "sha256": cur, "verification_sha256": vsha})
    return g, inputs


def _record_ok(
    ci: CheckInput, vrel: str, art_sha: str, memo: dict[str, bool]
) -> tuple[bool, str, str]:
    from tsl.core.clock import parse_iso
    from tsl.identity.verify import accept, facts_from

    p = ci.root / vrel
    if not vrel or not p.is_file():
        return False, "missing", ""
    raw = p.read_bytes()
    vsha = sha256_bytes(raw)
    if vrel in memo:
        return memo[vrel], "stale upstream", vsha
    try:
        rec = json.loads(raw.decode("utf-8"))
    except ValueError:
        memo[vrel] = False
        return False, "unreadable", vsha
    if rec.get("artifact_sha256") != art_sha:
        memo[vrel] = False
        return False, "does not match the artifact", vsha
    facts = ci.key_lookup(str(rec.get("key_id"))) if ci.key_lookup else None
    verdict, _ = accept(
        rec, parse_iso(str(rec.get("decided_at"))), [], facts_from(facts), check_roles=False
    )
    if verdict == "bad":
        memo[vrel] = False
        return False, "unsigned or signature invalid", vsha
    outcome = rec.get("outcome")
    if outcome not in ("PASS", "PASS-WITH-FINDINGS"):
        accepted = False
        if outcome == "ESCALATE" and ci.state is not None:
            st = next((s for s in ci.state["steps"] if s["id"] == rec.get("step")), None)
            accepted = bool(st and st.get("status") == "ACCEPTED")
        if not accepted:
            memo[vrel] = False
            return False, "not passed", vsha
    memo[vrel] = True
    for up in rec.get("inputs", []):
        uprel = str(up["path"])
        if not (ci.root / uprel).is_file() or sha256_file(ci.root / uprel) != up["sha256"]:
            memo[vrel] = False
            return False, "stale upstream", vsha
        uv = uprel[:-3] + ".verification.json"
        ok, _, usha = _record_ok(ci, uv, str(up["sha256"]), memo)
        if not ok or usha != up["verification_sha256"]:
            memo[vrel] = False
            return False, "stale upstream", vsha
    return True, "", vsha


# ------------------------------------------------------------------------------------ H7
def _log_entries(path: Path) -> list[dict[str, Any]]:
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except ValueError:
                out.append({"_bad": True})
    return out


def tool_log_sha(path: Path | None) -> str:
    if path is None or not path.is_file():
        return hashlib.sha256(b"").hexdigest()
    return sha256_bytes(path.read_bytes())


def _prefix_ok(data: bytes, recorded: str) -> bool:
    if hashlib.sha256(b"").hexdigest() == recorded:
        return True
    h = hashlib.sha256()
    for line in data.replace(b"\r\n", b"\n").splitlines(keepends=True):
        h.update(line)
        if h.hexdigest() == recorded:
            return True
    return False


def _tool_allowed(entry: dict[str, Any], allowed: list[str]) -> bool:
    tool = str(entry.get("tool"))
    if tool.startswith("mcp__"):
        return False
    if tool == "Bash":
        cmd = str(entry.get("target", ""))
        pats = [a[5:-1] for a in allowed if a.startswith("Bash(")] + ["tsl *"]
        return any(fnmatch.fnmatch(cmd, p) for p in pats)
    if tool == "NotebookEdit":
        return "Edit" in allowed
    return tool in allowed


def h7(ci: CheckInput) -> GateResult:
    from tsl.schemas.registry import errors

    g = GateResult("H7")
    if ci.standalone or ci.skill is None or ci.attempt is None:
        g.status = "skip"
        return g
    p = ci.tool_log
    if p is None or not p.is_file():
        g.fail("E-POL-05", "tool log missing", "GEN-TOOLS-01")
        return g
    data = p.read_bytes()
    for rec in ci.tool_log_prior:
        if not _prefix_ok(data, rec):
            g.fail("E-POL-05", "tool log altered (earlier lines changed)", "GEN-TOOLS-01")
            return g
    entries = _log_entries(p)
    for e in entries:
        if e.get("_bad") or errors("tool-log.v1", e):
            g.fail("E-POL-05", "tool log line does not parse", "GEN-TOOLS-01")
            return g
    mine = [e for e in entries if e["step"] == ci.art.step and e["attempt"] == ci.attempt["n"]]
    for e in mine:
        if e["decision"] == "deny":
            g.fail(str(e["code"]), f"denied {e['tool']} recorded in the tool log", "GEN-TOOLS-01")
        elif not _tool_allowed(e, ci.skill.allowed_tools):
            g.fail(
                "E-POL-04",
                f"tool {e['tool']} not permitted for skill {ci.skill.id}",
                "GEN-TOOLS-01",
            )
    return g


# ------------------------------------------------------------------------------------ soft
LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")


def soft_checks(ci: CheckInput, hits: list[detectors.Hit]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    art = ci.art
    body = art.doc.body if art.doc else art.text
    links = LINK.findall(body)
    rel_links = [x for x in links if "://" not in x and not x.startswith(("#", "mailto:"))]
    ext = [x for x in links if "://" in x]
    if rel_links:
        base = (ci.root / art.rel).parent
        ok = all(
            (base / x.split("#", 1)[0]).exists() or (ci.root / x.split("#", 1)[0]).exists()
            for x in rel_links
        )
        out.append({"id": "GEN-LINK-01", "pass": ok})
    if ext:
        from urllib.parse import urlparse

        ok = all(
            urlparse(x).scheme == "https" and (urlparse(x).hostname or "") in ci.link_hosts
            for x in ext
        )
        out.append({"id": "GEN-LINK-02", "pass": ok})
    out.append({"id": "GEN-SIZE-01", "pass": len(art.text.encode("utf-8")) <= 200 * 1024})
    if art.doc is not None:
        blocking = [u for u, b in _unknown_items(art.front) if b]
        if blocking:
            hs = headings(body)
            oq = next((h for h in hs if norm_title(h.title) == "open questions"), None)
            text = section_text(body, oq, hs) if oq else ""
            qlinks = {u.get("id"): u.get("question") for u in art.front.get("unknowns", []) or []}
            ok = all(u in text or (qlinks.get(u) or "~") in text for u in blocking)
            out.append({"id": "GEN-UNK-01", "pass": ok})
    if any(h.kind == "pii-soft" for h in hits):
        out.append({"id": "GEN-PII-02", "pass": False})
    return out


def injection_check(ci: CheckInput) -> tuple[dict[str, Any] | None, list[injection.InjectionHit]]:
    """SC-INJ-01 over the artifact and every declared input that exists (SEC-01 §6.2 L1)."""
    if ci.injection_markers is None:
        return None, []
    sources: list[tuple[str, str]] = [(ci.art.rel, ci.art.text)]
    for i in ci.expected_inputs:
        rel = str(i.get("path") or "")
        p = ci.root / rel
        if rel and p.is_file():
            sources.append((rel, p.read_text(encoding="utf-8", errors="replace")))
    entry, hits = injection.check(sources, ci.injection_markers)
    return entry, hits


def run_all(ci: CheckInput, h3_result: GateResult | None) -> CheckRun:
    env = CheckEnv(
        ci.art.front,
        ci.art.doc.body if ci.art.doc else "",
        ci.root,
        [str(i["path"]) for i in ci.expected_inputs if i.get("path")],
        {},
        {
            str(i["name"]): str(i["path"])
            for i in ci.expected_inputs
            if i.get("name") and i.get("path")
        },
    )
    skill_checks = run_declared(env, ci.skill.checks if ci.skill and ci.art.doc else None)
    g: dict[str, GateResult] = {}
    g["H7"] = h7(ci)
    g["H6"], inputs = h6(ci)
    g["H1"] = h1(ci)
    if g["H1"].codes and "E-H1-01" in g["H1"].codes:
        for k in ("H2", "H5"):
            g[k] = GateResult(k, "skip")
        g["H6"] = GateResult("H6", "skip") if not g["H6"].codes else g["H6"]
    else:
        g["H2"] = h2(ci, skill_checks)
        g["H5"] = h5(ci, skill_checks)
    g["H4"], hits = h4(ci)
    if ci.art.doc is not None:
        _skill_into(g["H4"], "H4", skill_checks)
        _skill_into(g["H1"], "H1", skill_checks)
    g["H3"] = h3_result or GateResult("H3", "skip")
    soft = soft_checks(ci, hits)
    inj_entry, inj_hits = injection_check(ci)
    if inj_entry is not None:
        soft.append(inj_entry)
    for o in skill_checks:
        if o.gate == "soft" and o.status != "skip":
            soft.append({"id": o.id, "pass": o.status == "pass"})
    return CheckRun(g, soft, inputs, tool_log_sha(ci.tool_log), skill_checks, inj_hits)
