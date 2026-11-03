"""post-write: run the fast checks on an artifact and feed failures back (SDD-05 §5.3)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tsl.hooks.dispatch import Ctx, _finish


def handle(ctx: Ctx) -> tuple[str, int]:
    if ctx.tool == "AskUserQuestion":
        from tsl.hooks import post_ask

        return post_ask.handle(ctx)
    ti = ctx.data.get("tool_input") or {}
    raw = str(ti.get("file_path") or ti.get("notebook_path") or "").replace("\\", "/")
    if "artifacts/" not in raw or not raw.endswith(".md") or "/history/" in raw:
        return _finish(ctx, None)  # fast path: not an artifact
    try:
        p = Path(raw)
        if not p.is_absolute():
            p = Path(str(ctx.data.get("cwd") or ".")) / p
        root = next((q for q in p.parents if (q / "tsl.yaml").is_file()), None)
        if root is None:
            return _finish(ctx, None)
        from tsl.core.errors import TslError
        from tsl.core.paths import ARTIFACT_RE
        from tsl.core.repo import Companion
        from tsl.harness.verify import verify_artifact

        comp = Companion(root)
        rel = p.resolve().relative_to(root.resolve()).as_posix()
        m = ARTIFACT_RE.match(rel)
        if not m:
            return _finish(ctx, None)
        ctx.run_id = m.group("run_id")
        try:
            verify_artifact(ctx.rt, comp, rel, fast=True)
            weak = _weak_claims(ctx, comp, rel)
            if not weak:
                return _finish(ctx, None)
            return _finish(
                ctx,
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PostToolUse",
                        "additionalContext": (
                            "tsl checks passed. " + weak + " Fix them now if you can: an "
                            "unverified claim lowers S1 at decide."
                        )[:4000],
                    }
                },
            )
        except TslError as exc:
            if exc.code in ("E-CHK-01", "E-SEC-01", "E-SEC-02") or exc.code.startswith("E-POL-"):
                return _block(ctx, comp, rel, m.group("step"), exc)
            if exc.code in ("E-RUN-09", "E-LOCK-02", "E-RUN-04"):
                ctx.decision, ctx.code = "feedback", exc.code
                return _finish(ctx, {"decision": "block", "reason": f"{exc.code} {exc.message}"})
            raise
    except Exception as exc:  # fail open: never lose the engineer's work
        code = getattr(exc, "code", "E-INT-01")
        ctx.decision, ctx.code = "allow", code if str(code).startswith("E-") else "E-INT-01"
        return _finish(
            ctx,
            {
                "systemMessage": f"tsl could not check {raw} ({ctx.code}); the file was "
                "kept. Run tsl doctor."
            },
        )


def _weak_claims(ctx: Ctx, comp: Any, rel: str) -> str:
    """Soft warning (B6): claims tsl decide would not count as verified. Never blocks."""
    try:
        from tsl.harness.decide_service import unverified_claims

        weak = unverified_claims(ctx.rt, comp, rel)
    except Exception:  # a warning only; decide reports the same claims
        return ""
    if not weak:
        return ""
    return (
        "Claims that will not verify: " + "; ".join(f"{w['id']}: {w['reason']}" for w in weak) + "."
    )


def _block(ctx: Ctx, comp: Any, rel: str, step: str, exc: Any) -> tuple[str, int]:
    from tsl.orchestrator.run import RunCtx
    from tsl.state.store import latest

    gates = [g for g in (exc.data or {}).get("gates", []) if g.get("status") == "fail"]
    # Every failing gate, with every detail (B5): one write can fix them all.
    parts = [
        f"{g['id']} failed: " + "; ".join(g.get("details") or [g.get("detail", "")]) for g in gates
    ]
    extra = ""
    if exc.code == "E-CHK-01":
        # Fast-check rejections count against retry.write, per attempt (B5). retry.checks is
        # left for the decide-time retries, so a write rejected here costs no decide retry.
        is_h3 = any(g["id"] == "H3" for g in gates)
        ctx_run = RunCtx(ctx.rt, comp, ctx.run_id or "")
        used: dict[str, int] = {}

        def bump(st: dict[str, Any]) -> None:
            s = next(x for x in st["steps"] if x["id"] == step)
            if is_h3:
                s["budget_used"]["verifier"] += 1
                used["n"] = int(s["budget_used"]["verifier"])
                return
            a = latest(s)
            if a is None:
                return
            a["write_rejects"] = int(a.get("write_rejects", 0)) + 1
            used["n"] = a["write_rejects"]

        ctx_run.store.update(bump)
        lims = ctx_run.retry_limits(step)
        lim = lims["verifier"] if is_h3 else lims.get("write", lims["checks"])
        if used.get("n", 0) >= lim:
            extra = f" Retry budget used up: run tsl decide {rel} now."
    ctx.decision, ctx.code = "feedback", exc.code
    weak = _weak_claims(ctx, comp, rel) if exc.code == "E-CHK-01" else ""
    reason = (
        f"{exc.code} "
        + ("; ".join(parts) if parts else exc.message)
        + ". Fix it and write again."
        + (f" {weak}" if weak else "")
        + extra
    )
    return _finish(ctx, {"decision": "block", "reason": reason[:8000]})
