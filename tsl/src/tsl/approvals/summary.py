"""Gate summary and the list of gates waiting for a person (used by `tsl gate`)."""

from __future__ import annotations

import json
from typing import Any

from tsl.approvals import approvals_md
from tsl.approvals.service import resolve_gate, waiting_gates
from tsl.core.errors import TslError
from tsl.core.paths import approvals_path, sibling
from tsl.core.repo import Companion
from tsl.core.runtime import Runtime
from tsl.gitops.git import GitError
from tsl.identity import me as memod
from tsl.state.store import all_runs, read_state_raw


def pull(comp: Companion) -> None:
    g = comp.git
    try:
        g.fetch()
        if g.resolve(f"origin/{comp.config.companion_branch}"):
            g.rebase(f"origin/{comp.config.companion_branch}")
    except GitError as exc:
        raise exc.tsl() from None


def portal_link(rt: Runtime, run_id: str) -> str:
    return f"{str(rt.org.service_url).rstrip('/')}/runs/{run_id}"


def _file(comp: Companion, rel: str) -> str:
    """Artifact paths may name a folder; show the file inside it when there is exactly one."""
    p = comp.path(rel)
    if p.is_dir():
        files = [
            f
            for f in p.iterdir()
            if f.is_file()
            and not f.name.startswith(".")
            and ".verification" not in f.name
            and ".review" not in f.name
        ]
        if len(files) == 1:
            return f"{rel.rstrip('/')}/{files[0].name}"
    return rel


def _row(
    comp: Companion, st: dict[str, Any], gate: str, role: str, me: dict[str, Any]
) -> dict[str, Any]:
    return {
        "run_id": st["run_id"],
        "ticket": st["ticket"],
        "workflow": st["workflow"],
        "gate": gate,
        "role": role,
        "mine_to_decide": memod.has_grant(me, {role}, comp.config.system.code),
        "owner_is_me": st.get("owner_pseudonym") == me.get("pseudonym"),
        "command": f"/tsl-gate {st['run_id']}",
    }


def list_waiting(rt: Runtime, comp: Companion) -> dict[str, Any]:
    """Gates waiting for a role the current person holds (all runs)."""
    pull(comp)
    me = memod.current_me(rt)
    rows = []
    for rid in all_runs(comp):
        st = read_state_raw(comp, rid)
        if not st or st.get("status") == "COMPLETED":
            continue
        try:
            obj = approvals_md.load(comp.path(approvals_path(rid)))
        except TslError:
            continue  # one broken approvals.md must not hide every other run's gates
        for gate in waiting_gates(st, obj):
            e = approvals_md.entry(obj, gate)
            if e is None or e.get("signature"):
                continue
            row = _row(comp, st, gate, str(e["role"]), me)
            if row["mine_to_decide"]:
                rows.append(row)
    return {"waiting": rows}


def summary(rt: Runtime, comp: Companion, run_id: str, gate: str | None = None) -> dict[str, Any]:
    pull(comp)
    st = read_state_raw(comp, run_id)
    if st is None:
        raise TslError("E-RUN-04", run_id=run_id)
    obj = approvals_md.load(comp.path(approvals_path(run_id)))
    if gate is None:
        gate = resolve_gate(st, obj, run_id)
    e = approvals_md.entry(obj, gate)
    if e is None:
        raise TslError(
            "E-RUN-05",
            status=st["status"],
            command="gate",
            needed=f"gate {gate} waiting for approval",
            hint=f"tsl state show {run_id}",
        )
    me = memod.current_me(rt)
    out = _row(comp, st, gate, str(e["role"]), me)
    out["reason"] = e.get("reason")
    out["artifacts"] = [_file(comp, a["path"]) for a in e.get("artifacts", [])]
    out["portal"] = portal_link(rt, run_id)
    out["step"] = (st.get("cursor") or {}).get("step")
    out["several"] = len(waiting_gates(st, obj)) > 1
    out["self_approval_allowed"] = bool(comp.config.gates.self_approval)
    out["questions"] = st.get("questions")
    for a in e.get("artifacts", []):
        try:
            vp = comp.path(sibling(a["path"], ".verification.json"))
        except ValueError:
            continue
        if vp.is_file():
            try:
                v = json.loads(vp.read_text(encoding="utf-8"))
            except ValueError:
                continue  # a broken record only costs the quality line
            if not isinstance(v, dict):
                continue
            out["verification"] = {
                "step": v.get("step"),
                "band": v.get("band"),
                "outcome": v.get("outcome"),
                "signals": v.get("signals"),
                "findings": [
                    {"id": f.get("id"), "severity": f.get("severity")}
                    for f in v.get("findings_kept", [])
                ],
            }
            break
    return out


def render(s: dict[str, Any]) -> str:
    lines = [
        f"Gate {s['gate']} on {s['run_id']} ({s['ticket']}, {s['workflow']})",
        f"Needs role: {s['role']}",
    ]
    if s.get("reason"):
        lines.append(f"Why: {s['reason']}")
    v = s.get("verification")
    if v:
        sev: dict[str, int] = {}
        for f in v["findings"]:
            k = str(f["severity"])
            sev[k] = sev.get(k, 0) + 1
        fs = ", ".join(f"{n} {k}" for k, n in sev.items()) or "none"
        q = v["band"] or "not scored (a hard check failed)"
        lines.append(f"Quality: {q} ({v['outcome']}); findings: {fs}")
    lines += [f"Artifact: {a}" for a in s["artifacts"]]
    lines.append(f"Details: {s['portal']}")
    if not s["mine_to_decide"]:
        lines.append(f"You do not hold the {s['role']} role, so you cannot decide this gate.")
    opt = f" --gate {s['gate']}" if s.get("several") else ""
    lines.append(f"Decide: /tsl-gate {s['run_id']} approve|changes|reject|abort [comment]{opt}")
    return "\n".join(lines)
