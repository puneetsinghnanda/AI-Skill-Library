"""tsl ci-verify: re-check a pull request's records with no LLM.

SDD-03 §13, SDD-07 §7.4, SDD-04 §6.13.
"""

from __future__ import annotations

import fnmatch
import re
from pathlib import Path
from typing import Any

from tsl.approvals import approvals_md
from tsl.core.clock import parse_iso
from tsl.core.config import effective_bands
from tsl.core.errors import TslError
from tsl.core.frontmatter import split
from tsl.core.hashing import sha256_bytes, sha256_file
from tsl.core.jsonio import read_json
from tsl.core.paths import approvals_path, feedback_path, sibling
from tsl.core.repo import Companion
from tsl.core.runtime import Runtime
from tsl.github.client import GitHubUnavailable, repo_slug
from tsl.gitops.git import Git, GitError
from tsl.harness import citations
from tsl.harness.decide import DecideInput, evaluate
from tsl.identity.verify import accept, facts_from
from tsl.insights.client import InsightsUnavailable
from tsl.orchestrator.run import RunCtx
from tsl.state.store import final_ok_attempt

MARKER = re.compile(r"<!--\s*tsl:run_id=(run_[0-9A-HJKMNP-TV-Z]{26})\s*-->")
VERIFY_ROLES = ["engineer", "tech_lead"]


class Fail(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code


def _used_before(ctx: RunCtx, step: str, n: int) -> dict[str, int]:
    used = {"checks": 0, "review": 0, "verifier": 0}
    for a in ctx.step(step)["attempts"]:
        if int(a["n"]) >= n or a.get("outcome") != "RETRY":
            continue
        fb = ctx.comp.path(feedback_path(ctx.run_id, step, int(a["n"])))
        kind = str(read_json(fb).get("kind")) if fb.is_file() else "checks"
        if kind in used:
            used[kind] += 1
    return used


def ci_verify(
    rt: Runtime,
    number: int,
    repo: str,
    companion: Path,
    head: str | None,
    product: Path | None,
    ci_token: str | None,
) -> tuple[dict[str, Any], list[str], str]:
    codes: list[str] = []
    steps: list[dict[str, Any]] = []
    summary: list[str] = []
    try:
        pr = rt.github.get_pull_request(repo, number)
    except GitHubUnavailable:
        raise TslError("E-CI-06") from None
    head = head or pr.head_sha
    runs = MARKER.findall(pr.body or "")
    if not companion.joinpath("tsl.yaml").is_file():
        raise TslError("E-CI-06")
    comp = Companion(companion)
    non_code = comp.config.ci.get("non_code_globs", ["**/*.md", "docs/**"])
    if len(set(runs)) != 1:
        code_files = [
            f
            for f in pr.changed_files
            if not any(
                fnmatch.fnmatch(f, g) or fnmatch.fnmatch(f, g.removeprefix("**/")) for g in non_code
            )
        ]
        if code_files or len(set(runs)) > 1:
            return (
                {"result": "fail", "run_id": None, "codes": ["E-CI-01"], "steps": []},
                ["E-CI-01"],
                "PR has code changes but no single tsl:run_id marker",
            )
        return (
            {
                "result": "pass",
                "run_id": None,
                "codes": [],
                "steps": [],
                "note": "no marker and no code changes",
            },
            [],
            "no code changes",
        )
    run_id = runs[0]
    try:
        ctx = RunCtx(rt, comp, run_id)
    except TslError:
        return (
            {"result": "fail", "run_id": run_id, "codes": ["E-CI-05"], "steps": []},
            ["E-CI-05"],
            "state.json missing for the run",
        )
    product_name = next(
        (r.name for r in comp.config.product_repos if repo_slug(r.url) == repo), None
    )
    records: list[tuple[str, dict[str, Any], dict[str, Any], str]] = []
    from tsl.schemas.registry import errors as schema_errors

    for s in ctx.state["steps"]:
        if s["kind"] != "skill":
            continue
        a = final_ok_attempt(s) or (s["attempts"][-1] if s["attempts"] else None)
        if a is None or not a.get("record") or not comp.path(str(a["record"])).is_file():
            codes.append("E-CI-05")
            steps.append(
                {
                    "step": s["id"],
                    "attempt": None,
                    "outcome": None,
                    "band": None,
                    "signature": "bad",
                    "hash": "bad",
                    "recheck": "differs",
                }
            )
            continue
        rec = read_json(comp.path(str(a["record"])))
        if schema_errors("verification.v1", rec):
            codes.append("E-SCH-01")
        records.append((s["id"], rec, a, str(a["record"])))
        if rec["outcome"] == "ABORT":
            codes.append("E-CI-05")
    # signatures (fail closed when the registry cannot be reached)
    items = [
        {
            "kind": "verification",
            "key_id": r["key_id"],
            "signed_at": r["decided_at"],
            "roles_needed": VERIFY_ROLES,
            "anchor_sha256": sha256_file(comp.path(p)),
        }
        for _, r, _, p in records
    ]
    appr = (
        approvals_md.load(comp.path(approvals_path(run_id)))
        if comp.path(approvals_path(run_id)).is_file()
        else {"entries": []}
    )
    blocks = [e["signature"] for e in appr.get("entries", []) if e.get("signature")]
    from tsl.core.hashing import sha256_raw
    from tsl.identity.signing import canonical

    items += [
        {
            "kind": "approval",
            "key_id": b["key_id"],
            "signed_at": b["approved_at"],
            "roles_needed": [b["role"]],
            "anchor_sha256": sha256_raw(canonical(b)),
        }
        for b in blocks
    ]
    try:
        res = rt.insights.verify_signatures(
            ci_token or "", {"system": comp.config.system.code, "items": items}
        )
    except InsightsUnavailable:
        raise TslError("E-CI-06") from None
    if res.status != 200 or not isinstance(res.body, dict):
        raise TslError("E-CI-06")
    facts = res.body.get("items", [])
    req_anchor = False
    verdicts: list[str] = []
    for i, it in enumerate(items):
        obj = records[i][1] if i < len(records) else blocks[i - len(records)]
        v, why = accept(
            obj,
            parse_iso(str(it["signed_at"])),
            list(it["roles_needed"]),
            facts_from(facts[i] if i < len(facts) else None),
            require_anchor=req_anchor,
        )
        verdicts.append(v)
        if v == "bad":
            codes.append("E-CI-02")
            summary.append(f"signature {it['kind']} {it['key_id']}: {why}")
    for idx, (sid, rec, a, _p) in enumerate(records):
        row = {
            "step": sid,
            "attempt": rec["attempt"],
            "outcome": rec["outcome"],
            "band": rec["band"],
            "signature": verdicts[idx],
            "hash": "ok",
            "recheck": "same",
        }
        art = comp.path(rec["artifact_path"])
        if not art.is_file():
            art = comp.path(str(a["artifact"]))
        ck, rv = (
            comp.path(sibling(str(a["artifact"]), ".checks.json")),
            comp.path(sibling(str(a["artifact"]), ".review.json")),
        )
        if (
            not art.is_file()
            or sha256_file(art) != rec["artifact_sha256"]
            or not ck.is_file()
            or sha256_file(ck) != rec["checks_sha256"]
            or (
                rec["review_sha256"]
                and (not rv.is_file() or sha256_file(rv) != rec["review_sha256"])
            )
        ):
            row["hash"] = "bad"
            codes.append("E-CI-02")
        for up in rec.get("inputs", []):
            up_rec = comp.path(str(up["path"])[:-3] + ".verification.json")
            if (
                not up_rec.is_file()
                or sha256_bytes(up_rec.read_bytes()) != up["verification_sha256"]
            ):
                codes.append("E-CI-05")
                summary.append(f"{sid}: input chain broken at {up['path']}")
        if rec["outcome"] == "ESCALATE":
            st = ctx.step(sid)
            gid = f"G-escalate-{sid}-a{rec['attempt']}"
            e = approvals_md.entry(appr, gid)
            b = (e or {}).get("signature") or {}
            if (
                st["status"] != "ACCEPTED"
                or b.get("decision") != "approve"
                or b.get("self_approved")
            ):
                codes.append("E-CI-05")
        # code binding (E-CI-04)
        for ch in rec.get("product_changes") or []:
            if ch["repo"] != product_name:
                continue
            g = Git(product or Path.cwd())
            try:
                tree = g.tree_of(head)
                diff = sha256_bytes(g.diff_bytes(ch["base_sha"], tree))
            except GitError:
                codes.append("E-CI-04")
                continue
            if tree != ch["tree_sha"] or diff != ch["diff_sha256"]:
                codes.append("E-CI-04")
        try:
            if _recheck(rt, ctx, sid, rec, a) is False:
                row["recheck"] = "differs"
                codes.append("E-CI-03")
        except TslError as exc:
            if exc.code in ("E-ENV-01", "E-RUN-10"):
                raise TslError(
                    "E-CI-06", message=f"skill definitions unavailable ({exc.code})"
                ) from None
            row["recheck"] = "differs"
            codes.append("E-CI-03")
        steps.append(row)
    codes = list(dict.fromkeys(codes))
    result = "fail" if codes else "pass"
    return (
        {"result": result, "run_id": run_id, "codes": codes, "steps": steps, "head_sha": head},
        codes,
        "; ".join(summary),
    )


def _recheck(
    rt: Runtime, ctx: RunCtx, sid: str, rec: dict[str, Any], attempt: dict[str, Any]
) -> bool:
    """Re-run code checks and replay decide; True when everything matches the record."""
    from tsl.harness.verify import compute

    art_rel = str(attempt["artifact"])
    checks = read_json(ctx.comp.path(sibling(art_rel, ".checks.json")))
    run, _ = compute(
        rt,
        ctx,
        art_rel,
        attempt,
        fast=False,
        only=None,
        existing=checks,
        changes=checks.get("product_changes"),
    )
    for g in checks["gates"]:
        if g["id"] == "H3" and g["status"] == "skip":
            continue
        mine = run.gates[g["id"]].status
        if (mine == "fail") != (g["status"] == "fail"):
            return False
    review = read_json(ctx.comp.path(sibling(art_rel, ".review.json")))
    sk = ctx.skill_for(sid)
    cfg = ctx.comp.config
    pack = rec.get("pack") or {}
    shas = dict(pack.get("source_sha") or {})
    front = split(ctx.comp.path(art_rel).read_text(encoding="utf-8")).front
    shas.update(front.get("pack_sha") or {})
    shas.update({c["repo"]: c["tree_sha"] for c in checks.get("product_changes") or []})
    repos = {r.name for r in cfg.product_repos} | {str(r["name"]) for r in cfg.read_only_repos}
    d = evaluate(
        DecideInput(
            checks=checks,
            review=review,
            front=front,
            rubric=sk.rubric,
            limits=ctx.retry_limits(sid),
            used=_used_before(ctx, sid, int(rec["attempt"])),
            thresholds=effective_bands(
                sk.harness.get("bands"), (cfg.harness.get("bands") or {}).get(sk.id)
            ),
            s5=str(rec["signals"]["S5"]),
            requires_fresh_pack=ctx.requires_fresh_pack,
            is_code=sk.is_code,
            change_limits=cfg.limits(),
            resolver=citations.Resolver(ctx.comp.root, ctx.comp.local_paths(), shas),
            repos=repos,
        )
    )
    return bool(d.outcome == rec["outcome"] and d.band == rec["band"] and d.caps == rec["caps"])
