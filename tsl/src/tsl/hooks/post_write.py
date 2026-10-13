"""post-write: run the fast checks on an artifact and feed failures back (SDD-05 §5.3)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tsl.hooks.dispatch import Ctx, _finish


def handle(ctx: Ctx) -> tuple[str, int]:
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
            return _finish(ctx, None)
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


def _block(ctx: Ctx, comp: Any, rel: str, step: str, exc: Any) -> tuple[str, int]:
    from tsl.orchestrator.run import RunCtx

    gates = [g for g in (exc.data or {}).get("gates", []) if g.get("status") == "fail"]
    parts = [f"{g['id']} failed: {g['detail']}" for g in gates][:3]
    kind = "verifier" if any(g["id"] == "H3" for g in gates) else "checks"
    extra = ""
    if exc.code == "E-CHK-01":
        ctx_run = RunCtx(ctx.rt, comp, ctx.run_id or "")
        used: dict[str, int] = {}

        def bump(st: dict[str, Any]) -> None:
            s = next(x for x in st["steps"] if x["id"] == step)
            s["budget_used"][kind] += 1
            used.update(s["budget_used"])

        ctx_run.store.update(bump)
        lim = ctx_run.retry_limits(step)[kind]
        if used.get(kind, 0) >= lim:
            extra = f" Retry budget used up: run tsl decide {rel} now."
    ctx.decision, ctx.code = "feedback", exc.code
    reason = (
        f"{exc.code} "
        + ("; ".join(parts) if parts else exc.message)
        + ". Fix it and write again."
        + extra
    )
    return _finish(ctx, {"decision": "block", "reason": reason[:1000]})
