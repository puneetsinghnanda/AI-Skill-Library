"""tsl verify <artifact> and tsl verify --inputs (SDD-03 §3, §4; SDD-04 §6.6; SDD-01 §3.3)."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from tsl.core.clock import iso
from tsl.core.errors import TslError
from tsl.core.hashing import sha256_bytes
from tsl.core.jsonio import read_json, read_yaml, write_json
from tsl.core.paths import ARTIFACT_RE, sibling, tool_log_path
from tsl.core.repo import Companion
from tsl.core.runtime import Runtime
from tsl.gitops.git import Git, GitError, worktree_tree
from tsl.harness import artifact as artmod
from tsl.harness import injection
from tsl.harness.gates import ABORT_CODES, CheckInput, CheckRun, GateResult, run_all
from tsl.harness.verifier import StepResult, VerifierUnavailable, log_tail
from tsl.identity.keys import public_key
from tsl.orchestrator.run import RunCtx
from tsl.state.session import compile_policy
from tsl.state.store import find_step, latest


def to_rel(comp: Companion, artifact: str) -> str:
    p = Path(artifact)
    if p.is_absolute():
        try:
            return p.resolve().relative_to(comp.root).as_posix()
        except ValueError:
            raise TslError(
                "E-USE-01", detail="artifact is outside the companion repo", cmd="verify"
            ) from None
    cand = (Path.cwd() / p).resolve()
    if cand.exists():
        try:
            return cand.relative_to(comp.root).as_posix()
        except ValueError:
            pass
    return p.as_posix()


def _attempt_for(ctx: RunCtx, step: str, ci: bool) -> dict[str, Any]:
    st = ctx.step(step)
    cur = ctx.state.get("cursor")
    if not ci and (not cur or cur["step"] != step):
        raise TslError("E-RUN-09", step=step, run_id=ctx.run_id)
    a = latest(st)
    if a is None:
        raise TslError("E-RUN-09", step=step, run_id=ctx.run_id)
    return a


def product_changes(ctx: RunCtx) -> list[dict[str, Any]] | None:
    branches = ctx.state.get("branch") or {}
    out: list[dict[str, Any]] = []
    for repo, b in sorted(branches.items()):
        clone = ctx.comp.product_clone(repo)
        if clone is None:
            continue
        g = Git(clone)
        # A passed code step leaves a checkpoint commit (head_sha); the next code step's change
        # is measured from there, so unit-test is not charged with implement's files.
        since = b.get("head_sha") or b["base_sha"]
        try:
            tree = worktree_tree(clone)
            added, deleted, files = g.numstat(since, tree)
            diff = g.diff_bytes(since, tree)
        except GitError as exc:
            raise exc.tsl() from None
        out.append(
            {
                "repo": repo,
                "base_sha": since,
                "tree_sha": tree,
                "diff_sha256": sha256_bytes(diff),
                "lines_added": added,
                "lines_deleted": deleted,
                "files": sorted(files),
            }
        )
    return out or None


def find_profile(rt: Runtime, profile: str) -> dict[str, Any] | None:
    root = rt.plugin_root()
    for base in (root / "verifiers", root.parent.parent / "verifiers"):
        p = base / profile / "profile.yaml"
        if p.is_file():
            from tsl.schemas.registry import require_valid

            data = read_yaml(p)
            require_valid("verifier-profile.v1", data, str(p.name))
            return dict(data)
    return None


def run_h3(
    rt: Runtime, ctx: RunCtx, out: dict[str, Any]
) -> tuple[GateResult, dict[str, Any] | None]:
    g = GateResult("H3")
    verifier: dict[str, Any] | None = None
    for repo in sorted(ctx.state.get("branch") or {}):
        cfg = ctx.comp.config.repo(repo)
        clone = ctx.comp.product_clone(repo)
        if cfg is None or clone is None:
            continue
        prof = find_profile(rt, cfg.verifier_profile)
        if prof is None:
            g.status = "skip"
            g.details.append(f"no verifier profile {cfg.verifier_profile}")
            continue
        outdir = ctx.comp.path(f"runs/{ctx.run_id}/verifier/{out['step']}")
        res = rt.verifier.run(
            prof, clone, outdir, with_coverage=ctx.skill_for(out["step"]).id == "unit-test"
        )
        verifier = {
            "profile": res.profile,
            "image_digest": res.image_digest,
            "steps": [
                {
                    "name": s.name,
                    "status": s.status,
                    "exit_code": s.exit_code,
                    "duration_ms": s.duration_ms,
                    "report_sha256": s.report_sha256,
                }
                for s in res.steps
            ],
        }
        for s in res.steps:
            if s.status == "fail" and s.code:
                if s.code == "E-SEC-01":
                    out.setdefault("_h4_extra", []).append(s.detail)
                else:
                    rel_dir = f"runs/{ctx.run_id}/verifier/{out['step']}"
                    g.fail(s.code, _with_log(s, outdir, rel_dir))
    return g, verifier


def _with_log(s: StepResult, outdir: Path, rel_dir: str) -> str:
    """Failure detail plus the step log path and its last lines, so the retry can fix it."""
    if not s.log:
        return s.detail
    head = f"{s.detail}; log {rel_dir}/{s.log}"
    tail = log_tail(outdir / s.log, max(0, 480 - len(head)))
    return f"{head}: {tail}" if tail else head


def _markers(rt: Runtime) -> injection.Markers | None:
    """SC-INJ-01 phrase list from the plugin (SEC-01 §6.5). An invalid file is a config error."""
    try:
        root = rt.plugin_root()
    except TslError:
        return None
    return injection.markers_for(root)


def build_input(
    rt: Runtime,
    ctx: RunCtx,
    rel: str,
    attempt: dict[str, Any],
    changes: list[dict[str, Any]] | None,
) -> CheckInput:
    comp = ctx.comp
    art = artmod.load(comp.root, rel)
    step = str(art.step)
    skill = ctx.skill_for(step)
    cfg = comp.config
    repos = {r.name for r in cfg.product_repos} | {str(r["name"]) for r in cfg.read_only_repos}
    prior: list[str] = []
    adir = comp.path(f"artifacts/{ctx.ticket}/{ctx.run_id}")
    for p in sorted(adir.rglob("*.checks.json")) if adir.is_dir() else []:
        if p.resolve() == comp.path(sibling(rel, ".checks.json")).resolve():
            continue
        try:
            prior.append(str(read_json(p)["tool_log_sha256"]))
        except (ValueError, KeyError):
            continue
    try:
        policy = compile_policy(rt, comp, ctx.run_id, ctx.state["pinned"]["tsl"])
    except (TslError, ValueError, OSError):
        policy = None
    return CheckInput(
        root=comp.root,
        art=art,
        skill=skill,
        repos=repos,
        clones=comp.local_paths(),
        state=ctx.state,
        attempt=attempt,
        expected_inputs=ctx.resolve_inputs(step),
        tool_log=comp.path(tool_log_path(ctx.run_id)),
        tool_log_prior=prior,
        policy=policy,
        product_scopes={r.name: r.path for r in cfg.product_repos},
        read_only={str(r["name"]) for r in cfg.read_only_repos},
        product_changes=changes,
        h4_allow=frozenset(cfg.h4_allow),
        key_lookup=lambda k: public_key(rt, k, online=False),
        link_hosts=tuple(cfg.harness.get("link_hosts", [])) or rt.org.link_hosts,
        injection_markers=_markers(rt),
    )


def compute(
    rt: Runtime,
    ctx: RunCtx,
    rel: str,
    attempt: dict[str, Any],
    *,
    fast: bool,
    only: list[str] | None,
    existing: dict[str, Any] | None,
    changes: list[dict[str, Any]] | None = None,
) -> tuple[CheckRun, dict[str, Any] | None]:
    step = str(ARTIFACT_RE.match(rel).group("step"))  # type: ignore[union-attr]
    skill = ctx.skill_for(step)
    if changes is None and skill.is_code:
        changes = product_changes(ctx)
    ci = build_input(rt, ctx, rel, attempt, changes)
    h3: GateResult | None = None
    verifier: dict[str, Any] | None = None
    extra: dict[str, Any] = {"step": step}
    if skill.is_code:
        prev_h3 = next((g for g in (existing or {}).get("gates", []) if g["id"] == "H3"), None)
        if fast and (only is None or "H3" not in only):
            if (
                prev_h3
                and prev_h3.get("status") != "pending"
                and existing
                and existing.get("artifact_sha256") == ci.art.sha256
            ):
                h3 = GateResult(
                    "H3",
                    prev_h3["status"],
                    list(prev_h3.get("codes", [])),
                    [prev_h3.get("detail", "")] if prev_h3.get("detail") else [],
                )
                verifier = (existing or {}).get("verifier")
            else:
                h3 = GateResult("H3", "pending", details=["verifier not run yet"])
        else:
            try:
                h3, verifier = run_h3(rt, ctx, extra)
            except VerifierUnavailable:
                h3 = GateResult("H3", "pending", details=["docker unavailable"])
                extra["_unavailable"] = True
    run = run_all(ci, h3)
    for d in extra.get("_h4_extra", []):
        run.gates["H4"].fail("E-SEC-01", f"verifier secrets scan: {d}", "GEN-SECRET-01")
    if extra.get("_unavailable"):
        run.gates["H3"].details.append("E-H3-07")
    return run, verifier


def record(
    ctx: RunCtx,
    rel: str,
    attempt: dict[str, Any],
    run: CheckRun,
    verifier: dict[str, Any] | None,
    changes: list[dict[str, Any]] | None,
    started: str,
    finished: str,
    art_sha: str,
    version: str,
) -> dict[str, Any]:
    rec = {
        "schema": "checks.v1",
        "run_id": ctx.run_id,
        "step": str(ARTIFACT_RE.match(rel).group("step")),  # type: ignore[union-attr]
        "attempt": int(attempt["n"]),
        "artifact_sha256": art_sha,
        "tool_log_sha256": run.tool_log_sha256,
        "tsl_version": version,
        "started_at": started,
        "finished_at": finished,
        "gates": [run.gates[k].record() for k in ("H1", "H2", "H3", "H4", "H5", "H6", "H7")],
        "soft": run.soft,
        "inputs": run.inputs,
        "verifier": verifier,
        "product_changes": changes,
    }
    from tsl.schemas.registry import errors

    errs = errors("checks.v1", rec)
    if errs:
        raise TslError(
            "E-INT-01",
            f"checks record invalid: {errs[0].pointer} {errs[0].message}",
            log_id="verify",
        )
    return rec


def verify_artifact(
    rt: Runtime,
    comp: Companion,
    artifact: str,
    *,
    fast: bool = False,
    only: list[str] | None = None,
) -> dict[str, Any]:
    rel = to_rel(comp, artifact)
    m = ARTIFACT_RE.match(rel)
    if not m or not comp.path(rel).is_file():
        raise TslError("E-USE-01", detail=f"{rel} is not an artifact of a run", cmd="verify")
    ctx = RunCtx(rt, comp, m.group("run_id"))
    started = iso(rt.clock())
    with ctx.store.local_lock():
        ctx.assert_lock_held()
        attempt = _attempt_for(ctx, m.group("step"), ci=False)
        checks_rel = sibling(rel, ".checks.json")
        existing = read_json(comp.path(checks_rel)) if comp.path(checks_rel).is_file() else None
        sk = ctx.skill_for(m.group("step"))
        changes = product_changes(ctx) if sk.is_code else None
        run, verifier = compute(
            rt, ctx, rel, attempt, fast=fast, only=only, existing=existing, changes=changes
        )
        art_sha = artmod.load(comp.root, rel).sha256
        rec = record(
            ctx,
            rel,
            attempt,
            run,
            verifier,
            changes,
            started,
            iso(rt.clock()),
            art_sha,
            rt.tsl_version,
        )
        write_json(comp.path(checks_rel), rec)
    hard_failed = [g["id"] for g in rec["gates"] if g["status"] == "fail"]
    codes = [c for g in rec["gates"] for c in g.get("codes", [])]
    data = {
        "artifact": rel,
        "artifact_sha256": art_sha,
        "checks_path": checks_rel,
        "attempt": rec["attempt"],
        "gates": [
            {
                "id": g["id"],
                "pass": g["pass"],
                "status": g["status"],
                "codes": g["codes"],
                "detail": g["detail"],
            }
            for g in rec["gates"]
        ],
        "soft": rec["soft"],
        "injection": [h.record() for h in run.injection_hits],
        "hard_failed": hard_failed,
        "duration_ms": 0,
    }
    if "E-H3-07" in run.gates["H3"].details:
        raise TslError("E-H3-07", data=data)
    abort = [c for c in codes if c in ABORT_CODES]
    if abort:
        h7 = next((g for g in rec["gates"] if g["id"] == "H7"), None)
        m_tool = re.search(r"tool (\S+)", str((h7 or {}).get("detail", "")))
        raise TslError(
            abort[0], data=data, path=rel, tool=m_tool.group(1) if m_tool else "?", skill=sk.id
        )
    if hard_failed:
        first = next(g for g in rec["gates"] if g["status"] == "fail")
        lim = ctx.retry_limits(m.group("step"))
        used = ctx.step(m.group("step")).get("budget_used") or {}
        kind = "verifier" if first["id"] == "H3" else "checks"
        raise TslError(
            "E-CHK-01",
            data=data,
            gate=first["id"],
            detail=first["detail"][:200],
            n=int(used.get(kind, 0)) + 1,
            max=lim[kind],
        )
    return data


def h3_status(rt: Runtime, comp: Companion, artifact: str) -> dict[str, Any]:
    rel = to_rel(comp, artifact)
    p = comp.path(sibling(rel, ".checks.json"))
    if not p.is_file():
        raise TslError("E-REV-01")
    rec = read_json(p)
    h3 = next(g for g in rec["gates"] if g["id"] == "H3")
    return {"artifact": rel, "h3": h3["status"], "detail": h3.get("detail", "")}


def detach_h3(rt: Runtime, comp: Companion, artifact: str) -> dict[str, Any]:
    rel = to_rel(comp, artifact)
    m = ARTIFACT_RE.match(rel)
    if not m:
        raise TslError("E-USE-01", detail="not an artifact", cmd="verify")
    status = comp.path(f"runs/{m.group('run_id')}/verifier/{m.group('step')}.status.json")
    write_json(status, {"state": "running", "started_at": iso(rt.clock())})
    subprocess.Popen(
        [sys.executable, "-m", "tsl", "verify", rel, "--gates", "H3", "--repo", str(comp.root)],
        cwd=str(comp.root),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    return {"artifact": rel, "detached": True, "status_path": comp.rel(status)}


# ------------------------------------------------------------------------- verify --inputs
def verify_inputs(
    rt: Runtime, comp: Companion, run_id: str | None, step: str | None, artifact: str | None
) -> dict[str, Any]:
    from tsl.core.paths import feedback_path
    from tsl.state.session import read_index

    if artifact:
        rel = to_rel(comp, artifact)
        m = ARTIFACT_RE.match(rel)
        if not m:
            raise TslError("E-USE-01", detail=f"{rel} is not an artifact path", cmd="verify")
        run_id, step = m.group("run_id"), m.group("step")
    if run_id is None:
        sid = rt.session_id()
        idx = read_index(rt.home.session(sid)) if sid else None
        if not idx:
            raise TslError("E-RUN-04", run_id="(no run bound to this session)")
        run_id = str(idx["run_id"])
    ctx = RunCtx(rt, comp, run_id)
    ctx.assert_lock_held()
    cur = ctx.state.get("cursor")
    if step is None:
        if not cur:
            raise TslError("E-RUN-09", step="(none)", run_id=run_id)
        step = str(cur["step"])
    if not cur or cur["step"] != step:
        raise TslError("E-RUN-09", step=step, run_id=run_id)
    attempt = latest(ctx.step(step))
    if attempt is None:
        raise TslError("E-RUN-09", step=step, run_id=run_id)
    # The skill calls this first, so it marks the launch. H5 and H7 read the tool log from here,
    # which leaves out calls a session made at this step before the skill ran.
    launched, n = iso(rt.clock()), attempt["n"]

    def mark(st: dict[str, Any]) -> None:
        a = latest(find_step(st, step))
        if a is not None and a["n"] == n:
            a["skill_started_at"] = launched

    with ctx.store.local_lock():
        ctx.state = ctx.store.update(mark)
    attempt = latest(ctx.step(step)) or attempt
    sk = ctx.skill_for(step)
    items = ctx.resolve_inputs(step)
    out_inputs: list[dict[str, Any]] = []
    missing: list[str] = []
    stale: list[tuple[str, str]] = []
    for i in items:
        present = bool(i["sha256"])
        is_stale = False
        if present and i.get("step"):
            final = ctx.final_sha(str(i["step"]))
            rec = comp.path(str(i["path"])[:-3] + ".verification.json")
            is_stale = final != i["sha256"] or not rec.is_file()
        if not present and i.get("required", True):
            missing.append(str(i["name"]))
        if is_stale:
            stale.append((str(i["path"]), str(i.get("step"))))
        out_inputs.append(
            {
                "name": i["name"],
                "path": i["path"],
                "schema": i["schema"],
                "sha256": i["sha256"],
                "present": present,
                "stale": is_stale,
            }
        )
    from tsl.context.freshness import pack_present

    pack = ctx.state.get("pack") or {}
    status = "fresh" if pack.get("fresh") else ("missing" if not pack_present(comp) else "stale")
    retry = None
    if attempt["n"] > 1 and attempt.get("feedback"):
        fb_path = comp.path(str(attempt["feedback"]))
        if fb_path.is_file():
            fb = read_json(fb_path)
            retry = {
                "failures": [{"gate": f["id"], "detail": f["detail"]} for f in fb["gate_failures"]],
                "findings": fb["findings"],
            }
            if fb.get("comment"):
                retry["comment"] = fb["comment"]
    envelope = {
        "schema": sk.artifact_output["schema"],
        "run_id": run_id,
        "step": step,
        "attempt": attempt["n"],
        "skill": attempt["skill"],
        "inputs": [{"path": i["path"], "sha256": i["sha256"]} for i in out_inputs if i["sha256"]],
        "pack_sha": dict(pack.get("source_sha") or {}),
    }
    if sk.is_code:
        # The skill re-runs `tsl verify --inputs` after its edits and copies code[] from here.
        changes = product_changes(ctx)
        if changes:
            envelope["code"] = [
                {
                    "repo": c["repo"],
                    "base_sha": c["base_sha"],
                    "head_sha": c["tree_sha"],
                    "diff_sha256": c["diff_sha256"],
                    "files": c["files"],
                }
                for c in changes
            ]
    data = {
        "run_id": run_id,
        "step": step,
        "attempt": attempt["n"],
        "skill": attempt["skill"],
        "artifact_path": attempt["artifact"],
        "output_schema": sk.artifact_output["schema"],
        "inputs": out_inputs,
        "context": {
            "status": status,
            "index": "context/manifest.json",
            "sections": list(sk.meta.get("context_sections", [])),
        },
        "envelope": envelope,
        "size_budget_tokens": sk.meta.get("size_budget_tokens"),
        "retry": retry,
        "feedback": attempt.get("feedback")
        or (feedback_path(run_id, step, attempt["n"] - 1) if attempt["n"] > 1 else None),
    }
    scans = _upstream_scans(comp, out_inputs)
    if scans:
        data["scans"] = scans
    if status == "missing" and ctx.requires_fresh_pack:
        raise TslError("E-CTX-01", detail="", data=data)
    if missing:
        raise TslError("E-IN-01", name=missing[0], skill=sk.id, data=data)
    if stale:
        raise TslError("E-IN-02", artifact=stale[0][0], step=stale[0][1], data=data)
    return data


def _upstream_scans(comp: Companion, inputs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """SAST and secrets reports from the H3 record of a change.v1 input (secure-code-review)."""
    out: list[dict[str, Any]] = []
    for i in inputs:
        if i.get("schema") != "change.v1":
            continue
        p = comp.path(sibling(str(i["path"]), ".checks.json"))
        if not p.is_file():
            continue
        for s in (read_json(p).get("verifier") or {}).get("steps", []):
            if s.get("name") in ("sast", "secrets") and s.get("report_sha256"):
                out.append({"kind": s["name"], "report_sha256": s["report_sha256"]})
    return out
