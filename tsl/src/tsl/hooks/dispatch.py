"""tsl hook <event>: Claude Code hook JSON in, hook JSON out (SDD-05 §5, SDD-04 §6.14).

Never prints the tsl envelope. Failure rules (SDD-05 §5.4):
- pre-tool / pre-mcp: inside a run, any failure denies with E-HOOK-01 (fail closed);
  outside a run, allow.
- post-write: any failure allows and warns with systemMessage (fail open).
- session-start / session-end: never block; errors are logged.
The no-run fast paths use the standard library only (NFR-02).
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from tsl import __version__

EVENTS = ("session-start", "pre-tool", "pre-mcp", "post-write", "session-end")
HOOK_NAME = {"pre-tool": "PreToolUse", "pre-mcp": "PreToolUse", "session-start": "SessionStart"}
TOOL_KIND = {"Write": "write", "Edit": "edit", "NotebookEdit": "edit", "Bash": "bash"}


class Ctx:
    def __init__(
        self,
        event: str,
        data: dict[str, Any],
        env: Mapping[str, str],
        home: Path,
        rt_factory: Callable[[], Any],
    ) -> None:
        self.event = event
        self.data = data
        self.env = env
        self.home = home
        self._rt_factory = rt_factory
        self._rt: Any = None
        self.decision = "allow"
        self.code: str | None = None
        self.run_id: str | None = None
        self.t0 = time.monotonic()

    @property
    def rt(self) -> Any:
        if self._rt is None:
            self._rt = self._rt_factory()
        return self._rt

    @property
    def session_id(self) -> str:
        return str(self.data.get("session_id") or "")

    @property
    def tool(self) -> str:
        return str(self.data.get("tool_name") or "")

    def session_file(self) -> Path:
        import re

        safe = re.sub(r"[^A-Za-z0-9._-]", "_", self.session_id)[:128]
        return self.home / "sessions" / f"{safe}.json"


def _now() -> str:
    import datetime as dt

    return dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _finish(ctx: Ctx, out: dict[str, Any] | None) -> tuple[str, int]:
    """One hook.log line and one hook.decision event per invocation (SDD-05 §5.4)."""
    ms = int((time.monotonic() - ctx.t0) * 1000)
    line = {
        "ts": _now(),
        "event": ctx.event,
        "session_id": ctx.session_id,
        "tool_name": ctx.tool or None,
        "decision": ctx.decision,
        "code": ctx.code,
        "duration_ms": ms,
    }
    try:
        logs = ctx.home / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        with (logs / "hook.log").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(line, sort_keys=True) + "\n")
    except OSError:
        pass
    try:
        from tsl.core.clock import system_clock
        from tsl.core.ids import IdFactory
        from tsl.telemetry.outbox import Outbox

        rt = ctx._rt
        clock = rt.clock if rt is not None else system_clock
        ids = rt.ids if rt is not None else IdFactory(clock)
        body: dict[str, Any] = {"hook": ctx.event, "decision": ctx.decision, "code": ctx.code}
        if ctx.session_id:
            body["session_id"] = ctx.session_id[:128]
        if ctx.event == "pre-mcp":
            body["tool_kind"] = "mcp_write" if ctx.decision == "deny" else "mcp_read"
        elif ctx.event == "pre-tool":
            body["tool_kind"] = TOOL_KIND.get(ctx.tool, "other")
        Outbox(ctx.home / "outbox.db", clock, ids).enqueue_trusted("hook.decision", body, None)
    except Exception:  # noqa: S110 - telemetry must never change a hook decision
        pass
    return (json.dumps(out) if out else ""), 0


def deny(ctx: Ctx, code: str, reason: str) -> tuple[str, int]:
    ctx.decision, ctx.code = "deny", code
    return _finish(
        ctx,
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": f"{code} {reason}"[:500],
            }
        },
    )


def allow(ctx: Ctx) -> tuple[str, int]:
    ctx.decision, ctx.code = "allow", None
    return _finish(ctx, None)


def run(
    event: str,
    stdin: str,
    env: Mapping[str, str] | None = None,
    home: Path | None = None,
    rt_factory: Callable[[], Any] | None = None,
) -> tuple[str, int]:
    env = dict(os.environ) if env is None else env
    home = home or Path.home() / ".truminds"
    if rt_factory is None:

        def rt_factory() -> Any:
            from tsl.core.runtime import get_runtime

            return get_runtime()

    try:
        data = json.loads(stdin or "{}")
        if not isinstance(data, dict):
            raise ValueError("stdin is not an object")
    except ValueError:
        data = {}
    ctx = Ctx(event, data, env, home, rt_factory)
    if event not in EVENTS:
        return "", 0
    if event == "pre-tool":
        from tsl.hooks import pre_tool

        return pre_tool.handle(ctx)
    if event == "pre-mcp":
        from tsl.hooks import pre_mcp

        return pre_mcp.handle(ctx)
    if event == "post-write":
        from tsl.hooks import post_write

        return post_write.handle(ctx)
    if event == "session-start":
        from tsl.hooks import session

        return session.start(ctx)
    from tsl.hooks import session

    return session.end(ctx)


def active_run(ctx: Ctx) -> dict[str, Any] | None:
    """Session index for this session, if it points at a run that is still RUNNING.

    A session that is no longer the run's active_session (another session resumed it) gets
    None, so its tool calls are not logged against the run's current step.
    """
    p = ctx.session_file()
    if not ctx.session_id or not p.is_file():
        return None
    idx = json.loads(p.read_text(encoding="utf-8"))
    state_p = Path(idx["companion"]) / "runs" / idx["run_id"] / "state.json"
    if not state_p.is_file():
        return None
    st = json.loads(state_p.read_text(encoding="utf-8"))
    if st.get("status") != "RUNNING":
        return None
    act = st.get("active_session")
    if act and act.get("session_id") != ctx.session_id[:128]:
        return None
    idx["_state"] = st
    ctx.run_id = idx["run_id"]
    return dict(idx)


def policy_for(ctx: Ctx, idx: dict[str, Any]) -> dict[str, Any]:
    p = ctx.session_file().with_name(ctx.session_file().name[:-5] + ".policy.json")
    if p.is_file():
        return dict(json.loads(p.read_text(encoding="utf-8")))
    from tsl.core.repo import Companion
    from tsl.state.session import compile_policy

    comp = Companion(Path(idx["companion"]))
    return compile_policy(ctx.rt, comp, idx["run_id"], idx["_state"]["pinned"]["tsl"])


def log_tool(
    idx: dict[str, Any],
    ctx: Ctx,
    target: str,
    decision: str,
    code: str | None,
    read_only: bool | None = None,
) -> None:
    st = idx["_state"]
    cur = st.get("cursor") or {}
    line = {
        "ts": _now(),
        "session_id": ctx.session_id[:128] or "unknown",
        "step": cur.get("step") or "run",
        "attempt": int(cur.get("attempt") or 1),
        "tool": ctx.tool,
        "target": target[:1024],
        "decision": decision,
        "code": code,
    }
    if read_only is not None:
        line["read_only"] = read_only
    p = Path(idx["companion"]) / "runs" / idx["run_id"] / "tool-log.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(line, sort_keys=True) + "\n")


def version_ok(pinned: str) -> bool:
    return pinned.split(".", 1)[0] == __version__.split(".", 1)[0]
