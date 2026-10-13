"""tsl next: name the single next action of a run (SDD-02 §6). Idempotent."""

from __future__ import annotations

from typing import Any

from tsl.approvals import approvals_md
from tsl.core.clock import iso
from tsl.core.errors import TslError
from tsl.core.paths import RECORD_SUFFIXES, approvals_path, feedback_path, history_dir, sibling
from tsl.core.repo import Companion
from tsl.core.runtime import Runtime
from tsl.gitops.git import Git, GitError
from tsl.orchestrator.run import RunCtx
from tsl.orchestrator.workflow import downstream, step_id, step_kind
from tsl.state import lock as lockmod
from tsl.state.session import unbind_run
from tsl.state.store import final_ok_attempt, latest

DONE_LIKE = ("DONE", "ACCEPTED", "APPROVED")
STOPPED = ("aborted", "rejected", "cancelled", "lock_released", "archived")


def _budget(ctx: RunCtx, sid: str) -> dict[str, str]:
    lim = ctx.retry_limits(sid)
    used = ctx.step(sid).get("budget_used") or {}
    return {k: f"{used.get(k, 0)}/{lim[k]}" for k in ("checks", "review", "verifier")}


def _action_for_attempt(ctx: RunCtx, sid: str, action: str) -> dict[str, Any]:
    st = ctx.step(sid)
    a = latest(st)
    if a is None:
        raise TslError("E-RUN-09", step=sid, run_id=ctx.run_id)
    sk = ctx.skill_for(sid)
    inputs = [
        {"name": i["name"], "path": i["path"], "sha256": i["sha256"], "schema": i["schema"]}
        for i in ctx.resolve_inputs(sid)
        if i["sha256"]
    ]
    answers = None
    if a["cause"] == "input_answered":
        answers = ctx.questions_rel()
    elif a["cause"] == "gate_changes":
        answers = approvals_path(ctx.run_id)
    return {
        "schema": "next-action.v1",
        "action": action,
        "run_id": ctx.run_id,
        "step": sid,
        "attempt": a["n"],
        "cause": a["cause"],
        "skill": sk.ref,
        "artifact_path": a["artifact"],
        "inputs": inputs,
        "feedback": a.get("feedback"),
        "answers": answers,
        "context_sections": list(sk.meta.get("context_sections", [])),
        "budget": _budget(ctx, sid),
        "progress": ctx.progress(sid),
    }


def _deps_done(ctx: RunCtx, sdef: dict[str, Any]) -> bool:
    return all(ctx.step(d)["status"] in DONE_LIKE for d in sdef.get("after", []))


def pending_cause(ctx: RunCtx, sid: str) -> str:
    st = ctx.step(sid)
    if st["status"] == "STALE":
        return "stale_rerun"
    a = latest(st)
    for g in reversed(ctx.state.get("gates", [])):
        if (
            g.get("step") == sid
            and g.get("decision") in ("changes", "reject")
            and g.get("decided_at")
            and (a is None or str(g["decided_at"]) >= str(a.get("started_at", "")))
        ):
            return "gate_changes" if g["decision"] == "changes" else "gate_reject"
    if a is None:
        return "first"
    if a.get("outcome") == "RETRY":
        p = ctx.comp.path(feedback_path(ctx.run_id, sid, int(a["n"])))
        kind = "checks"
        if p.is_file():
            from tsl.core.jsonio import read_json

            kind = str(read_json(p).get("kind", "checks"))
        return {
            "checks": "retry_checks",
            "review": "retry_review",
            "verifier": "retry_verifier",
        }.get(kind, "retry_checks")
    if a.get("outcome") == "NEEDS-INPUT":
        return "input_answered"
    pinned = ctx.state["pinned"]["skills"].get(str(a["skill"]).split("@")[0])
    if pinned and str(a["skill"]).split("@")[1] != pinned:
        return "repin"
    return "retry_checks" if a.get("outcome") == "RETRY" else "first"


def archive_attempt(ctx: RunCtx, sid: str, attempt: dict[str, Any]) -> None:
    """Move attempt N's files into history/<step>/a<N>/ (git rename; never edited, R-03)."""
    cur = ctx.artifact_rel(sid)
    dest = history_dir(ctx.ticket, ctx.run_id, sid, int(attempt["n"]))
    git = ctx.comp.git
    for suffix in (".md", *RECORD_SUFFIXES):
        src = cur if suffix == ".md" else sibling(cur, suffix)
        if ctx.comp.path(src).exists():
            target = f"{dest}/{sid}{suffix}"
            try:
                git.mv(src, target)
            except GitError:
                ctx.comp.path(target).parent.mkdir(parents=True, exist_ok=True)
                ctx.comp.path(src).replace(ctx.comp.path(target))
    if attempt.get("artifact") == cur:
        attempt["artifact"] = f"{dest}/{sid}.md"
    if attempt.get("record") == sibling(cur, ".verification.json"):
        attempt["record"] = f"{dest}/{sid}.verification.json"


def _open_attempt(ctx: RunCtx, sid: str, cause: str) -> None:
    sk = ctx.skill_for(sid)
    inputs = ctx.resolve_inputs(sid)
    rt = ctx.rt
    branches: dict[str, Any] = {}
    if sk.is_code:
        branches = _ensure_branches(ctx)

    def apply(st: dict[str, Any]) -> None:
        step = next(s for s in st["steps"] if s["id"] == sid)
        prev = latest(step)
        if prev is not None:
            archive_attempt(ctx, sid, prev)
        fb = None
        if prev is not None and prev.get("outcome") in (
            "RETRY",
            "ESCALATE",
            "PASS",
            "PASS-WITH-FINDINGS",
        ):
            fp = feedback_path(ctx.run_id, sid, int(prev["n"]))
            fb = fp if ctx.comp.path(fp).is_file() else None
        n = (int(prev["n"]) + 1) if prev else 1
        step["attempts"].append(
            {
                "n": n,
                "cause": cause,
                "skill": sk.ref,
                "started_at": iso(rt.clock()),
                "decided_at": None,
                "outcome": None,
                "band": None,
                "artifact": ctx.artifact_rel(sid),
                "artifact_sha256": None,
                "record": None,
                "inputs": [
                    {"name": i["name"], "step": i["step"], "sha256": i["sha256"]}
                    for i in inputs
                    if i["step"] and i["sha256"]
                ],
                "feedback": fb,
                "answers_sha256": None,
            }
        )
        step["status"] = "IN_PROGRESS"
        st["cursor"] = {"step": sid, "attempt": n}
        for repo, b in branches.items():
            st.setdefault("branch", {})[repo] = b

    ctx.state = ctx.store.update(apply)
    a = latest(ctx.step(sid))
    if a is None:
        raise TslError("E-RUN-09", step=sid, run_id=ctx.run_id)
    seq = sum(len(s.get("attempts", [])) for s in ctx.state["steps"])
    body: dict[str, Any] = {
        "step": sid,
        "skill": sk.id,
        "skill_version": sk.version,
        "attempt": a["n"],
        "seq": seq,
    }
    if rt.session_id():
        body["session_id"] = rt.session_id()
    ctx.emit("step.started", body)


def _ensure_branches(ctx: RunCtx) -> dict[str, Any]:
    """First code step: local branch tsl/<ticket>/<run_id> in each product clone (SDD-02 §10.3)."""
    out: dict[str, Any] = {}
    existing = ctx.state.get("branch") or {}
    for repo in ctx.comp.config.product_repos:
        if repo.name in existing:
            continue
        clone = ctx.comp.product_clone(repo.name)
        if clone is None:
            continue
        g = Git(clone)
        name = f"tsl/{ctx.ticket}/{ctx.run_id}"
        try:
            base = g.resolve(f"origin/{repo.default_branch}") or g.head()
            if g.resolve(name) is None:
                g.run("checkout", "-q", "-b", name, base)
            else:
                g.run("checkout", "-q", name)
        except GitError as exc:
            raise exc.tsl() from None
        out[repo.name] = {"name": name, "base_sha": base, "head_sha": None}
    return out


def mark_stale(ctx: RunCtx) -> list[str]:
    """H6 hash check: DONE/ACCEPTED steps whose consumed inputs changed, plus downstream."""
    changed: list[tuple[str, str]] = []
    for s in ctx.state["steps"]:
        if s["status"] not in ("DONE", "ACCEPTED"):
            continue
        a = final_ok_attempt(s)
        if not a:
            continue
        for inp in a.get("inputs", []):
            cur = ctx.final_sha(str(inp["step"]))
            if cur is not None and cur != inp["sha256"]:
                changed.append((s["id"], str(inp["step"])))
                break
    if not changed:
        return []
    stale: dict[str, str] = {}
    for sid, cause_step in changed:
        stale.setdefault(sid, cause_step)
        for d in downstream(ctx.snapshot, sid):
            stale.setdefault(d, sid)

    def apply(st: dict[str, Any]) -> None:
        for s in st["steps"]:
            if s["id"] not in stale:
                continue
            if s["kind"] == "skill" and s["status"] in ("DONE", "ACCEPTED"):
                s["status"] = "STALE"
            elif s["kind"] == "gate" and s["status"] == "APPROVED":
                s["status"] = "PENDING"

    ctx.state = ctx.store.update(apply)
    for sid, cause_step in stale.items():
        if ctx.kinds().get(sid) == "skill":
            ctx.emit(
                "step.invalidated", {"step": sid, "cause_step": cause_step, "reason": "stale_input"}
            )
    return list(stale)


def _gate_entry(ctx: RunCtx, sdef: dict[str, Any]) -> None:
    gid = str(sdef["gate"])
    arts = sdef.get("artifacts") or [
        a for a in sdef.get("after", []) if ctx.kinds().get(a) == "skill"
    ]
    items = []
    for a in arts:
        att = final_ok_attempt(ctx.step(a))
        if att and att.get("artifact_sha256"):
            items.append(
                {"step": a, "path": str(att["artifact"]), "sha256": str(att["artifact_sha256"])}
            )
    approvals_md.append_entry(
        ctx.comp.path(approvals_path(ctx.run_id)),
        ctx.run_id,
        gid,
        str(sdef["role"]),
        "workflow_gate",
        [{"path": i["path"], "sha256": i["sha256"]} for i in items],
        "workflow gate (always)",
    )
    prev = ctx.state["status"]

    def apply(st: dict[str, Any]) -> None:
        step = next(s for s in st["steps"] if s["id"] == gid)
        step["status"] = "WAITING_APPROVAL"
        st["gates"] = [
            g for g in st.get("gates", []) if not (g["id"] == gid and not g.get("decision"))
        ]
        st["gates"].append(
            {
                "id": gid,
                "kind": "workflow",
                "status": "WAITING_APPROVAL",
                "artifacts": [{"step": i["step"], "sha256": i["sha256"]} for i in items],
                "decision": None,
                "approver_key": None,
                "decided_at": None,
            }
        )
        st["status"] = "PAUSED_APPROVAL"

    ctx.state = ctx.store.update(apply)
    unbind_run(ctx.rt, ctx.run_id)
    ctx.emit(
        "run.status_changed",
        {"from": prev, "to": "PAUSED_APPROVAL", "reason_code": "paused_approval", "gate": gid},
    )


def _waiting_gate(ctx: RunCtx) -> str | None:
    for g in ctx.state.get("gates", []):
        if g.get("status") == "WAITING_APPROVAL":
            return str(g["id"])
    return None


def next_action(rt: Runtime, comp: Companion, run_id: str) -> tuple[dict[str, Any], str]:
    """Return (next-action.v1 data, literal instruction for the run skill)."""
    ctx = RunCtx(rt, comp, run_id)
    with ctx.store.local_lock():
        ctx.assert_lock_held()
        ctx.assert_session()
        st = ctx.state
        if st["status"] == "COMPLETED":
            act = "stopped" if st.get("end_reason") in STOPPED else "done"
            return {"schema": "next-action.v1", "action": act, "run_id": run_id}, act
        if st["status"] == "PAUSED_INPUT":
            raise TslError(
                "E-RUN-01",
                next=f"answer {ctx.questions_rel()}, then /truminds:resume {run_id}",
                data={"schema": "next-action.v1", "action": "pause_input", "run_id": run_id},
            )
        if st["status"] == "PAUSED_APPROVAL":
            gate = _waiting_gate(ctx) or "?"
            raise TslError(
                "E-RUN-02",
                next=f"approver runs tsl approve {run_id} {gate}",
                data={"schema": "next-action.v1", "action": "pause_approval", "run_id": run_id},
            )
        for name, ver in st["pinned"]["skills"].items():
            sk = ctx.installed.get(name)
            if sk is None or sk.version != ver:
                raise TslError("E-RUN-10", detail=f"{name}@{ver}", run_id=run_id)
        lockmod.heartbeat(rt, comp, st)
        if st.get("cursor"):
            sid = str(st["cursor"]["step"])
            rel = ctx.artifact_rel(sid)
            if (
                comp.path(rel).is_file()
                and comp.path(sibling(rel, ".review.json")).is_file()
                and not comp.path(sibling(rel, ".verification.json")).is_file()
            ):
                data = _action_for_attempt(ctx, sid, "run_decide")
                return data, f"run tsl decide {rel}"
            data = _action_for_attempt(ctx, sid, "run_skill")
            return data, f"run skill {data['skill']}"
        mark_stale(ctx)
        for sdef in ctx.snapshot["steps"]:
            sid = step_id(sdef)
            status = ctx.step(sid)["status"]
            if status not in ("READY", "STALE", "PENDING", "IN_PROGRESS") or not _deps_done(
                ctx, sdef
            ):
                continue
            kind = step_kind(sdef)
            if kind == "skill":
                _open_attempt(ctx, sid, pending_cause(ctx, sid))
                data = _action_for_attempt(ctx, sid, "run_skill")
                return data, f"run skill {data['skill']}"
            if kind == "gate":
                _gate_entry(ctx, sdef)
                raise TslError(
                    "E-RUN-02",
                    next=f"approver runs tsl approve {run_id} {sid}",
                    data={"schema": "next-action.v1", "action": "pause_approval", "run_id": run_id},
                )
            if kind == "pr":
                return (
                    {"schema": "next-action.v1", "action": "open_pr", "run_id": run_id},
                    f"run tsl pr {run_id}",
                )
        blocked = [s["id"] for s in ctx.state["steps"] if s["status"] not in DONE_LIKE]
        if blocked:
            raise TslError(
                "E-RUN-05",
                status=f"steps {', '.join(blocked)} not ready",
                command="next",
                needed="a ready step",
                hint=f"tsl state show {run_id}",
            )
        reason = "completed" if ctx.snapshot.get("kind") == "read_only" else "pr_opened"
        prev = st["status"]

        def done(s: dict[str, Any]) -> None:
            s["status"], s["end_reason"], s["cursor"] = "COMPLETED", reason, None

        ctx.state = ctx.store.update(done)
        ctx.emit("run.status_changed", {"from": prev, "to": "COMPLETED", "reason_code": reason})
        lockmod.release(rt, comp, ctx.state, "complete")
        unbind_run(rt, run_id)
        return {"schema": "next-action.v1", "action": "done", "run_id": run_id}, "done"
