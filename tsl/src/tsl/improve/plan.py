"""tsl improve plan (SDD-11 §5, SDD-04 §6.17). Reads metadata only; never touches Jira."""

from __future__ import annotations

import re
from datetime import timedelta
from pathlib import Path
from typing import Any

from tsl.core.clock import iso, parse_iso
from tsl.core.errors import TslError
from tsl.core.jsonio import read_json, write_json
from tsl.core.runtime import Runtime
from tsl.identity import me as memod
from tsl.insights.client import InsightsUnavailable
from tsl.orchestrator.skills import load_skill

ROLES = {"engineer", "tech_lead", "skill_owner", "eng_lead", "admin"}


def _report(
    rt: Runtime, skill: str, report: Path | None, offline: bool
) -> tuple[dict[str, Any], str, list[dict[str, str]]]:
    warnings: list[dict[str, str]] = []
    cache = rt.home.improve_cache / f"{skill}.json"
    if report is not None:
        return dict(read_json(report)), str(report), warnings
    if offline:
        if not cache.is_file():
            raise TslError("E-NET-02", "No cached improvement report; run without --offline")
        body = dict(read_json(cache))
        age = rt.clock() - parse_iso(str(body.get("fetched_at")))
        warnings.append(
            {"code": "E-NET-01", "message": f"Cached report, {age // timedelta(hours=1)} h old"}
        )
        return body, str(cache), warnings
    me = memod.current_me(rt)
    if not any(g.get("role") in ROLES for g in me.get("grants", [])):
        raise TslError("E-AUTH-03", system="(any)")
    try:
        res = rt.insights.improvement_report(rt.token(), skill)
    except InsightsUnavailable:
        raise TslError("E-NET-02") from None
    if res.status == 403:
        raise TslError("E-AUTH-03", system="(skill owner)")
    if res.status != 200 or not isinstance(res.body, dict):
        raise TslError("E-NET-02")
    body = dict(res.body)
    write_json(cache, {**body, "fetched_at": iso(rt.clock())})
    return body, f"/v1/improvement/skills/{skill}", warnings


def plan(
    rt: Runtime,
    skill: str,
    report: Path | None,
    flag: str | None = None,
    offline: bool = False,
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    from tsl.evals.service import content_hash
    from tsl.improve.service import library_git, save_plan

    d = rt.plugin_root() / "skills" / skill
    if not (d / "skill.yaml").is_file():
        raise TslError("E-USE-01", detail=f"unknown skill {skill}", cmd="improve plan")
    sk = load_skill(d)
    body, ref, warnings = _report(rt, skill, report, offline)
    top: list[dict[str, Any]] = []
    clusters = {c.get("signature"): c for c in body.get("clusters", []) if isinstance(c, dict)}
    flags = [f for f in body.get("flags", []) if isinstance(f, dict)]
    if flag is not None and flag not in {f.get("id") for f in flags}:
        raise TslError("E-USE-01", detail=f"flag {flag} is not open for {skill}", cmd="improve")
    for f in flags:
        examples = []
        for c in clusters.values():
            examples += [str(e.get("run_id")) for e in c.get("examples", []) if e.get("run_id")]
        top.append(
            {
                "signal": f.get("signal"),
                "flag_id": f.get("id"),
                "value": f.get("value"),
                "count": f.get("sample"),
                "example_runs": examples[:10],
            }
        )
    for c in clusters.values():
        top.append(
            {
                "signal": "IS-9",
                "signature": c.get("signature"),
                "count": c.get("count"),
                "example_runs": [str(e.get("run_id")) for e in c.get("examples", [])][:10],
            }
        )
    imp_id = rt.ids.new("imp")
    chosen = [flag] if flag else []
    signature = None
    if clusters:
        best = max(clusters.values(), key=lambda c: int(c.get("count") or 0)).get("signature")
        if isinstance(best, str) and re.fullmatch(r"[A-Z-]+(\|[^|]*){4}", best):
            signature = best
    g = library_git(sk)
    branch = None
    base_sha = None
    if g is not None:
        rel = str(sk.dir)
        if g.out("status", "--porcelain", "--", rel):
            raise TslError("E-ENV-01", item=f"a clean working copy of skills/{sk.id}")
        base_sha = g.head()
        branch = f"improve/{sk.id}/{imp_id}"
        if not g.ok("checkout", "-q", "-b", branch):
            raise TslError("E-GIT-01", op="checkout", detail=branch)
    data = {
        "skill": sk.id,
        "version": sk.version,
        "report_ref": ref,
        "improvement_id": imp_id,
        "top_issues": top,
        "flags": chosen,
        "signature": signature,
        "branch": branch,
        "base_sha": base_sha,
        "skill_sha256": content_hash(sk),
        "cases_added": [],
        "first_step": "add_failing_eval_case",
        "eval_case_template": f"skills/{sk.id}/evals/_template/",
    }
    save_plan(rt, data)
    snapshot_base(rt, sk.dir, imp_id)
    return data, warnings


def snapshot_base(rt: Runtime, skill_dir: Path, imp_id: str) -> Path:
    """Copy the skill folder as it is now: the 'before' version for tsl improve check."""
    import shutil

    dst = rt.home.improve_cache / imp_id / "base" / skill_dir.name
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(
        skill_dir, dst, ignore=shutil.ignore_patterns("results", "improvements", ".git")
    )
    return dst
