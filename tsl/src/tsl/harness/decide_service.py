"""tsl decide: verify citations, compute signals, band and outcome, sign the record,
update the run (SDD-03 §11-§12, SDD-02 §8-§9, SDD-04 §6.10)."""

from __future__ import annotations

from typing import Any

from tsl.approvals import approvals_md, questions_md
from tsl.core.clock import iso
from tsl.core.config import effective_bands
from tsl.core.errors import TslError
from tsl.core.hashing import sha256_file, sha256_raw
from tsl.core.jsonio import read_json, write_json
from tsl.core.paths import ARTIFACT_RE, approvals_path, feedback_path, questions_path, sibling
from tsl.core.repo import Companion
from tsl.core.runtime import Runtime
from tsl.gitops.git import Git, GitError
from tsl.harness import citations
from tsl.harness.decide import DecideInput, Decision, evaluate
from tsl.harness.verify import to_rel
from tsl.identity.keys import Signer, load_signer
from tsl.identity.signing import canonical, round4, sign_object
from tsl.orchestrator.run import RunCtx
from tsl.state import lock as lockmod
from tsl.state.session import unbind_run
from tsl.state.store import latest

ACTION = {
    "PASS": "continue",
    "PASS-WITH-FINDINGS": "continue",
    "RETRY": "retry",
    "NEEDS-INPUT": "pause_input",
    "ESCALATE": "pause_approval",
    "ABORT": "stop",
}
ASK_ROLE = {
    "product owner": "product_owner",
    "tech lead": "tech_lead",
    "SME": "sme",
    "client": "client",
}


def _s5(ctx: RunCtx) -> str:
    from tsl.context.freshness import pack_present

    pack = ctx.state.get("pack") or {}
    if pack.get("fresh"):
        return "fresh"
    if not pack_present(ctx.comp):
        return "fresh" if not ctx.requires_fresh_pack else "missing"
    return "stale"


def _stale_steps(ctx: RunCtx, step: str) -> list[str]:
    out = []
    for i in ctx.resolve_inputs(step):
        if i.get("step") and ctx.final_sha(str(i["step"])) != i.get("sha256"):
            out.append(str(i["step"]))
    return out


def _answered(ctx: RunCtx) -> set[str]:
    return set((ctx.state.get("questions") or {}).get("answered_sha256", {}).keys())


def failed_gates(comp: Companion, rel: str, attempt: int | None = None) -> list[str]:
    """Hard gates that failed in the artifact's current checks.json; [] when there is none."""
    crel = sibling(rel, ".checks.json")
    if not comp.path(crel).is_file() or not comp.path(rel).is_file():
        return []
    checks = read_json(comp.path(crel))
    if checks.get("artifact_sha256") != sha256_file(comp.path(rel)):
        return []
    if attempt is not None and int(checks.get("attempt", 0)) != attempt:
        return []
    return [str(g["id"]) for g in checks.get("gates", []) if g.get("status") == "fail"]


def _record_skipped_review(rt: Runtime, comp: Companion, rel: str) -> None:
    """A failing gate makes the review moot: record it as not done so decide can retry or abort."""
    if comp.path(sibling(rel, ".review.json")).is_file():
        return
    failed = failed_gates(comp, rel)
    if failed:
        from tsl.review.service import record

        record(rt, comp, rel, None, f"not reviewed: gate {', '.join(failed)} failed")


def decide(
    rt: Runtime, comp: Companion, artifact: str
) -> tuple[dict[str, Any], Decision, list[dict[str, str]]]:
    rel = to_rel(comp, artifact)
    m = ARTIFACT_RE.match(rel)
    if not m or not comp.path(rel).is_file():
        raise TslError("E-USE-01", detail=f"{rel} is not an artifact of a run", cmd="decide")
    _record_skipped_review(rt, comp, rel)
    ctx = RunCtx(rt, comp, m.group("run_id"))
    step = m.group("step")
    warnings: list[dict[str, str]] = []
    with ctx.store.local_lock():
        ctx.assert_lock_held()
        ctx.assert_session()
        if ctx.state["status"] != "RUNNING":
            raise TslError(
                "E-RUN-05",
                status=ctx.state["status"],
                command="decide",
                needed="RUNNING",
                hint=f"tsl state show {ctx.run_id}",
            )
        cur = ctx.state.get("cursor")
        if not cur or cur["step"] != step:
            raise TslError("E-RUN-09", step=step, run_id=ctx.run_id)
        attempt = latest(ctx.step(step))
        if attempt is None:
            raise TslError("E-RUN-09", step=step, run_id=ctx.run_id)
        vrel = sibling(rel, ".verification.json")
        crel, rrel = sibling(rel, ".checks.json"), sibling(rel, ".review.json")
        if not comp.path(crel).is_file() or not comp.path(rrel).is_file():
            raise TslError(
                "E-RUN-05",
                status="missing records",
                command="decide",
                needed="checks.json and review.json",
                hint=f"tsl verify {rel}, then the review skill",
            )
        checks = read_json(comp.path(crel))
        review = read_json(comp.path(rrel))
        pending = [g["id"] for g in checks["gates"] if g.get("status") == "pending"]
        if pending:
            raise TslError("E-DEC-01", gate=pending[0])
        art_sha = sha256_file(comp.path(rel))
        if (
            checks.get("artifact_sha256") != art_sha
            or int(checks.get("attempt", 0)) != attempt["n"]
        ):
            raise TslError("E-DEC-02")
        if review.get("artifact_sha256") != art_sha:
            raise TslError("E-DEC-02")
        signer = load_signer(rt)  # no usable key: exit 10, nothing written (SDD-07 §6.3)
        sk = ctx.skill_for(step)
        cfg = comp.config
        thresholds = effective_bands(
            sk.harness.get("bands"), (cfg.harness.get("bands") or {}).get(sk.id)
        )
        prev_fb = None
        if attempt.get("feedback") and comp.path(str(attempt["feedback"])).is_file():
            prev_fb = read_json(comp.path(str(attempt["feedback"])))
        pack = ctx.state.get("pack") or {}
        shas = dict(pack.get("source_sha") or {})
        shas.update(
            {r: c["tree_sha"] for c in checks.get("product_changes") or [] for r in [c["repo"]]}
        )
        from tsl.core.frontmatter import split

        front = split(comp.path(rel).read_text(encoding="utf-8")).front
        shas.update({k: v for k, v in (front.get("pack_sha") or {}).items()})
        repos = {r.name for r in cfg.product_repos} | {str(r["name"]) for r in cfg.read_only_repos}
        gen_mm = comp.path("context/generated/module-map.json")
        inp = DecideInput(
            checks=checks,
            review=review,
            front=front,
            rubric=sk.rubric,
            limits=ctx.retry_limits(step),
            used=dict(ctx.step(step).get("budget_used") or {}),
            thresholds=thresholds,
            s5=_s5(ctx),
            requires_fresh_pack=ctx.requires_fresh_pack,
            is_code=sk.is_code,
            change_limits=cfg.limits(),
            resolver=citations.Resolver(comp.root, comp.local_paths(), shas),
            repos=repos,
            answered=_answered(ctx),
            prev_feedback=prev_fb,
            stale_steps=_stale_steps(ctx, step),
            generated=read_json(gen_mm) if gen_mm.is_file() else None,
        )
        d = evaluate(inp)
        record = _record(rt, ctx, rel, attempt, checks, review, d, thresholds, signer, sk.ref)
        write_json(comp.path(vrel), record)
        vsha = sha256_file(comp.path(vrel))
        data = _apply(rt, ctx, rel, step, attempt, d, vrel, vsha, record, warnings)
    data.update({"verification_path": vrel, "key_id": signer.key_id})
    if "pack-stale" in d.caps:
        warnings.append(
            {"code": "E-CTX-02", "message": "Context pack is stale. Band capped at Medium."}
        )
    if d.outcome == "RETRY" and d.budget_kind is None and d.rerun_step:
        warnings.append({"code": "E-IN-02", "message": f"upstream step {d.rerun_step} is stale"})
    return data, d, warnings


def _record(
    rt: Runtime,
    ctx: RunCtx,
    rel: str,
    attempt: dict[str, Any],
    checks: dict[str, Any],
    review: dict[str, Any],
    d: Decision,
    thresholds: dict[str, Any],
    signer: Signer,
    skill_ref: str,
) -> dict[str, Any]:
    comp = ctx.comp
    prev_sha = None
    if attempt["n"] > 1:
        prev = ctx.step(str(checks["step"]))["attempts"]
        if (
            len(prev) >= 2
            and prev[-2].get("record")
            and comp.path(str(prev[-2]["record"])).is_file()
        ):
            prev_sha = sha256_file(comp.path(str(prev[-2]["record"])))
    signals = dict(d.signals)
    signals["S1"], signals["S2"] = round4(signals["S1"]), round4(signals["S2"])
    if signals["S3"] is not None:
        signals["S3"] = round4(float(signals["S3"]))
    pack = ctx.state.get("pack") or {}
    rec: dict[str, Any] = {
        "schema": "verification.v1",
        "run_id": ctx.run_id,
        "step": checks["step"],
        "attempt": int(attempt["n"]),
        "skill": skill_ref,
        "artifact_path": rel,
        "artifact_sha256": checks["artifact_sha256"],
        "checks_sha256": sha256_file(comp.path(sibling(rel, ".checks.json"))),
        "review_sha256": sha256_file(comp.path(sibling(rel, ".review.json"))),
        "inputs": list(checks.get("inputs") or []),
        "product_changes": [
            {k: c[k] for k in ("repo", "base_sha", "tree_sha", "diff_sha256")}
            for c in checks.get("product_changes") or []
        ]
        or None,
        "findings_kept": [
            {k: f[k] for k in ("id", "severity", "raised_from") if k in f} for f in d.kept
        ],
        "findings_dropped": [{"id": x["id"], "reason": x["reason"]} for x in d.dropped],
        "claims": {"total": d.claims_total, "verified": d.claims_verified},
        "signals": signals,
        "band": d.band,
        "outcome": d.outcome,
        "gate_failures": d.gate_failures,
        "caps": d.caps,
        "thresholds_sha256": sha256_raw(canonical(_round_all(thresholds))),
        "pack": {
            "signed_at": pack.get("signed_at"),
            "source_sha": dict(pack.get("source_sha") or {}),
            "manifest_sha256": pack.get("manifest_sha256"),
        },
        "prev_attempt_sha256": prev_sha,
        "decided_by": f"tsl@{rt.tsl_version}",
        "decided_at": iso(rt.clock()),
    }
    passed_on_defaults = d.outcome in ("PASS", "PASS-WITH-FINDINGS") and any(
        not q["blocking"] for q in d.questions
    )
    if passed_on_defaults or (attempt.get("cause") == "input_answered" and _defaults_accepted(ctx)):
        rec["accepted_default"] = True
    signed = sign_object(rec, signer.key_id, signer.private)
    from tsl.schemas.registry import errors

    errs = errors("verification.v1", signed)
    if errs:
        raise TslError(
            "E-INT-01",
            f"verification record invalid: {errs[0].pointer} {errs[0].message}",
            log_id="decide",
        )
    return signed


def _round_all(x: Any) -> Any:
    if isinstance(x, dict):
        return {k: _round_all(v) for k, v in x.items()}
    if isinstance(x, float):
        return round4(x)
    return x


def _defaults_accepted(ctx: RunCtx) -> bool:
    p = ctx.comp.path(questions_path(ctx.run_id))
    if not p.is_file():
        return False
    try:
        obj = questions_md.parse(p.read_text(encoding="utf-8"))
    except TslError:
        return False
    return any(not q["blocking"] and not q.get("answer") for q in obj.get("questions", []))


def _apply(
    rt: Runtime,
    ctx: RunCtx,
    rel: str,
    step: str,
    attempt: dict[str, Any],
    d: Decision,
    vrel: str,
    vsha: str,
    record: dict[str, Any],
    warnings: list[dict[str, str]],
) -> dict[str, Any]:
    comp = ctx.comp
    outcome = d.outcome
    fb_rel: str | None = None
    new_questions: list[dict[str, Any]] = []
    gate_id: str | None = None
    limits = ctx.retry_limits(step)
    if outcome == "RETRY":
        fb_rel = feedback_path(ctx.run_id, step, attempt["n"])
        checks = read_json(comp.path(sibling(rel, ".checks.json")))
        fails = [
            {"id": g["id"], "detail": (g.get("detail") or "")[:500]}
            for g in checks["gates"]
            if g.get("status") == "fail"
        ]
        verified = [
            {
                "id": f["id"],
                "severity": f["severity"],
                "text": f["text"][:300],
                "cites": [{"ref": c["ref"], "quote": c["quote"]} for c in f["cites"]],
            }
            for f in d.kept
            if f["severity"] in ("major", "blocker")
        ]
        must = [f["id"] for f in fails] + [f["id"] for f in verified]
        kind = d.budget_kind or "checks"
        fb = {
            "schema": "feedback.v1",
            "run_id": ctx.run_id,
            "step": step,
            "from_attempt": attempt["n"],
            "kind": kind,
            "gate_failures": fails,
            "findings": verified,
            "dropped": [x["id"] for x in d.dropped],
            "must_resolve": list(dict.fromkeys(must)),
        }
        from tsl.schemas.registry import require_valid

        require_valid("feedback.v1", fb, fb_rel)
        write_json(comp.path(fb_rel), fb)
    if outcome == "NEEDS-INPUT" or (outcome in ("PASS", "PASS-WITH-FINDINGS") and d.questions):
        # On a pass every question is non-blocking: record the defaults the run goes on with,
        # so they show in open-questions.md, the PR and the portal (SDD-02 §9.1).
        new_questions = _write_questions(ctx, step, attempt, d)
    if outcome == "ESCALATE":
        gate_id = f"G-escalate-{step}-a{attempt['n']}"
        role = str(
            (ctx.step_def(step).get("on") or {}).get("ESCALATE", {}).get("gate_role", "tech_lead")
        )
        approvals_md.append_entry(
            comp.path(approvals_path(ctx.run_id)),
            ctx.run_id,
            gate_id,
            role,
            "escalation",
            [{"path": rel, "sha256": record["artifact_sha256"]}],
            d.escalate_reason or "band Low",
        )
    head_shas: dict[str, str] = {}
    if outcome in ("PASS", "PASS-WITH-FINDINGS") and ctx.skill_for(step).is_code:
        head_shas = _checkpoint(ctx, step, attempt)
    prev_status = ctx.state["status"]

    def apply(st: dict[str, Any]) -> None:
        s = next(x for x in st["steps"] if x["id"] == step)
        a = s["attempts"][-1]
        a.update(
            {
                "decided_at": record["decided_at"],
                "outcome": outcome,
                "band": d.band,
                "artifact": rel,
                "artifact_sha256": record["artifact_sha256"],
                "record": vrel,
            }
        )
        if record.get("accepted_default"):
            a["accepted_default"] = True
        bu = s.setdefault("budget_used", {"checks": 0, "review": 0, "verifier": 0, "rework": 0})
        if outcome == "RETRY" and d.budget_kind:
            bu[d.budget_kind] += 1
        if outcome == "RETRY":
            s["status"] = "IN_PROGRESS"
            if d.rerun_step:
                up = next((x for x in st["steps"] if x["id"] == d.rerun_step), None)
                if up and up["status"] in ("DONE", "ACCEPTED"):
                    up["status"] = "STALE"
        elif outcome in ("PASS", "PASS-WITH-FINDINGS"):
            s["status"] = "DONE"
            if new_questions:
                q = st.setdefault(
                    "questions",
                    {"round": 0, "open_blocking": 0, "open_non_blocking": 0, "answered_sha256": {}},
                )
                q["round"] = int(q["round"]) + 1
                q["open_non_blocking"] = int(q.get("open_non_blocking", 0)) + len(new_questions)
        elif outcome == "NEEDS-INPUT":
            s["status"] = "WAITING_INPUT"
            st["status"] = "PAUSED_INPUT"
            q = st.setdefault(
                "questions",
                {"round": 0, "open_blocking": 0, "open_non_blocking": 0, "answered_sha256": {}},
            )
            q["round"] = int(q["round"]) + 1
            q["open_blocking"] = sum(1 for x in new_questions if x["blocking"])
            q["open_non_blocking"] = sum(1 for x in new_questions if not x["blocking"])
        elif outcome == "ESCALATE":
            s["status"] = "WAITING_APPROVAL"
            st["status"] = "PAUSED_APPROVAL"
            st.setdefault("gates", []).append(
                {
                    "id": gate_id,
                    "kind": "escalate",
                    "step": step,
                    "status": "WAITING_APPROVAL",
                    "artifacts": [{"step": step, "sha256": record["artifact_sha256"]}],
                    "decision": None,
                    "approver_key": None,
                    "decided_at": None,
                }
            )
        elif outcome == "ABORT":
            s["status"] = "FAILED"
            st["status"], st["end_reason"] = "COMPLETED", "aborted"
        for repo, sha in head_shas.items():
            if repo in st.get("branch", {}):
                st["branch"][repo]["head_sha"] = sha
        st["cursor"] = None

    ctx.state = ctx.store.update(apply)
    # events (metadata only, Doc 5 §5.3)
    sk = ctx.skill_for(step)
    seq = sum(1 for s in ctx.state["steps"] for a in s.get("attempts", []) if a.get("decided_at"))
    fc = {k: sum(1 for f in d.kept if f["severity"] == k) for k in ("blocker", "major", "minor")}
    body: dict[str, Any] = {
        "step": step,
        "skill": sk.id,
        "skill_version": sk.version,
        "attempt": attempt["n"],
        "outcome": outcome,
        "band": d.band,
        "signals": record["signals"],
        "caps": d.caps,
        "gate_failures": d.gate_failures,
        "findings_count": fc,
        "duration_ms": 0,
        "verification_sha256": vsha,
        "seq": seq,
        "reasons": d.reasons,
        "key_id": record["key_id"],
        "decided_by": record["decided_by"],
        "cause": attempt["cause"],
        "claims": {"total": d.claims_total, "verified": d.claims_verified},
        "findings_dropped": [x["id"] for x in d.dropped],
    }
    if rt.session_id():
        body["session_id"] = rt.session_id()
    ctx.emit("step.decided", body)
    for q in new_questions:
        ev: dict[str, Any] = {
            "step": step,
            "question_id": q["id"],
            "blocking": q["blocking"],
            "ask_role": ASK_ROLE.get(q["ask"], "tech_lead"),
        }
        ctx.emit("question.created", ev)
    if outcome == "ABORT":
        code = next(c for c in d.codes if c.startswith(("E-SEC", "E-POL")))
        ctx.emit("security.abort", {"code": code, "step": step})
    if ctx.state["status"] != prev_status:
        reason = {"NEEDS-INPUT": "paused_input", "ESCALATE": "paused_approval", "ABORT": "aborted"}[
            outcome
        ]
        ev2: dict[str, Any] = {
            "from": prev_status,
            "to": ctx.state["status"],
            "reason_code": reason,
            "step": step,
        }
        if gate_id:
            ev2["gate"] = gate_id
        ctx.emit("run.status_changed", ev2)
    if outcome == "ABORT":
        if not lockmod.release(rt, comp, ctx.state, "aborted"):
            warnings.append(
                {"code": "E-GIT-01", "message": "lock release not pushed; retried later"}
            )
        unbind_run(rt, ctx.run_id)
    else:
        if outcome in ("NEEDS-INPUT", "ESCALATE"):
            unbind_run(rt, ctx.run_id)
        ctx.push_best_effort(f"tsl({ctx.run_id}): decide {step} a{attempt['n']}", warnings)
    used = ctx.step(step).get("budget_used") or {}
    kind = d.budget_kind or "checks"
    return {
        "outcome": outcome,
        "band": d.band,
        "action": ACTION[outcome],
        "attempt": attempt["n"],
        "retries_left": max(0, limits.get(kind, 0) - int(used.get(kind, 0))),
        "signals": record["signals"],
        "caps": d.caps,
        "findings_dropped": [x["id"] for x in d.dropped],
        "retry_input": fb_rel,
        "gate": gate_id,
        "rerun_step": d.rerun_step,
        "questions": [q["id"] for q in new_questions],
        "row": d.row,
    }


def _write_questions(
    ctx: RunCtx, step: str, attempt: dict[str, Any], d: Decision
) -> list[dict[str, Any]]:
    p = ctx.comp.path(questions_path(ctx.run_id))
    used: set[str] = set()
    if p.is_file():
        used = {
            q["id"] for q in questions_md.parse(p.read_text(encoding="utf-8")).get("questions", [])
        }
    nxt = 1
    out: list[dict[str, Any]] = []
    for q in d.questions:
        src = str(q["source_id"])
        qid = src if src.startswith("Q-") and len(src) >= 4 and src not in used else None
        while qid is None:
            cand = f"Q-{nxt:02d}"
            nxt += 1
            if cand not in used:
                qid = cand
        used.add(qid)
        item = {
            "id": qid,
            "blocking": bool(q["blocking"]),
            "ask": q.get("ask") or "tech lead",
            "question": str(q["question"])[:2000],
            "why": q.get("why"),
            "evidence": list(q.get("evidence") or []),
            "options": list(q.get("options") or []),
            "proposed_default": q.get("proposed_default"),
        }
        if item["ask"] not in ("product owner", "tech lead", "SME", "client"):
            item["ask"] = "tech lead"
        out.append(item)
    sk = ctx.skill_for(step)
    front = {
        "schema": "open-questions.v1",
        "run_id": ctx.run_id,
        "ticket": ctx.ticket,
        "workflow": ctx.state["workflow"],
        "step": f"{step}@{sk.version}",
        "created_at": iso(ctx.rt.clock()),
        "status": "open",
    }
    rnd = int((ctx.state.get("questions") or {}).get("round", 0)) + 1
    questions_md.append_round(p, front, ctx.ticket, step, ctx.run_id, rnd, out)
    questions_md.load(p)  # validates against open-questions.v1
    return out


def _checkpoint(ctx: RunCtx, step: str, attempt: dict[str, Any]) -> dict[str, str]:
    """PASS of a code step: local checkpoint commit in each product repo (SDD-02 §10.3)."""
    out: dict[str, str] = {}
    for repo in ctx.state.get("branch") or {}:
        clone = ctx.comp.product_clone(repo)
        if clone is None:
            continue
        g = Git(clone)
        try:
            g.run("add", "-A")
            if not g.ok("diff", "--cached", "--quiet"):
                g.run(
                    "commit",
                    "-q",
                    "-m",
                    f"tsl: {ctx.run_id} {step} a{attempt['n']}\n\nTsl-Run: {ctx.run_id}",
                )
            out[repo] = g.head()
        except GitError as exc:
            raise exc.tsl() from None
    return out
