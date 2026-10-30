"""tsl state start | resume | show | unlock | cancel | repair | repin.

SDD-02, SDD-04 §6.7, §6.21.
"""

from __future__ import annotations

import re
import shutil
from typing import Any

from tsl.approvals import approvals_md, questions_md
from tsl.core.clock import iso, parse_iso
from tsl.core.errors import TslError
from tsl.core.hashing import sha256_file
from tsl.core.jsonio import dump_yaml, dumps, read_json, write_json
from tsl.core.paths import (
    approvals_path,
    feedback_path,
    lock_path,
    questions_path,
    snapshot_path,
    state_path,
)
from tsl.core.repo import Companion
from tsl.core.runtime import Runtime
from tsl.gitops.git import GitError
from tsl.identity import me as memod
from tsl.identity.keys import active_info, public_key_strict
from tsl.identity.verify import accept, facts_from
from tsl.orchestrator import skills as skillmod
from tsl.orchestrator import workflow as wfmod
from tsl.orchestrator.run import RunCtx
from tsl.state import lock as lockmod
from tsl.state import ticket as ticketmod
from tsl.state.session import bind, compile_policy, unbind_run
from tsl.state.store import all_runs, latest, read_state_raw, write_new
from tsl.telemetry.emit import emit, flush_quietly

TICKET = re.compile(r"^[A-Za-z][A-Za-z0-9_]*-[0-9]+$")


def _require_git() -> None:
    if shutil.which("git") is None:
        raise TslError("E-ENV-01", item="git")


def _major(v: str) -> str:
    return v.split(".", 1)[0]


def start(
    rt: Runtime,
    comp: Companion,
    workflow: str,
    ticket: str,
    system: str | None = None,
    pod: str | None = None,
    ticket_file: str | None = None,
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    _require_git()
    cfg = comp.config
    warnings = list(comp.warnings)
    if system and system != cfg.system.code:
        raise TslError(
            "E-USE-01", detail=f"--system {system} is not this repo's system", cmd="state start"
        )
    if not TICKET.match(ticket) or len(ticket) > 40:
        raise TslError(
            "E-USE-01", detail=f"ticket {ticket!r} is not a ticket reference", cmd="state start"
        )
    tfile = ticketmod.load(ticket_file, ticket, cfg.deny_term_hashes) if ticket_file else None
    plugin_root = rt.plugin_root()
    plugin_version = rt.plugin_version()
    if plugin_version != rt.tsl_version:
        raise TslError("E-VER-01", a=rt.tsl_version, what="plugin", b=plugin_version)
    wf, wf_path = wfmod.load(plugin_root, workflow)
    installed = skillmod.installed(plugin_root)
    problems = wfmod.validate(wf, installed)
    if problems:
        code, ptr, msg = problems[0]
        raise TslError(code, detail=f"{ptr} {msg}")
    if wf["status"] == "deprecated":
        warnings.append({"code": "E-DEP-01", "message": f"workflow {workflow} is deprecated"})
    me = memod.require_grant(rt, {"engineer", "tech_lead"}, cfg.system.code, "E-AUTH-03")
    memod.require_consent(rt, cfg.system.code, ("code_processing", "companion_storage"))
    from tsl.context.freshness import status as pack_status

    requires_fresh = bool(wf.get("requires_fresh_pack", True))
    pk = pack_status(rt, comp)
    if requires_fresh and pk["state"] == "missing":
        raise TslError("E-CTX-01", detail="")
    if requires_fresh and pk["state"] == "invalid":
        raise TslError("E-CTX-03")
    if pk["state"] == "stale":
        warnings.append(
            {
                "code": "E-CTX-02",
                "message": f"Context pack is stale ({', '.join(pk['reasons'])}). "
                "Band capped at Medium.",
            }
        )
    from tsl.context.freshness import behind_warnings

    warnings += behind_warnings(pk)
    info = active_info(rt)
    if not info:
        raise TslError("E-AUTH-02")
    resolved = wfmod.resolve(wf, installed, wfmod.load_lock(wf_path))
    snap = wfmod.snapshot(wf, resolved)
    snap_text = dump_yaml(snap)
    run_id = rt.ids.new("run")
    now = iso(rt.clock())
    steps = []
    for s in snap["steps"]:
        entry: dict[str, Any] = {
            "id": wfmod.step_id(s),
            "kind": wfmod.step_kind(s),
            "status": "PENDING",
            "attempts": [],
        }
        if entry["kind"] == "skill":
            entry["budget_used"] = {"checks": 0, "review": 0, "verifier": 0, "rework": 0}
        steps.append(entry)
    session = rt.session_id()
    import hashlib
    import socket

    state: dict[str, Any] = {
        "schema": "run-state.v1",
        "run_id": run_id,
        "rev": 0,
        "workflow": f"{wf['id']}@{wf['version']}",
        "workflow_sha256": hashlib.sha256(snap_text.encode()).hexdigest(),
        "ticket": ticket,
        "system": cfg.system.code,
        "owner": info["key_id"],
        "owner_pseudonym": me["pseudonym"],
        "status": "RUNNING",
        "end_reason": None,
        "pinned": {
            "plugin": plugin_version,
            "tsl": rt.tsl_version,
            "skills": {r.split("@")[0]: r.split("@")[1] for r in resolved.values()},
        },
        "pack": pk["state_block"],
        "branch": {},
        "active_session": (
            {
                "session_id": session,
                "since": now,
                "host_hash": "h_" + hashlib.sha256(socket.gethostname().encode()).hexdigest()[:8],
            }
            if session
            else None
        ),
        "cursor": None,
        "steps": steps,
        "gates": [],
        "questions": {
            "round": 0,
            "open_blocking": 0,
            "open_non_blocking": 0,
            "answered_sha256": {},
        },
        "prs": [],
        "created_at": now,
        "updated_at": now,
        "heartbeat_at": now,
    }
    if pod:
        state["pod"] = pod
    from tsl.schemas.registry import errors

    errs = errors("run-state.v1", state)
    if errs:
        raise TslError(
            "E-INT-01", f"state invalid: {errs[0].pointer} {errs[0].message}", log_id="state"
        )
    files = {state_path(run_id): dumps(state), snapshot_path(run_id): snap_text}
    ticket_rel = None
    if tfile:
        ticket_rel = ticketmod.snapshot_rel(ticket, run_id)
        files[ticket_rel] = ticketmod.render(tfile, ticket, run_id, now)
    lock = lockmod.lock_body(rt, run_id, str(me["pseudonym"]), str(info["key_id"]))
    lockmod.take_lock(rt, comp, ticket, wf["id"], run_id, files, lock)
    rel = lock_path(ticket, wf["id"])
    if session:
        bind(rt, comp, session, run_id, rel, compile_policy(rt, comp, run_id, rt.tsl_version))
    body: dict[str, Any] = {
        "workflow": wf["id"],
        "workflow_version": wf["version"],
        "ticket_ref": ticket,
        "system": cfg.system.code,
        "plugin_version": plugin_version,
        "pinned_skills": state["pinned"]["skills"],
        "pack_fresh": pk["state"] == "fresh",
    }
    if session:
        body["session_id"] = session
    if pod:
        body["pod"] = pod
    emit(rt, "run.started", body, run_id, enabled=cfg.telemetry_enabled)
    if cfg.telemetry_enabled:
        flush_quietly(rt, max_seconds=1.5)
    first = next(wfmod.step_id(s) for s in snap["steps"])
    return {
        "run_id": run_id,
        "status": "RUNNING",
        "lock_path": rel,
        "pinned": {
            "plugin": plugin_version,
            "tsl": rt.tsl_version,
            "workflow": state["workflow"],
            "skills": state["pinned"]["skills"],
        },
        "pack": {"fresh": pk["state"] == "fresh", "signed_at": pk["state_block"].get("signed_at")},
        "first_step": first,
        "ticket_snapshot": ticket_rel,
    }, warnings


def _pull(comp: Companion) -> None:
    g = comp.git
    try:
        g.fetch()
        if g.resolve(f"origin/{comp.config.companion_branch}"):
            g.rebase(f"origin/{comp.config.companion_branch}")
    except GitError as exc:
        raise exc.tsl() from None


def _owner_check(rt: Runtime, ctx: RunCtx) -> dict[str, Any]:
    me = memod.current_me(rt)
    info = active_info(rt) or {}
    if (
        me.get("pseudonym") != ctx.state.get("owner_pseudonym")
        and info.get("key_id") != ctx.state["owner"]
    ):
        raise TslError("E-RUN-06", run_id=ctx.run_id, owner=ctx.state.get("owner_pseudonym", "?"))
    return me


def resume(
    rt: Runtime, comp: Companion, run_id: str, take_over: bool = False
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    warnings: list[dict[str, str]] = []
    _pull(comp)
    ctx = RunCtx(rt, comp, run_id)
    with ctx.store.local_lock():
        if ctx.state["status"] == "COMPLETED":
            raise TslError(
                "E-RUN-05",
                status="COMPLETED",
                command="state resume",
                needed="an open run",
                hint=f"tsl state show {run_id}",
            )
        ctx.assert_lock_held()
        _owner_check(rt, ctx)
        if _major(ctx.state["pinned"]["tsl"]) != _major(rt.tsl_version):
            raise TslError(
                "E-VER-01", a=rt.tsl_version, what="run pin", b=ctx.state["pinned"]["tsl"]
            )
        for name, ver in ctx.state["pinned"]["skills"].items():
            sk = ctx.installed.get(name)
            if sk is None or sk.version != ver:
                raise TslError("E-RUN-10", detail=f"{name}@{ver}", run_id=run_id)
        if not take_over:
            ctx.assert_session()
        answered: list[str] = []
        approvals: list[dict[str, Any]] = []
        prev = ctx.state["status"]
        if prev == "PAUSED_INPUT":
            answered = _resume_input(rt, ctx)
        elif prev == "PAUSED_APPROVAL":
            approvals = _resume_approval(rt, ctx)
        from tsl.context.freshness import status as pack_status

        pk = pack_status(rt, comp)
        session = rt.session_id()

        def fin(st: dict[str, Any]) -> None:
            st["pack"] = pk["state_block"]
            if session:
                st["active_session"] = {
                    "session_id": session,
                    "since": iso(rt.clock()),
                    "host_hash": (st.get("active_session") or {}).get("host_hash", "h_0000"),
                }

        ctx.state = ctx.store.update(fin)
        if pk["state"] == "stale":
            warnings.append(
                {"code": "E-CTX-02", "message": "Context pack is stale. Band capped at Medium."}
            )
        if ctx.state["status"] != prev:
            ctx.emit(
                "run.status_changed",
                {
                    "from": prev,
                    "to": ctx.state["status"],
                    "reason_code": "resumed"
                    if ctx.state["status"] == "RUNNING"
                    else str(ctx.state.get("end_reason")),
                },
            )
        if session and ctx.state["status"] == "RUNNING":
            bind(
                rt,
                comp,
                session,
                run_id,
                lockmod.lock_rel(ctx.state),
                compile_policy(rt, comp, run_id, ctx.state["pinned"]["tsl"]),
            )
        if ctx.state["status"] == "COMPLETED":
            lockmod.release(rt, comp, ctx.state, str(ctx.state.get("end_reason")))
            unbind_run(rt, run_id)
        else:
            ctx.push_best_effort(f"tsl({run_id}): resume", warnings)
    nxt = next(
        (
            s["id"]
            for s in ctx.state["steps"]
            if s["status"] in ("READY", "STALE", "IN_PROGRESS", "PENDING")
        ),
        None,
    )
    return {
        "run_id": run_id,
        "status": ctx.state["status"],
        "next_step": nxt,
        "answered": answered,
        "approvals": approvals,
    }, warnings


def _resume_input(rt: Runtime, ctx: RunCtx) -> list[str]:
    p = ctx.comp.path(questions_path(ctx.run_id))
    if not p.is_file():
        raise TslError("E-RUN-03", n=1)
    obj = questions_md.load(p)
    qs = obj.get("questions", [])
    frozen = dict((ctx.state.get("questions") or {}).get("answered_sha256", {}))
    changed = [
        qid
        for qid, q in questions_md.originals(qs).items()
        if qid in frozen and questions_md.answer_hash(q) != frozen[qid]
    ]
    if changed:
        raise TslError("E-RUN-07", ids=", ".join(changed))
    eff = questions_md.effective(qs)
    open_ids = [qid for qid in eff if qid not in frozen]
    missing = [
        qid
        for qid in open_ids
        if eff[qid]["blocking"]
        and (
            not eff[qid].get("answer")
            or not questions_md.valid_answered_by(eff[qid].get("answered_by"))
        )
    ]
    if missing:
        raise TslError("E-RUN-03", n=len(missing), data={"unanswered": missing})
    waiting = next((s for s in ctx.state["steps"] if s["status"] == "WAITING_INPUT"), None)
    created = parse_iso(str(obj["created_at"]))
    age = max(0, int((rt.clock() - created).total_seconds()))

    def apply(st: dict[str, Any]) -> None:
        q = st["questions"]
        for qid in open_ids:
            q["answered_sha256"][qid] = questions_md.answer_hash(eff[qid])
        q["open_blocking"] = q["open_non_blocking"] = 0
        for s in st["steps"]:
            if s["status"] == "WAITING_INPUT":
                s["status"] = "READY"
        st["status"] = "RUNNING"

    ctx.state = ctx.store.update(apply)
    questions_md.set_status(p, "answered")
    for qid in open_ids:
        ctx.emit(
            "question.answered",
            {
                "step": waiting["id"] if waiting else "unknown",
                "question_id": qid,
                "age_s": age,
                "accepted_default": not eff[qid].get("answer"),
            },
        )
    return open_ids


REAPPROVE = "The approver runs tsl doctor, then tsl approve {run} {gate} again"
APPROVAL_PROBLEMS = {
    "unknown_key": "the approver's signing key {key} is not registered on the service",
    "bad_signature": "the signature does not match the approver's key",
    "signed_before_key": "it was signed before the approver's key existed",
    "key_expired": "the approver's key had expired when it was signed",
    "revoked": "the approver's key was revoked before it was signed",
    "compromised": "the approver's key is marked compromised",
    "not_anchored_before_compromise": "the approver's key is marked compromised",
}


def _verify_block(rt: Runtime, ctx: RunCtx, gate: str, block: dict[str, Any]) -> None:
    """Raises a specific error when a signed approval does not verify (E-AUTH-01, E-NET-02,
    E-AUTH-11), so the user sees the real cause instead of a role problem."""
    from tsl.schemas.registry import errors

    path = approvals_path(ctx.run_id)
    if errors("approval-signature.v1", block):
        raise TslError(
            "E-AUTH-11",
            gate=gate,
            reason="the signature block is malformed (edited by hand?)",
            fix=f"git checkout HEAD -- {path}, then repeat; if it stays, approve again",
        )
    facts = public_key_strict(rt, str(block["key_id"]))
    verdict, why = accept(
        block, parse_iso(str(block["approved_at"])), [], facts_from(facts), check_roles=False
    )
    if verdict == "bad":
        raise TslError(
            "E-AUTH-11",
            gate=gate,
            reason=APPROVAL_PROBLEMS.get(str(why), str(why)).format(key=block["key_id"]),
            fix=REAPPROVE.format(run=ctx.run_id, gate=gate),
        )


def _resume_approval(rt: Runtime, ctx: RunCtx) -> list[dict[str, Any]]:
    obj = approvals_md.load(ctx.comp.path(approvals_path(ctx.run_id)))
    decided: list[dict[str, Any]] = []
    for g in [x for x in ctx.state.get("gates", []) if x.get("status") == "WAITING_APPROVAL"]:
        e = approvals_md.entry(obj, str(g["id"]))
        block = (e or {}).get("signature")
        if not e or not block:
            raise TslError("E-RUN-02", next=f"approver runs tsl approve {ctx.run_id} {g['id']}")
        _verify_block(rt, ctx, str(g["id"]), block)
        if block["role"] != e["role"] or block["decision"] != e["decision"]:
            raise TslError("E-AUTH-05", role=e["role"], gate=g["id"])
        if block["comment_sha256"] != approvals_md.comment_sha256(e.get("comment")):
            raise TslError("E-RUN-08", detail=f"{g['id']} comment changed after signing")
        for a in e["artifacts"]:
            p = ctx.comp.path(a["path"])
            if not p.is_file() or sha256_file(p) != a["sha256"]:
                raise TslError("E-RUN-08", detail=f"{a['path']} changed")
        decided.append(_apply_decision(rt, ctx, g, e, block))
    return decided


def _apply_decision(
    rt: Runtime, ctx: RunCtx, gate: dict[str, Any], entry: dict[str, Any], block: dict[str, Any]
) -> dict[str, Any]:
    decision = str(block["decision"])
    gid = str(gate["id"])
    kind = gate["kind"]
    target: str | None = None
    if kind == "workflow":
        sdef = ctx.step_def(gid)
        if decision == "changes":
            target = str(sdef.get("on_changes") or (sdef.get("artifacts") or sdef["after"])[-1])
        elif decision == "reject" and sdef["on_reject"] != "abort":
            target = str(sdef["on_reject"])
    else:
        target = str(gate.get("step"))
    reruns = target is not None and (kind == "workflow" or decision == "changes")
    if decision in ("changes", "reject") and reruns and target:
        st_target = ctx.step(target)
        if int((st_target.get("budget_used") or {}).get("rework", 0)) >= ctx.max_rework:
            raise TslError(
                "E-RUN-05",
                status="rework limit reached",
                command="state resume",
                needed="approve or abort",
                hint="the approver must approve or abort",
            )
    if decision == "changes" and target:
        last = latest(ctx.step(target))
        if last is not None:
            fb = {
                "schema": "feedback.v1",
                "run_id": ctx.run_id,
                "step": target,
                "from_attempt": int(last["n"]),
                "kind": "rework",
                "gate_failures": [],
                "findings": [],
                "dropped": [],
                "must_resolve": [],
                "comment_sha256": block["comment_sha256"],
                "comment": entry.get("comment"),
            }
            write_json(ctx.comp.path(feedback_path(ctx.run_id, target, int(last["n"]))), fb)
    stale: list[str] = []
    if decision == "reject" and target and kind == "workflow":
        stale = [target, *wfmod.downstream(ctx.snapshot, target)]
    head_shas: dict[str, str] = {}
    # An approved escalation accepts the step as it stands: commit its code to the run
    # branch as a PASS does, or the pull request leaves it out.
    if decision == "approve" and kind != "workflow" and target and ctx.skill_for(target).is_code:
        from tsl.harness.decide_service import _checkpoint

        sstate = next(x for x in ctx.state["steps"] if x["id"] == target)
        head_shas = _checkpoint(ctx, target, sstate["attempts"][-1])
    now = iso(rt.clock())

    def apply(st: dict[str, Any]) -> None:
        g = next(x for x in st["gates"] if x["id"] == gid and x["status"] == "WAITING_APPROVAL")
        g.update({"decision": decision, "approver_key": block["key_id"], "decided_at": now})
        g["status"] = {
            "approve": "APPROVED",
            "changes": "CHANGES",
            "reject": "REJECTED",
            "abort": "ABORTED",
        }[decision]
        if target:
            g["step"] = target
        steps = {s["id"]: s for s in st["steps"]}
        if kind == "workflow":
            gs = steps[gid]
            gs["status"] = "APPROVED" if decision == "approve" else "PENDING"
            if decision == "changes" and target:
                t = steps[target]
                t["status"] = "READY"
                t["budget_used"]["rework"] += 1
            if decision == "reject" and target:
                for sid in stale:
                    s = steps.get(sid)
                    if s is None:
                        continue
                    if s["kind"] == "skill" and s["attempts"]:
                        s["status"] = "STALE" if sid != target else "READY"
                    elif s["kind"] == "gate":
                        s["status"] = "PENDING"
                steps[target]["budget_used"]["rework"] += 1
        else:
            s = steps[str(gate["step"])]
            if decision == "approve":
                s["status"] = "ACCEPTED"
            elif decision == "changes":
                s["status"] = "READY"
                bu = s["budget_used"]
                if bu["rework"] == 0:
                    bu["checks"] = bu["review"] = bu["verifier"] = 0
                bu["rework"] += 1
        for repo, sha in head_shas.items():
            if repo in st.get("branch", {}):
                st["branch"][repo]["head_sha"] = sha
        if decision == "abort" or (decision == "reject" and (kind != "workflow" or not target)):
            st["status"], st["end_reason"] = "COMPLETED", "rejected"
        else:
            st["status"] = "RUNNING"

    ctx.state = ctx.store.update(apply)
    return {"gate": gid, "decision": decision, "approver_key": block["key_id"]}


def show(rt: Runtime, comp: Companion, run_id: str | None, all_: bool) -> dict[str, Any]:
    ids = [run_id] if run_id else all_runs(comp)
    runs = []
    for rid in ids:
        st = read_state_raw(comp, rid)
        if st is None:
            raise TslError("E-RUN-04", run_id=rid)
        if not all_ and not run_id and st["status"] == "COMPLETED":
            continue
        cur = st.get("cursor") or {}
        waiting = None
        if st["status"] == "PAUSED_INPUT":
            waiting = questions_path(rid)
        elif st["status"] == "PAUSED_APPROVAL":
            waiting = next(
                (g["id"] for g in st.get("gates", []) if g["status"] == "WAITING_APPROVAL"), None
            )
        pending_release = st["status"] == "COMPLETED" and lockmod.lock_is_held(comp, st)
        runs.append(
            {
                "run_id": rid,
                "ticket": st["ticket"],
                "workflow": st["workflow"],
                "status": st["status"],
                "end_reason": st.get("end_reason"),
                "step": cur.get("step"),
                "attempt": cur.get("attempt"),
                "updated_at": st["updated_at"],
                "waiting_on": waiting,
                "lock_release_pending": pending_release,
            }
        )
    return {"runs": runs}


def unlock(rt: Runtime, comp: Companion, ticket: str, workflow: str, reason: str) -> dict[str, Any]:
    cfg = comp.config
    memod.require_grant(rt, {"tech_lead"}, cfg.system.code, "E-AUTH-04", action="state unlock")
    _pull(comp)
    rel = lock_path(ticket, workflow)
    lk = lockmod.read_lock(comp, rel)
    if lk is None:
        raise TslError(
            "E-RUN-05",
            status="unlocked",
            command="state unlock",
            needed="a lock",
            hint="nothing to release",
        )
    st = read_state_raw(comp, str(lk["run_id"]))
    if not lockmod.is_stale(rt, comp, st, lk):
        raise TslError(
            "E-RUN-05",
            status="active (lock not stale)",
            command="state unlock",
            needed=f"no state change for {cfg.gates.lock_timeout_hours} h",
            hint="ask the run owner",
        )
    comp.path(rel).unlink()
    try:
        comp.git.commit(
            f"tsl({lk['run_id']}): unlock ({reason[:60]})",
            [rel],
            trailer=f"Tsl-Run: {lk['run_id']}",
        )
    except GitError as exc:
        raise exc.tsl() from None
    if not comp.git.sync_push(cfg.companion_branch):
        raise TslError("E-GIT-01", op="push", detail="lock release not pushed")
    emit(
        rt,
        "run.status_changed",
        {
            "from": (st or {}).get("status", "RUNNING"),
            "to": "COMPLETED",
            "reason_code": "lock_released",
        },
        str(lk["run_id"]),
        enabled=cfg.telemetry_enabled,
    )
    return {"released_lock": rel, "run_id": lk["run_id"], "previous_holder": lk.get("holder")}


def cancel(rt: Runtime, comp: Companion, run_id: str, reason: str) -> dict[str, Any]:
    ctx = RunCtx(rt, comp, run_id)
    if ctx.state["status"] == "COMPLETED":
        raise TslError(
            "E-RUN-05",
            status="COMPLETED",
            command="state cancel",
            needed="an open run",
            hint="nothing to cancel",
        )
    try:
        _owner_check(rt, ctx)
    except TslError:
        me = memod.current_me(rt)
        if not memod.has_grant(me, {"tech_lead"}, comp.config.system.code):
            raise
    prev = ctx.state["status"]

    def apply(st: dict[str, Any]) -> None:
        st["status"], st["end_reason"], st["cursor"] = "COMPLETED", "cancelled", None

    ctx.state = ctx.store.update(apply)
    ctx.emit("run.status_changed", {"from": prev, "to": "COMPLETED", "reason_code": "cancelled"})
    pushed = lockmod.release(rt, comp, ctx.state, f"cancel ({reason[:60]})")
    unbind_run(rt, run_id)
    if not pushed:
        raise TslError("E-GIT-01", op="push", detail="cancel recorded locally, not pushed")
    return {"run_id": run_id, "status": "COMPLETED", "end_reason": "cancelled"}


def repin(rt: Runtime, comp: Companion, run_id: str) -> dict[str, Any]:
    ctx = RunCtx(rt, comp, run_id)
    if ctx.state["status"] == "COMPLETED":
        raise TslError(
            "E-RUN-05",
            status="COMPLETED",
            command="state repin",
            needed="an open run",
            hint="nothing to repin",
        )
    changes: dict[str, list[str]] = {}
    for name, ver in ctx.state["pinned"]["skills"].items():
        sk = ctx.installed.get(name)
        if sk and sk.version != ver:
            changes[name] = [ver, sk.version]
    majors = {n for n, (a, b) in changes.items() if _major(a) != _major(b)}

    def apply(st: dict[str, Any]) -> None:
        for n, (_, b) in changes.items():
            st["pinned"]["skills"][n] = b
        for s in st["steps"]:
            if s["kind"] != "skill" or not s["attempts"]:
                continue
            used = str(s["attempts"][-1]["skill"]).split("@")[0]
            if used in majors and s["status"] in ("DONE", "ACCEPTED"):
                s["status"] = "STALE"

    ctx.state = ctx.store.update(apply)
    return {"run_id": run_id, "repinned": changes, "stale_by_major": sorted(majors)}


def repair(rt: Runtime, comp: Companion, run_id: str) -> dict[str, Any]:
    """Rebuild state.json from the snapshot, the signed records and approvals.md (SDD-02 §11.3)."""
    from tsl.core.jsonio import read_yaml

    snap_p = comp.path(snapshot_path(run_id))
    if not snap_p.is_file():
        raise TslError("E-RUN-04", run_id=run_id)
    snap = read_yaml(snap_p)
    old = read_state_raw(comp, run_id) or {}
    lk = None
    lock_ticket = None
    for p in (
        sorted(comp.path("runs/active").glob("*.lock")) if comp.path("runs/active").is_dir() else []
    ):
        d = read_json(p)
        if d.get("run_id") == run_id:
            lk = d
            lock_ticket = p.name.split("__", 1)[0]
    ticket = old.get("ticket")
    if not ticket:
        hits = sorted(comp.root.glob(f"artifacts/*/{run_id}"))
        ticket = hits[0].parent.name if hits else (lock_ticket if lk else None)
    if not ticket or (not lk and not old):
        raise TslError("E-RUN-04", run_id=run_id)
    steps = []
    for s in snap["steps"]:
        sid, kind = wfmod.step_id(s), wfmod.step_kind(s)
        entry: dict[str, Any] = {"id": sid, "kind": kind, "status": "PENDING", "attempts": []}
        if kind == "skill":
            entry["budget_used"] = {"checks": 0, "review": 0, "verifier": 0, "rework": 0}
            recs = sorted(
                comp.root.glob(
                    f"artifacts/{ticket}/{run_id}/history/{sid}/a*/{sid}.verification.json"
                )
            )
            cur = comp.path(f"artifacts/{ticket}/{run_id}/{sid}.verification.json")
            if cur.is_file():
                recs.append(cur)
            for rp in recs:
                r = read_json(rp)
                entry["attempts"].append(
                    {
                        "n": int(r["attempt"]),
                        "cause": "first" if r["attempt"] == 1 else "retry_checks",
                        "skill": r["skill"],
                        "decided_at": r["decided_at"],
                        "outcome": r["outcome"],
                        "band": r["band"],
                        "artifact": r["artifact_path"]
                        if rp == cur
                        else comp.rel(rp)[: -len(".verification.json")] + ".md",
                        "artifact_sha256": r["artifact_sha256"],
                        "record": comp.rel(rp),
                        "inputs": [],
                        "feedback": None,
                        "answers_sha256": None,
                    }
                )
            if entry["attempts"]:
                out = entry["attempts"][-1]["outcome"]
                entry["status"] = {
                    "PASS": "DONE",
                    "PASS-WITH-FINDINGS": "DONE",
                    "RETRY": "IN_PROGRESS",
                    "NEEDS-INPUT": "WAITING_INPUT",
                    "ESCALATE": "WAITING_APPROVAL",
                    "ABORT": "FAILED",
                }[out]
        steps.append(entry)
    state = dict(old) if old else {}
    state.update(
        {
            "schema": "run-state.v1",
            "run_id": run_id,
            "rev": int(old.get("rev", 0)) + 1,
            "workflow": f"{snap['id']}@{snap['version']}",
            "ticket": ticket,
            "system": old.get("system", comp.config.system.code),
            "owner": old.get("owner") or (lk or {}).get("key_id"),
            "steps": steps,
            "cursor": None,
            "updated_at": iso(rt.clock()),
        }
    )
    state.setdefault("status", "RUNNING")
    state.setdefault("end_reason", None)
    state.setdefault(
        "pinned",
        {
            "plugin": rt.tsl_version,
            "tsl": rt.tsl_version,
            "skills": {
                wfmod.skill_name(s): str(s["skill"]).split("@")[1]
                for s in snap["steps"]
                if wfmod.step_kind(s) == "skill"
            },
        },
    )
    state.setdefault("pack", {"fresh": False})
    state.setdefault("gates", [])
    state.setdefault("prs", [])
    state.setdefault(
        "questions", {"round": 0, "open_blocking": 0, "open_non_blocking": 0, "answered_sha256": {}}
    )
    state.setdefault("created_at", iso(rt.clock()))
    write_new(rt, comp, state)
    return {"run_id": run_id, "steps": len(steps), "rebuilt_from": "snapshot, records"}
