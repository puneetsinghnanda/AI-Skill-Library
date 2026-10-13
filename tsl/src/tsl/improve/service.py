"""tsl improve case | check | pr (SDD-11 §5, §6). Plain code: no LLM, no Jira.

The improvement id, the chosen flags and the new case ids live in the plan file that
`tsl improve plan` writes to ~/.truminds/cache/improve/<imp_id>/plan.json.
"""

from __future__ import annotations

import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

from tsl.core.clock import parse_iso
from tsl.core.errors import TslError
from tsl.core.hashing import sha256_file
from tsl.core.jsonio import dump_yaml, read_json, read_yaml, write_json
from tsl.core.runtime import Runtime
from tsl.gitops.git import Git, GitError
from tsl.orchestrator.skills import Skill, load_skill

STRUCTURE_MARKERS = [
    (re.compile(r"run_[0-9A-HJKMNP-TV-Z]{26}"), "run id"),
    (re.compile(r"tsl:run_id"), "run marker"),
    (re.compile(r"artifacts/[A-Za-z][A-Za-z0-9_]*-[0-9]+/"), "companion artifact path"),
    (re.compile(r"\bpack_sha\b"), "pack_sha block"),
]
OWNER_INITIATED = "OWNER-INITIATED|-|-|-|-"


# ------------------------------------------------------------------------------- plans
def _skill(rt: Runtime, skill: str) -> Skill:
    d = rt.plugin_root() / "skills" / skill
    if not (d / "skill.yaml").is_file():
        raise TslError("E-USE-01", detail=f"unknown skill {skill}", cmd="improve")
    return load_skill(d)


def find_plan(rt: Runtime, skill: str, imp_id: str | None) -> dict[str, Any] | None:
    base = rt.home.improve_cache
    if imp_id:
        p = base / imp_id / "plan.json"
        if not p.is_file():
            raise TslError("E-USE-01", detail=f"no plan {imp_id}", cmd="improve")
        data = read_json(p)
        return dict(data)
    if not base.is_dir():
        return None
    for d in sorted(base.glob("imp_*"), reverse=True):  # ULIDs sort by time
        p = d / "plan.json"
        if p.is_file():
            data = read_json(p)
            if data.get("skill") == skill:
                return dict(data)
    return None


def save_plan(rt: Runtime, plan: dict[str, Any]) -> None:
    write_json(rt.home.improve_cache / str(plan["improvement_id"]) / "plan.json", plan)


def library_git(sk: Skill) -> Git | None:
    g = Git(sk.dir)
    return g if g.ok("rev-parse", "--is-inside-work-tree") else None


# ------------------------------------------------------------------------------- case
def case(
    rt: Runtime, skill: str, case_id: str, kind: str, title: str | None, imp_id: str | None
) -> dict[str, Any]:
    from tsl.identity import me as memod
    from tsl.schemas.registry import require_valid

    sk = _skill(rt, skill)
    if not re.fullmatch(r"EC-[0-9]{2,3}", case_id):
        raise TslError("E-USE-01", detail="--id must look like EC-11 (eval-case.v1)", cmd="improve")
    cases = sk.dir / "evals" / "cases"
    target = cases / case_id
    if target.exists():
        raise TslError("E-USE-01", detail=f"case {case_id} already exists", cmd="improve case")
    me = memod.cached_me(rt) or {}
    by = str(me.get("pseudonym") or "eng-0000")
    tpl = sk.dir / "evals" / "_template"
    if tpl.is_dir():
        shutil.copytree(tpl, target)
    else:
        (target / "inputs").mkdir(parents=True)
        (target / "inputs" / "ticket.md").write_text(
            "# INVENTED-1\nDescribe the invented ticket on the sample order-tracking system.\n",
            encoding="utf-8",
        )
    meta_path = target / "case.yaml"
    base: dict[str, Any] = read_yaml(meta_path) if meta_path.is_file() else {}
    base.update(
        {
            "schema": "eval-case.v1",
            "id": case_id,
            "title": title or base.get("title") or f"Reproduction case {case_id} (invented data)",
            "kind": kind,
            "inputs": base.get("inputs") or {"ticket": "inputs/ticket.md"},
            "expect": base.get("expect") or {"outcome_in": ["PASS", "PASS-WITH-FINDINGS"]},
            "provenance": "invented",
            "attestation": {
                "by": by,
                "statement": "All data in this case is invented for the sample system.",
            },
        }
    )
    try:
        require_valid("eval-case.v1", base, f"{case_id}/case.yaml")
    except TslError:
        shutil.rmtree(target, ignore_errors=True)
        raise
    meta_path.write_text(dump_yaml(base), encoding="utf-8")
    plan = find_plan(rt, sk.id, imp_id)
    if plan is not None:
        added = list(plan.get("cases_added", []))
        if case_id not in added:
            added.append(case_id)
        plan["cases_added"] = added
        save_plan(rt, plan)
    files = sorted(p.relative_to(sk.dir).as_posix() for p in target.rglob("*") if p.is_file())
    return {
        "skill": sk.id,
        "case_id": case_id,
        "case_dir": str(target),
        "files": files,
        "improvement_id": plan.get("improvement_id") if plan else None,
    }


# ------------------------------------------------------------------------------- check
def _result(path: Path, label: str) -> dict[str, Any]:
    from tsl.schemas.registry import errors

    if not path.is_file():
        raise TslError("E-IMP-04", detail=f"{label} result {path.name} missing")
    data = read_json(path)
    errs = errors("eval-result.v1", data)
    if errs:
        raise TslError("E-IMP-04", detail=f"{label} result invalid at {errs[0].pointer or '/'}")
    return dict(data)


def _signature_ok(rt: Runtime, rec: dict[str, Any]) -> str | None:
    from tsl.identity.keys import public_key
    from tsl.identity.verify import accept, facts_from

    facts = public_key(rt, str(rec.get("key_id")), online=True)
    verdict, why = accept(
        rec, parse_iso(str(rec["recorded_at"])), [], facts_from(facts), check_roles=False
    )
    return why if verdict == "bad" else None


def _my_keys(rt: Runtime) -> set[str]:
    from tsl.insights.client import InsightsUnavailable

    try:
        res = rt.insights.my_keys(rt.token())
    except InsightsUnavailable:
        raise TslError("E-NET-02") from None
    if res.status != 200 or not isinstance(res.body, dict):
        raise TslError("E-NET-02")
    return {str(k.get("key_id")) for k in res.body.get("keys", [])}


def _materialize(g: Git, sk: Skill, ref: str, dst: Path) -> Path | None:
    """Write the skill folder as it was at `ref` into dst; None when it did not exist."""
    top = Path(g.out("rev-parse", "--show-toplevel"))
    rel = sk.dir.resolve().relative_to(top.resolve()).as_posix()
    if g.resolve(ref) is None:
        return None
    names = [n for n in g.out("ls-tree", "-r", "--name-only", ref, "--", rel).splitlines() if n]
    if not names:
        return None
    for n in names:
        data = Git(top).raw("show", f"{ref}:{n}")
        if data is None:
            return None
        out = dst / Path(n).relative_to(rel)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(data)
    return dst


def base_hash(
    rt: Runtime, sk: Skill, plan: dict[str, Any], base: str | None, new: list[str]
) -> str | None:
    """content_hash of the base version of the skill plus the new cases (SDD-11 §6.1 check 2).

    The before run includes the new failing cases, so they are overlaid on the base folder.
    The base is the skill at `--base` (CI), else the copy `tsl improve plan` took.
    """
    from tsl.evals.service import content_hash

    with tempfile.TemporaryDirectory() as tmp:
        dst = Path(tmp) / sk.id
        g = library_git(sk)
        got: Path | None = None
        if base and g is not None:
            got = _materialize(g, sk, base, dst)
        if got is None and plan.get("improvement_id"):
            snap = rt.home.improve_cache / str(plan["improvement_id"]) / "base" / sk.id
            if snap.is_dir():
                shutil.copytree(snap, dst)
                got = dst
        if got is None:
            return None
        for cid in new:
            src = sk.dir / "evals" / "cases" / cid
            if src.is_dir():
                target = dst / "evals" / "cases" / cid
                if target.exists():
                    shutil.rmtree(target)
                shutil.copytree(src, target)
        return content_hash(load_skill(dst))


def _changed_eval_files(sk: Skill, g: Git | None, base: str | None, new: list[str]) -> list[Path]:
    evals = sk.dir / "evals"
    out: set[Path] = set()
    if g is not None and base and g.resolve(base) is not None:
        top = Path(g.out("rev-parse", "--show-toplevel"))
        for n in g.out("diff", "--name-only", base, "--", str(evals)).splitlines():
            out.add(top / n)
        for n in g.out("ls-files", "--others", "--exclude-standard", "--", str(evals)).splitlines():
            out.add(top / n)
    for cid in new:
        d = evals / "cases" / cid
        out.update(p for p in d.rglob("*") if p.is_file())
    return sorted(p for p in out if p.is_file() and "results" not in p.parts)


def scan_eval_files(files: list[Path], root: Path, deny: frozenset[str]) -> list[dict[str, Any]]:
    from tsl.harness import detectors

    hits: list[dict[str, Any]] = []
    for p in files:
        try:
            text = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        rel = p.relative_to(root).as_posix() if p.is_relative_to(root) else p.name
        for h in detectors.scan(text, deny_term_hashes=deny):
            if h.kind in ("secret", "pii", "term"):
                hits.append({"path": rel, "line": h.line, "kind": h.kind})
        for i, line in enumerate(text.splitlines(), 1):
            for rx, what in STRUCTURE_MARKERS:
                if rx.search(line):
                    hits.append({"path": rel, "line": i, "kind": what})
    return hits


def check(
    rt: Runtime,
    skill: str,
    imp_id: str | None = None,
    base: str | None = None,
    new_cases: list[str] | None = None,
    before_path: Path | None = None,
    after_path: Path | None = None,
    deny_hashes: Path | None = None,
) -> tuple[dict[str, Any], list[str]]:
    """Returns (data, codes). Writes improvement.v1 only when every check passes."""
    from tsl.evals.service import _cases, content_hash
    from tsl.schemas.registry import require_valid

    sk = _skill(rt, skill)
    plan = find_plan(rt, sk.id, imp_id)
    if plan is None and imp_id is None and before_path is None:
        raise TslError(
            "E-USE-01", detail="no improvement plan; run tsl improve plan", cmd="improve"
        )
    plan = plan or {}
    from_version = str(plan.get("version") or "")
    results = sk.dir / "evals" / "results"
    before_p = before_path or results / f"{from_version}.eval-result.json"
    after_p = after_path or results / f"{sk.version}.eval-result.json"
    codes: list[str] = []
    notes: dict[str, str] = {}

    def fail(code: str, note: str) -> None:
        if code not in codes:
            codes.append(code)
            notes[code] = note

    before = _result(before_p, "before")
    after = _result(after_p, "after")
    from_version = str(before["version"])
    if before["version"] == after["version"]:
        fail("E-IMP-04", "after version equals before version; bump the skill version")
    if after["version"] != sk.version:
        fail("E-IMP-04", f"after result is for {after['version']}, skill is {sk.version}")
    # 1. signatures, signer = author
    mine = _my_keys(rt)
    for label, rec in (("before", before), ("after", after)):
        why = _signature_ok(rt, rec)
        if why:
            fail("E-IMP-04", f"{label} signature {why}")
        elif str(rec["key_id"]) not in mine:
            fail("E-IMP-04", f"{label} result signed by another person")
    # 2. skill hashes
    new = list(dict.fromkeys([*(plan.get("cases_added") or []), *(new_cases or [])]))
    g = library_git(sk)
    base_ref = base or plan.get("base_sha")
    want_before = base_hash(rt, sk, plan, base, new)
    if not want_before:
        fail("E-IMP-04", "base version of the skill not found")
    elif before["skill_sha256"] != want_before:
        fail("E-IMP-04", "before result does not match the skill at the base commit")
    if after["skill_sha256"] != content_hash(sk):
        fail("E-IMP-04", "after result does not match the current skill folder")
    # 3. new cases fail before and pass after
    es, cases = _cases(sk)
    present = {c["id"] for _, c in cases}
    b = {c["id"]: c for c in before["cases"]}
    a = {c["id"]: c for c in after["cases"]}
    failed_before = [c for c in new if b.get(c, {}).get("result") == "fail"]
    passed_after = [c for c in new if a.get(c, {}).get("result") == "pass"]
    if not new:
        fail("E-IMP-01", "(none added)")
    for c in new:
        if c not in present or c not in failed_before or c not in passed_after:
            fail("E-IMP-01", c)
    # 4 and 6. no regression, nothing removed or edited, enough cases
    regressions = sorted(
        c for c, v in b.items() if v["result"] == "pass" and a.get(c, {}).get("result") != "pass"
    )
    if regressions:
        fail("E-IMP-02", f"regressions {', '.join(regressions)}")
    changed = sorted(
        c
        for c, v in b.items()
        if c not in new and a.get(c, {}).get("case_sha256") != v["case_sha256"]
    )
    if changed:
        fail("E-IMP-02", f"cases removed or edited {', '.join(changed)}")
    if len(after["cases"]) < int(es["min_cases"]):
        fail("E-IMP-02", f"{len(after['cases'])} cases, minimum {es['min_cases']}")
    # 5. pass rate
    min_rate = float(es["min_pass_rate"])
    if float(after["pass_rate"]) < min_rate or float(after["pass_rate"]) < float(
        before["pass_rate"]
    ):
        fail("E-IMP-03", f"{after['pass_rate']} < max({min_rate}, {before['pass_rate']})")
    # 7. forbidden content in changed eval files
    deny: frozenset[str] = frozenset()
    if deny_hashes is not None:
        deny = frozenset(
            x.strip().lower()
            for x in deny_hashes.read_text(encoding="utf-8").splitlines()
            if re.fullmatch(r"\s*[0-9a-fA-F]{64}\s*", x)
        )
    hits = scan_eval_files(
        _changed_eval_files(sk, g, str(base_ref) if base_ref else None, new), sk.dir, deny
    )
    if hits:
        fail("E-IMP-05", f"{hits[0]['path']} line {hits[0]['line']}")
    imp = str(plan.get("improvement_id") or imp_id or rt.ids.new("imp"))
    data: dict[str, Any] = {
        "skill": sk.id,
        "improvement_id": imp,
        "from_version": from_version,
        "to_version": str(after["version"]),
        "before": {
            "result": before_p.name,
            "pass_rate": before["pass_rate"],
            "new_cases_failed": failed_before,
        },
        "after": {
            "result": after_p.name,
            "pass_rate": after["pass_rate"],
            "new_cases_passed": passed_after,
        },
        "cases_added": new,
        "regressions": regressions,
        "forbidden": hits[:20],
        "codes": codes,
        "notes": notes,
        "improvement_path": None,
    }
    if codes:
        return data, codes

    def rel(p: Path) -> str:
        return p.relative_to(sk.dir).as_posix() if p.is_relative_to(sk.dir) else p.name

    rec = {
        "schema": "improvement.v1",
        "id": imp,
        "skill": sk.id,
        "from_version": from_version,
        "to_version": str(after["version"]),
        "flags": list(plan.get("flags") or []),
        "signature": str(plan.get("signature") or OWNER_INITIATED),
        "cases_added": new,
        "before": {
            "result": rel(before_p),
            "sha256": sha256_file(before_p),
            "pass_rate": before["pass_rate"],
            "new_cases_failed": failed_before,
        },
        "after": {
            "result": rel(after_p),
            "sha256": sha256_file(after_p),
            "pass_rate": after["pass_rate"],
            "new_cases_passed": passed_after,
        },
        "regressions": [],
        "checked_by": f"tsl@{rt.tsl_version}",
    }
    require_valid("improvement.v1", rec, "improvement")
    out = sk.dir / "evals" / "improvements" / f"{imp}.json"
    write_json(out, rec)
    data["improvement_path"] = str(out)
    return data, codes


def raise_first(data: dict[str, Any], codes: list[str]) -> TslError:
    code = codes[0]
    note = data["notes"][code]
    fmt: dict[str, Any] = {"detail": note, "case": note}
    if code == "E-IMP-03":
        fmt.update(after=data["after"]["pass_rate"], before=data["before"]["pass_rate"], min="min")
    if code == "E-IMP-05":
        f = data["forbidden"][0]
        fmt.update(path=f["path"], line=f["line"])
    return TslError(code, data=data, **fmt)


# ------------------------------------------------------------------------------- pr
def pr_body(rec: dict[str, Any], summary: str, total_before: int, total_after: int) -> str:
    new = ", ".join(rec["cases_added"])
    b_rate, a_rate = rec["before"]["pass_rate"], rec["after"]["pass_rate"]
    flags = ", ".join(rec["flags"]) or "owner-initiated"
    return "\n".join(
        [
            f"## {rec['skill']} {rec['from_version']} → {rec['to_version']}",
            "",
            f"**Improvement:** {rec['id']} · flags: {flags} · cluster {rec['signature']}",
            f"**What changed:** {summary}",
            "",
            f"| Eval run | Cases | Pass rate | New case {new} |",
            "|---|---|---|---|",
            f"| Before ({rec['from_version']}) | {total_before} | {b_rate} | fail |",
            f"| After ({rec['to_version']}) | {total_after} | {a_rate} | pass |",
            "",
            "Regressions: none",
            "",
            "- [ ] Eval cases use invented data only (author attestation in each case)",
            "- [ ] Version bump matches the change (patch / minor / major)",
            "",
            f"<!-- tsl:improvement={rec['id']} -->",
        ]
    )


def open_pr(rt: Runtime, skill: str, imp_id: str | None, summary: str | None) -> dict[str, Any]:
    from tsl.github.client import GitHubUnavailable, repo_slug
    from tsl.telemetry.emit import emit

    sk = _skill(rt, skill)
    plan = find_plan(rt, sk.id, imp_id)
    if plan is None:
        raise TslError("E-ENV-01", item="an improvement plan (tsl improve plan)")
    imp = str(plan["improvement_id"])
    evidence = sk.dir / "evals" / "improvements" / f"{imp}.json"
    if not evidence.is_file():
        raise TslError("E-ENV-01", item=f"improvement evidence {imp} (run tsl improve check)")
    data, codes = check(rt, skill, imp)
    if codes:
        raise raise_first(data, codes)
    g = library_git(sk)
    if g is None or not g.has_remote():
        raise TslError("E-ENV-01", item="a git clone of the skill-library repo with a remote")
    branch = f"improve/{sk.id}/{imp}"
    if g.branch() != branch:
        raise TslError("E-ENV-01", item=f"the improvement branch {branch} checked out")
    top = Path(g.out("rev-parse", "--show-toplevel"))
    rel = sk.dir.resolve().relative_to(top.resolve()).as_posix()
    rec = read_json(evidence)
    try:
        Git(top).commit(
            f"improve({sk.id}): {rec['from_version']} -> {rec['to_version']} ({imp})", [rel]
        )
    except GitError as exc:
        raise exc.tsl() from None
    if not g.push(branch):
        raise TslError("E-GIT-01", op="push", detail=branch)
    before = read_json(sk.dir / rec["before"]["result"])
    after = read_json(sk.dir / rec["after"]["result"])
    try:
        pr = rt.github.create_pull_request(
            repo_slug(g.out("remote", "get-url", "origin")),
            branch,
            "main",
            f"{sk.id} {rec['from_version']} → {rec['to_version']}",
            pr_body(
                rec, summary or "See the skill diff.", len(before["cases"]), len(after["cases"])
            ),
            False,
            ["truminds", "improvement"],
        )
    except GitHubUnavailable as exc:
        raise TslError("E-GIT-01", op="pull request", detail=str(exc)) from None
    emit(
        rt,
        "improvement.proposed",
        {
            "improvement_id": imp,
            "skill": sk.id,
            "from_version": rec["from_version"],
            "to_version": rec["to_version"],
            "flag_ids": rec["flags"],
            "before_pass_rate": rec["before"]["pass_rate"],
            "after_pass_rate": rec["after"]["pass_rate"],
            "cases_added": len(rec["cases_added"]),
        },
    )
    return {
        "improvement_id": imp,
        "branch": branch,
        "pr": {"number": pr.number, "url": pr.url, "draft": pr.draft},
        "from_version": rec["from_version"],
        "to_version": rec["to_version"],
    }
