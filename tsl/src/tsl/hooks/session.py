"""session-start and session-end hooks (SDD-05 §5.3, §5.5). Never block."""

from __future__ import annotations

import json
import platform
from pathlib import Path
from typing import Any

from tsl import __version__
from tsl.core.errors import UPDATE_HINT
from tsl.hooks.dispatch import Ctx, _finish

OS = {"Darwin": "macos", "Windows": "windows", "Linux": "linux"}


def start(ctx: Ctx) -> tuple[str, int]:
    msgs: list[str] = []
    extra: list[str] = []
    try:
        env_file = ctx.env.get("CLAUDE_ENV_FILE")
        if env_file and ctx.session_id:
            with open(env_file, "a", encoding="utf-8") as fh:
                fh.write(f"export TSL_SESSION_ID={ctx.session_id}\n")
        root = ctx.env.get("CLAUDE_PLUGIN_ROOT")
        plugin_version = None
        if root and (Path(root) / ".claude-plugin" / "plugin.json").is_file():
            (ctx.home / "cache").mkdir(parents=True, exist_ok=True)
            (ctx.home / "cache" / "plugin-root.txt").write_text(root, encoding="utf-8")
            plugin_version = json.loads(
                (Path(root) / ".claude-plugin" / "plugin.json").read_text()
            )["version"]
            if plugin_version != __version__:
                msgs.append(
                    f"E-VER-01 tsl {__version__} does not match plugin {plugin_version}: "
                    + UPDATE_HINT
                )
        rt = ctx.rt
        logged_in = True
        try:
            rt.token()
        except Exception:
            logged_in = False
            msgs.append("E-AUTH-01 Not logged in to Truminds. Run: tsl login")
        if logged_in:
            try:
                from tsl.telemetry.emit import flush

                flush(rt, max_seconds=1.5)
            except Exception:  # noqa: S110 - events stay queued (R-04)
                pass
        extra += _reminders(ctx)
        _prefetch_approval_keys(ctx)
        dev = rt.device_id()
        stats = rt.outbox().stats()
        if dev and ctx.session_id:
            body: dict[str, Any] = {
                "session_id": ctx.session_id[:128],
                "device_id": dev,
                "plugin_version": plugin_version or __version__,
                "tsl_version": __version__,
                "os": OS.get(platform.system(), "linux"),
                "outbox_depth": stats["pending"],
                "outbox_oldest_at": stats["oldest_pending_at"],
            }
            rt.outbox().enqueue("session.started", body)
    except Exception as exc:  # warn, never block
        msgs.append(f"tsl session check failed ({type(exc).__name__}). Run tsl doctor.")
    out: dict[str, Any] = {}
    if extra:
        out["hookSpecificOutput"] = {
            "hookEventName": "SessionStart",
            "additionalContext": " ".join(extra),
        }
    if msgs:
        out["systemMessage"] = " ".join(msgs)
    return _finish(ctx, out or None)


def _reminders(ctx: Ctx) -> list[str]:
    cwd = Path(str(ctx.data.get("cwd") or "."))
    root = next((p for p in (cwd, *cwd.parents) if (p / "tsl.yaml").is_file()), None)
    if root is None or not (root / "runs").is_dir():
        return []
    me_p = ctx.home / "cache" / "me.json"
    me = json.loads(me_p.read_text(encoding="utf-8")) if me_p.is_file() else {}
    out = []
    for st_p in sorted((root / "runs").glob("run_*/state.json")):
        st = json.loads(st_p.read_text(encoding="utf-8"))
        if st.get("status") != "COMPLETED" and st.get("owner_pseudonym") == me.get("pseudonym"):
            out.append(
                f"Unfinished run {st['run_id']} ({st['ticket']} / {st['workflow']}, "
                f"{st['status']}): "
                f"/truminds:resume {st['run_id']}"
            )
    return out


def _prefetch_approval_keys(ctx: Ctx) -> None:
    """Cache signer keys of approval blocks so pre-mcp can verify offline (SDD-07 §7.1)."""
    cwd = Path(str(ctx.data.get("cwd") or "."))
    root = next((p for p in (cwd, *cwd.parents) if (p / "tsl.yaml").is_file()), None)
    if root is None:
        return
    from tsl.approvals import approvals_md
    from tsl.identity.keys import public_key

    for ap in sorted((root / "runs").glob("run_*/approvals.md")):
        try:
            obj = approvals_md.parse(ap.read_text(encoding="utf-8"))
        except Exception:  # noqa: S112 - a broken file is reported by tsl state commands
            continue
        for e in obj.get("entries", []):
            sig = e.get("signature") or {}
            if sig.get("key_id"):
                public_key(ctx.rt, str(sig["key_id"]), online=True)


def end(ctx: Ctx) -> tuple[str, int]:
    try:
        rt = ctx.rt
        active = False
        p = ctx.session_file()
        if ctx.session_id and p.is_file():
            idx = json.loads(p.read_text(encoding="utf-8"))
            from tsl.core.repo import Companion
            from tsl.state.store import RunStore

            comp = Companion(Path(idx["companion"]))
            store = RunStore(rt, comp, idx["run_id"])
            if store.exists():
                store.update(lambda st: None)  # rev+1 and heartbeat_at
                active = True
                ctx.run_id = idx["run_id"]
                try:
                    st = store.load()
                    comp.git.commit(
                        f"tsl({idx['run_id']}): heartbeat",
                        [f"runs/{idx['run_id']}"],
                        trailer=f"Tsl-Run: {idx['run_id']}",
                    )
                    comp.git.push(comp.config.companion_branch)
                    del st
                except Exception:  # noqa: S110 - silent; retried next time (SDD-04 §6.20)
                    pass
        dev = rt.device_id()
        stats = rt.outbox().stats()
        if dev and ctx.session_id:
            rt.outbox().enqueue(
                "session.ended",
                {
                    "session_id": ctx.session_id[:128],
                    "device_id": dev,
                    "outbox_depth": stats["pending"],
                    "outbox_oldest_at": stats["oldest_pending_at"],
                    "active_run": active,
                },
            )
        try:
            from tsl.telemetry.emit import flush

            flush(rt, max_seconds=1.5)
        except Exception:  # noqa: S110 - events stay queued
            pass
    except Exception:  # noqa: S110 - never block session end
        pass
    return _finish(ctx, None)
