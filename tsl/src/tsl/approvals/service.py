"""tsl approve: sign a gate decision in approvals.md (SDD-02 §9.2, SDD-07 §6.4, SDD-04 §6.11)."""

from __future__ import annotations

from typing import Any

from tsl.approvals import approvals_md
from tsl.core.clock import iso
from tsl.core.errors import TslError
from tsl.core.hashing import sha256_file, sha256_raw
from tsl.core.paths import ARTIFACT_RE, approvals_path
from tsl.core.repo import Companion
from tsl.core.runtime import Runtime
from tsl.gitops.git import GitError
from tsl.identity import me as memod
from tsl.identity.keys import load_signer
from tsl.identity.signing import canonical, sign_object
from tsl.orchestrator.run import RunCtx
from tsl.telemetry.emit import emit

DECISIONS = ("approve", "reject", "changes", "abort")


def approve(rt: Runtime, comp: Companion, run_id: str, gate: str) -> dict[str, Any]:
    g = comp.git
    try:
        g.fetch()
        if g.resolve(f"origin/{comp.config.companion_branch}"):
            g.rebase(f"origin/{comp.config.companion_branch}")
    except GitError as exc:
        raise exc.tsl() from None
    ctx = RunCtx(rt, comp, run_id)
    path = comp.path(approvals_path(run_id))
    obj = approvals_md.load(path)
    e = approvals_md.entry(obj, gate)
    st_gate = next(
        (
            x
            for x in ctx.state.get("gates", [])
            if x["id"] == gate and x["status"] == "WAITING_APPROVAL"
        ),
        None,
    )
    external = gate.startswith("W-")
    if e is None or (
        not external and (st_gate is None or ctx.state["status"] != "PAUSED_APPROVAL")
    ):
        raise TslError(
            "E-RUN-05",
            status=ctx.state["status"],
            command="approve",
            needed=f"gate {gate} waiting for approval",
            hint=f"tsl state show {run_id}",
        )
    if e.get("signature"):
        raise TslError(
            "E-RUN-05",
            status="already signed",
            command="approve",
            needed="an unsigned gate",
            hint=f"tsl state resume {run_id}",
        )
    decision = e.get("decision")
    if decision not in DECISIONS:
        raise TslError(
            "E-RUN-05",
            status="no decision",
            command="approve",
            needed="decision approve, reject, changes or abort",
            hint=f"fill decision: under {gate} in {approvals_path(run_id)}",
        )
    me = memod.current_me(rt)
    role = str(e["role"])
    if not memod.has_grant(me, {role}, comp.config.system.code):
        raise TslError("E-AUTH-05", role=role, gate=gate)
    signer = load_signer(rt)
    self_gen = me.get("pseudonym") == ctx.state.get(
        "owner_pseudonym"
    ) or signer.key_id == ctx.state.get("owner")
    if self_gen and not comp.config.gates.self_approval:
        raise TslError("E-AUTH-06")
    arts = []
    for a in e["artifacts"]:
        p = comp.path(a["path"])
        if not p.is_file() or sha256_file(p) != a["sha256"]:
            raise TslError("E-RUN-08", detail=f"{a['path']} changed since the gate was written")
        m = ARTIFACT_RE.match(a["path"])
        step = m.group("step") if m else str(a["path"]).rsplit("/", 1)[-1].split(".")[0]
        st = next((s for s in ctx.state["steps"] if s["id"] == step), None)
        n = next(
            (
                int(x["n"])
                for x in reversed((st or {}).get("attempts", []))
                if x.get("artifact_sha256") == a["sha256"]
            ),
            1,
        )
        arts.append({"step": step, "attempt": n, "sha256": a["sha256"]})
    if decision in ("changes", "reject") and st_gate is not None:
        target = (
            st_gate.get("step")
            if st_gate["kind"] == "escalate"
            else (
                ctx.step_def(gate).get("on_changes")
                if decision == "changes"
                else ctx.step_def(gate)["on_reject"]
            )
        )
        if target and target != "abort":
            used = int((ctx.step(str(target)).get("budget_used") or {}).get("rework", 0))
            if used >= ctx.max_rework:
                raise TslError(
                    "E-RUN-05",
                    status="rework limit reached",
                    command="approve",
                    needed="approve or abort",
                    hint="change the decision to approve or abort",
                )
    kind = (
        "external_write"
        if external
        else "escalation"
        if gate.startswith("G-escalate-")
        else "workflow_gate"
    )
    block = {
        "schema": "approval-signature.v1",
        "run_id": run_id,
        "system": comp.config.system.code,
        "gate": gate,
        "kind": kind,
        "artifacts": arts,
        "action": e.get("action") if external else None,
        "decision": decision,
        "comment_sha256": approvals_md.comment_sha256(e.get("comment")),
        "role": role,
        "approver": me["pseudonym"],
        "self_approved": bool(self_gen),
        "approved_at": iso(rt.clock()),
    }
    signed = sign_object(block, signer.key_id, signer.private)
    from tsl.schemas.registry import require_valid

    require_valid("approval-signature.v1", signed, "approval block")
    approvals_md.append_signature(path, gate, signed)
    block_sha = sha256_raw(canonical(signed))
    try:
        g.commit(
            f"tsl({run_id}): approve {gate}", [approvals_path(run_id)], trailer=f"Tsl-Run: {run_id}"
        )
    except GitError as exc:
        raise exc.tsl() from None
    if decision != "abort":
        body: dict[str, Any] = {
            "gate": gate,
            "decision": decision,
            "approver_role": role,
            "signature_block_sha256": block_sha,
            "key_id": signer.key_id,
        }
        if arts:
            body["step"] = arts[0]["step"]
        emit(rt, "approval.recorded", body, run_id, enabled=comp.config.telemetry_enabled)
    if not g.sync_push(comp.config.companion_branch):
        raise TslError(
            "E-GIT-01",
            op="push",
            detail="approval signed and committed locally; push failed",
            data={"gate": gate, "decision": decision, "signature_block_sha256": block_sha},
        )
    return {
        "gate": gate,
        "decision": decision,
        "approver_role": role,
        "signature_block_sha256": block_sha,
        "run_status": ctx.state["status"],
        "self_approved": bool(self_gen),
    }
