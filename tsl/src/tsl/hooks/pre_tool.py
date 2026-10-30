"""pre-tool: write scope, Bash rules and the open step's tools while a run is active (SDD-05 §5.3).

While a step's skill is open (tsl verify --inputs marked it launched and tsl decide has not run),
a tool outside that skill's allowed-tools is refused before it runs, so H7 never has to fail the
step for it afterwards. The run loop's own tools (tsl commands, the review skill) stay allowed.
"""

from __future__ import annotations

import fnmatch
import json
import os
import time
from pathlib import Path
from typing import Any

from tsl.hooks.dispatch import Ctx, active_run, allow, deny, log_tool, policy_for, version_ok

BIND_WINDOW_S = 600
# Tools the run loop itself uses between the skill and tsl decide; never step work.
RUN_LOOP_TOOLS = frozenset({"Skill", "Agent", "Task", "ToolSearch", "AskUserQuestion", "TodoWrite"})
LOGGED = ("Write", "Edit", "NotebookEdit", "Bash")


def _open_step(ctx: Ctx, idx: dict[str, Any]) -> tuple[str, list[str]] | None:
    """(skill id, allowed tools) of the cursor step while its skill is open, else None."""
    st = idx["_state"]
    cur = st.get("cursor") or {}
    step = cur.get("step")
    if not step:
        return None
    s = next((x for x in st.get("steps", []) if x.get("id") == step), None)
    a = (s or {}).get("attempts") or []
    if not a or not a[-1].get("skill_started_at") or a[-1].get("decided_at"):
        return None
    from tsl.core.repo import Companion
    from tsl.orchestrator.run import RunCtx

    try:
        run = RunCtx(ctx.rt, Companion(Path(idx["companion"])), idx["run_id"])
        sk = run.skill_for(str(step))
    except Exception:
        return None  # skill not loadable: H7 still checks the step afterwards
    return sk.id, sk.allowed_tools


def _off_step(ctx: Ctx, cmd: str, open_step: tuple[str, list[str]]) -> str | None:
    """Why this call is outside the open step's tools, or None when it is allowed."""
    skill, allowed = open_step
    tool = ctx.tool
    if tool == "Bash":
        from tsl.harness.commands import bash_allowed, is_read_only

        if bash_allowed(cmd, allowed):
            return None
        if is_read_only(cmd) or cmd.strip().startswith(("sed ", "awk ", "type ")):
            return f"step {skill} reads files with Read, Grep or Glob, not shell commands"
        return f"Bash command is not in step {skill}'s tools; only tsl commands run here"
    if tool in allowed or tool in RUN_LOOP_TOOLS:
        return None
    if tool == "NotebookEdit" and "Edit" in allowed:
        return None
    if tool == "PowerShell":
        return f"step {skill} runs tsl through the Bash tool, not PowerShell"
    return f"tool {tool} is not in step {skill}'s tools ({', '.join(allowed)})"


def _try_bind(ctx: Ctx) -> dict[str, Any] | None:
    """U-06 fallback: bind a lock this user created in the last 10 minutes (SDD-04 §6.14)."""
    cwd = Path(str(ctx.data.get("cwd") or "."))
    root = None
    for p in (cwd, *cwd.parents):
        if (p / "tsl.yaml").is_file():
            root = p
            break
    if root is None or not (root / "runs" / "active").is_dir() or not ctx.session_id:
        return None
    now = time.time()
    recent = [
        p
        for p in (root / "runs" / "active").glob("*.lock")
        if now - p.stat().st_mtime < BIND_WINDOW_S
    ]
    if not recent:
        return None
    me_p = ctx.home / "cache" / "me.json"
    me = json.loads(me_p.read_text(encoding="utf-8")) if me_p.is_file() else {}
    for lp in sorted(recent):
        lk = json.loads(lp.read_text(encoding="utf-8"))
        st_p = root / "runs" / lk["run_id"] / "state.json"
        if lk.get("holder") != me.get("pseudonym") or not st_p.is_file():
            continue
        st = json.loads(st_p.read_text(encoding="utf-8"))
        if st.get("active_session") or st.get("status") != "RUNNING":
            continue
        from tsl.core.repo import Companion
        from tsl.state.session import bind, compile_policy
        from tsl.state.store import RunStore

        comp = Companion(root)
        rt = ctx.rt
        bind(
            rt,
            comp,
            ctx.session_id,
            lk["run_id"],
            f"runs/active/{lp.name}",
            compile_policy(rt, comp, lk["run_id"], st["pinned"]["tsl"]),
        )

        def setsess(s: dict[str, Any]) -> None:
            s["active_session"] = {
                "session_id": ctx.session_id[:128],
                "host_hash": "h_0000",
                "since": s["updated_at"],
            }

        RunStore(rt, comp, lk["run_id"]).update(setsess)
        return active_run(ctx)
    return None


def _abs(ctx: Ctx, path: str) -> str:
    p = Path(path)
    if not p.is_absolute():
        p = Path(str(ctx.data.get("cwd") or ".")) / p
    return os.path.normpath(str(p)).replace("\\", "/")


def _allowed(target: str, pol: dict[str, Any]) -> bool:
    if any(fnmatch.fnmatch(target, d) for d in pol.get("deny", [])):
        return False
    return any(fnmatch.fnmatch(target, a) for a in pol.get("allow", []))


def _sensitive(tok: str, base: str, glob: str) -> bool:
    """A file-name glob matches the last path part; a glob with '/' matches the path tail."""
    if "/" in glob:
        return fnmatch.fnmatch(tok, glob) or fnmatch.fnmatch(tok, "*/" + glob)
    return fnmatch.fnmatch(base, glob)


def handle(ctx: Ctx) -> tuple[str, int]:
    if ctx.tool.startswith("mcp__"):
        return allow(ctx)  # pre-mcp decides MCP tools
    idx = None
    try:
        idx = active_run(ctx)
        if idx is None and not ctx.session_file().is_file():
            idx = _try_bind(ctx)
    except Exception:
        idx = None
    if idx is None:
        return allow(ctx)  # outside a run: static rules come from managed settings
    try:
        pol = policy_for(ctx, idx)
        if not version_ok(str(pol.get("pinned_tsl", idx["_state"]["pinned"]["tsl"]))):
            log_tool(idx, ctx, ctx.tool, "deny", "E-VER-01")
            return deny(
                ctx, "E-VER-01", "tsl version does not match the run pin; install the pinned tsl"
            )
        ti = ctx.data.get("tool_input") or {}
        open_step = _open_step(ctx, idx)
        if open_step is not None:
            why = _off_step(ctx, str(ti.get("command") or ""), open_step)
            if why is not None:
                # Refused before it runs and not written to the tool log: nothing happened,
                # so H7 has nothing to fail. hook.log still records the refusal.
                return deny(ctx, "E-POL-06", f"Refused: {why}. Carry on with the step's tools")
        if ctx.tool not in LOGGED:
            return allow(ctx)
        if ctx.tool in ("Write", "Edit", "NotebookEdit"):
            raw = str(ti.get("file_path") or ti.get("notebook_path") or "")
            target = _abs(ctx, raw)
            if not raw or not _allowed(target, pol):
                log_tool(idx, ctx, target, "deny", "E-POL-01")
                return deny(ctx, "E-POL-01", f"Blocked: write outside allowed paths {target}")
            log_tool(idx, ctx, target, "allow", None)
            return allow(ctx)
        if ctx.tool == "Bash":
            cmd = str(ti.get("command") or "")
            for pat in pol.get("bash_deny", []):
                if pat in cmd:
                    log_tool(idx, ctx, cmd[:80], "deny", "E-POL-01")
                    return deny(
                        ctx,
                        "E-POL-01",
                        f"Blocked: '{pat}' is not allowed inside a run (tsl pr does pushes)",
                    )
            for tok in cmd.split():
                tok = tok.strip("'\"")
                base = tok.rsplit("/", 1)[-1]
                if any(_sensitive(tok, base, g) for g in pol.get("read_deny", [])):
                    log_tool(idx, ctx, cmd[:80], "deny", "E-POL-02")
                    return deny(ctx, "E-POL-02", f"Blocked: read of sensitive file {base}")
            from tsl.harness.commands import is_read_only, strip_cd

            log_tool(idx, ctx, strip_cd(cmd)[:80], "allow", None, read_only=is_read_only(cmd))
            return allow(ctx)
        return allow(ctx)
    except Exception:
        return deny(
            ctx,
            "E-HOOK-01",
            "Write blocked: tsl did not answer while a run is active. Run tsl doctor",
        )
