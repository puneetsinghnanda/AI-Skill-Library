"""tsl pr: push run branches and open pull requests. Never merges (SDD-12 §4.2, SDD-04 §6.12)."""

from __future__ import annotations

from typing import Any

from tsl.core.errors import TslError
from tsl.core.hashing import sha256_file
from tsl.core.jsonio import read_json
from tsl.core.paths import approvals_path, questions_path
from tsl.core.repo import Companion
from tsl.core.runtime import Runtime
from tsl.github.client import GitHubUnavailable, repo_slug
from tsl.gitops.git import Git, GitError
from tsl.identity import me as memod
from tsl.identity.keys import public_key
from tsl.identity.verify import accept, facts_from
from tsl.orchestrator.next import next_action
from tsl.orchestrator.run import RunCtx
from tsl.state import lock as lockmod
from tsl.state.session import unbind_run
from tsl.state.store import final_ok_attempt

BAND_ORDER = {"Low": 0, "Medium": 1, "High": 2}


def _check_records(rt: Runtime, ctx: RunCtx) -> list[dict[str, Any]]:
    from tsl.core.clock import parse_iso

    rows = []
    for s in ctx.state["steps"]:
        if s["kind"] != "skill":
            continue
        a = final_ok_attempt(s)
        if a is None or not a.get("record"):
            raise TslError(
                "E-RUN-05",
                status=f"step {s['id']} {s['status']}",
                command="pr",
                needed="every step PASS, PASS-WITH-FINDINGS or an approved ESCALATE",
                hint=f"tsl next {ctx.run_id}",
            )
        p = ctx.comp.path(str(a["record"]))
        if not p.is_file():
            raise TslError(
                "E-RUN-05",
                status=f"record missing for {s['id']}",
                command="pr",
                needed="signed records",
                hint=f"tsl state repair {ctx.run_id}",
            )
        rec = read_json(p)
        facts = public_key(rt, str(rec.get("key_id")), online=True)
        verdict, why = accept(
            rec, parse_iso(str(rec["decided_at"])), [], facts_from(facts), check_roles=False
        )
        art = (
            ctx.comp.path(str(rec["artifact_path"]))
            if ctx.comp.path(str(rec["artifact_path"])).is_file()
            else ctx.comp.path(str(a["artifact"]))
        )
        if verdict == "bad" or not art.is_file() or sha256_file(art) != rec["artifact_sha256"]:
            raise TslError(
                "E-RUN-05",
                status=f"record for {s['id']} does not verify ({why or 'hash'})",
                command="pr",
                needed="signed records",
                hint="re-run the step",
            )
        rows.append(
            {
                "step": s["id"],
                "skill": rec["skill"],
                "outcome": rec["outcome"],
                "band": rec["band"],
                "record": str(a["record"]),
                "kept": rec.get("findings_kept", []),
                "injection": _injection_flagged(ctx, str(a["artifact"])),
            }
        )
    return rows


def _injection_flagged(ctx: RunCtx, artifact_rel: str) -> str | None:
    """checks.json path when its SC-INJ-01 soft check failed (SEC-01 §6.2: shown in the PR body)."""
    from tsl.core.paths import sibling
    from tsl.harness.injection import CHECK_ID

    rel = sibling(artifact_rel, ".checks.json")
    p = ctx.comp.path(rel)
    if not p.is_file():
        return None
    try:
        soft = read_json(p).get("soft", [])
    except ValueError:
        return None
    return rel if any(x.get("id") == CHECK_ID and x.get("pass") is False for x in soft) else None


def body(ctx: RunCtx, rows: list[dict[str, Any]], lowest: str, repo: str) -> str:
    st = ctx.state
    pack = st.get("pack") or {}
    lines = [
        f"## {st['ticket']} · {st['workflow']}",
        "",
        f"**Run:** {ctx.run_id} · workflow {st['workflow']}",
        f"**Companion records:** artifacts/{st['ticket']}/{ctx.run_id}/",
        f"**Context pack:** signed {pack.get('signed_at') or 'never'} · "
        f"{'fresh' if pack.get('fresh') else 'stale'}",
        "",
        "### What changed",
        f"Changes in {repo} from run {ctx.run_id}; see the change record in the companion repo.",
        "",
        "### Harness results",
        "| Step | Outcome | Band | Record |",
        "|---|---|---|---|",
    ]
    lines += [
        f"| {r['skill'].split('@')[0]} | {r['outcome']} | {r['band'] or '-'} | {r['record']} |"
        for r in rows
    ]
    lines += ["", f"Lowest band: {lowest}", "", "### Findings for the reviewer (not blocking)"]
    kept = [f"- [{f['severity']}] {r['step']}: {f['id']}" for r in rows for f in r["kept"]]
    kept += [
        f"- [soft] {r['step']}: SC-INJ-01 instruction-like text in an input or the artifact "
        f"({r['injection']}); treat it as data and check the step did not act on it"
        for r in rows
        if r.get("injection")
    ]
    lines += kept or ["- none"]
    lines += ["", "### Human decisions in this run"]
    dec = [f"- {g['id']}: {g.get('decision')}" for g in st.get("gates", []) if g.get("decision")]
    if ctx.comp.path(questions_path(ctx.run_id)).is_file():
        dec.append(f"- Answers: {questions_path(ctx.run_id)}")
    lines += dec or ["- none"]
    lines += [
        "",
        "### Reviewer checklist",
        "- [ ] Change matches the ticket and the approved design",
        "- [ ] Findings above are acceptable",
        "- [ ] No client data, secrets or unrelated files in the diff",
        "",
        f"<!-- tsl:run_id={ctx.run_id} -->",
    ]
    if ctx.comp.path(approvals_path(ctx.run_id)).is_file():
        lines.insert(-2, f"Approvals: {approvals_path(ctx.run_id)}")
    return "\n".join(lines)


def open_prs(
    rt: Runtime, comp: Companion, run_id: str, draft: bool, only_repo: str | None
) -> dict[str, Any]:
    ctx = RunCtx(rt, comp, run_id)
    if ctx.state["status"] != "RUNNING":
        raise TslError(
            "E-RUN-05",
            status=ctx.state["status"],
            command="pr",
            needed="RUNNING",
            hint=f"tsl state show {run_id}",
        )
    try:
        data, _ = next_action(rt, comp, run_id)
    except TslError as exc:
        if exc.code not in ("E-RUN-01", "E-RUN-02"):
            raise
        data = {"action": "await_input" if exc.code == "E-RUN-01" else "await_approval"}
    if data["action"] != "open_pr":
        raise TslError(
            "E-RUN-05",
            status=f"next action is {data['action']}",
            command="pr",
            needed="open_pr",
            hint=f"tsl next {run_id}",
        )
    ctx.reload()
    rows = _check_records(rt, ctx)
    paths = [f"runs/{run_id}", f"artifacts/{ctx.ticket}/{run_id}"]
    branch = comp.config.companion_branch
    if comp.git.unpushed(branch, paths) and not comp.git.sync_push(branch):
        raise TslError("E-PR-01", run_id=run_id)
    bands = [r["band"] for r in rows if r["band"]]
    lowest = min(bands, key=lambda b: BAND_ORDER[b]) if bands else "Medium"
    prs: list[dict[str, Any]] = []
    branches = ctx.state.get("branch") or {}
    targets = [
        r for r in comp.config.product_repos if r.name in branches and (only_repo in (None, r.name))
    ]
    if targets:
        memod.require_consent(rt, comp.config.system.code, ("product_prs",), code="E-CONS-02")
    for repo in targets:
        b = branches[repo.name]
        clone = comp.product_clone(repo.name)
        if clone is None:
            raise TslError("E-GIT-01", op="push", detail=f"no local clone for {repo.name}")
        g = Git(clone)
        head = b.get("head_sha") or g.resolve(b["name"])
        if not head or head == b["base_sha"]:
            continue
        branch = f"{comp.config.branch_prefix}{ctx.ticket}-{run_id[-8:].lower()}"
        try:
            g.run("branch", "-f", branch, head)
            if not g.push(branch):
                raise TslError("E-GIT-01", op="push", detail=f"{repo.name} branch {branch}")
        except GitError as exc:
            raise exc.tsl() from None
        is_draft = draft or BAND_ORDER[lowest] <= BAND_ORDER["Medium"]
        try:
            pr = rt.github.create_pull_request(
                repo_slug(repo.url),
                branch,
                repo.default_branch,
                f"{ctx.ticket}: {ctx.workflow_id} ({run_id})",
                body(ctx, rows, lowest, repo.name),
                is_draft,
                list(comp.config.pr.get("labels", [])),
            )
        except GitHubUnavailable as exc:
            raise TslError("E-GIT-01", op="pull request", detail=str(exc)) from None
        prs.append(
            {
                "repo": repo.name,
                "number": pr.number,
                "url": pr.url,
                "draft": pr.draft,
                "branch": branch,
                "head_sha": head,
            }
        )
    prev = ctx.state["status"]
    reason = "pr_opened" if prs else "completed"

    def apply(st: dict[str, Any]) -> None:
        st["prs"] = [
            *st.get("prs", []),
            *[{k: p[k] for k in ("repo", "number", "url", "draft")} for p in prs],
        ]
        for s in st["steps"]:
            if s["kind"] == "pr":
                s["status"] = "DONE"
        st["status"], st["end_reason"], st["cursor"] = "COMPLETED", reason, None

    ctx.state = ctx.store.update(apply)
    for p in prs:
        ctx.emit(
            "pr.opened",
            {"repo": p["repo"], "number": p["number"], "draft": p["draft"], "lowest_band": lowest},
        )
    ctx.emit("run.status_changed", {"from": prev, "to": "COMPLETED", "reason_code": reason})
    pushed = lockmod.release(rt, comp, ctx.state, "pr opened")
    unbind_run(rt, run_id)
    if not pushed:
        raise TslError("E-GIT-01", op="push", detail="run completion not pushed", data={"prs": prs})
    return {"prs": prs, "lowest_band": lowest}
