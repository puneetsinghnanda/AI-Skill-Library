"""Fast entry for `tsl hook <event>` (SDD-05 §5.2, §5.4). Standard library only until dispatch.

`bin/tsl-hook` is a builtin-only shell launcher that `exec`s `tsl hook <event>` once. Everything the old
launcher did around that call lives here, inside the one process:

- version check: `tsl` must equal the plugin version (plugin.json under TSL_PLUGIN_ROOT / CLAUDE_PLUGIN_ROOT), E-VER-01;
- time budget (8 s pre-tool / pre-mcp, 12 s session hooks, 85 s post-write; TSL_HOOK_BUDGET_S may only lower it),
  enforced by a watchdog timer, because the launcher no longer supervises tsl;
- failure rules of SDD-05 §5.4: pre-tool / pre-mcp deny with E-HOOK-01 inside a run (fail closed) and allow
  outside one; post-write allows with a systemMessage; session hooks warn (version) or ignore (crash, timeout).

"Inside a run" = a run lock exists: found through ~/.truminds/sessions/<session_id>.json, or by walking up from
the hook's cwd to the folder holding tsl.yaml (any lock in runs/active/ there keeps writes closed).
"""

from __future__ import annotations

import json
import os
import sys
import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

BUDGET_S = {"session-start": 12, "session-end": 12, "pre-tool": 8, "pre-mcp": 8, "post-write": 85}
INSTALL_HINT = (
    "update tsl and the plugin from your AI-Skill-Library clone: git pull; uv tool install --python 3.12 "
    "--reinstall --no-cache ./tsl (TSL_ORG_FILE set, see the pilot guide); claude plugin marketplace update "
    "truminds-skill-library; claude plugin update truminds@truminds-skill-library"
)
_SID_CHARS = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_.-")


def budget_for(event: str, env: Mapping[str, str]) -> int:
    budget = BUDGET_S.get(event, 8)
    raw = env.get("TSL_HOOK_BUDGET_S", "")
    if raw.isascii() and raw.isdigit() and 1 <= int(raw) < budget:
        budget = int(raw)
    return budget


def plugin_version(env: Mapping[str, str]) -> str | None:
    """None when no plugin root is known (manual `tsl hook` call); 'unknown' when plugin.json is unreadable."""
    root = env.get("TSL_PLUGIN_ROOT") or env.get("CLAUDE_PLUGIN_ROOT")
    if not root:
        return None
    try:
        with open(os.path.join(root, ".claude-plugin", "plugin.json"), encoding="utf-8") as fh:
            return str(json.load(fh)["version"]) or "unknown"
    except (OSError, ValueError, KeyError, TypeError):
        return "unknown"


def _lock_in(root: str) -> bool:
    try:
        active = os.path.join(root, "runs", "active")
        return any(n.endswith(".lock") and os.path.isfile(os.path.join(active, n)) for n in os.listdir(active))
    except OSError:
        return False


def run_active(data: Mapping[str, object], home: str) -> bool:
    """Conservative: True when tsl cannot rule out an open run for this session or companion repo."""
    sid = data.get("session_id")
    if isinstance(sid, str) and sid and not (set(sid) - _SID_CHARS):
        try:
            with open(os.path.join(home, "sessions", sid + ".json"), encoding="utf-8") as fh:
                idx = json.load(fh)
            comp, lock = idx.get("companion"), idx.get("lock")
            if comp and lock and os.path.isfile(os.path.join(comp, lock)):
                return True
        except (OSError, ValueError, AttributeError, TypeError):
            pass
    cwd = data.get("cwd")
    d = os.path.abspath(cwd if isinstance(cwd, str) and cwd and os.path.isdir(cwd) else os.getcwd())
    while True:
        if os.path.isfile(os.path.join(d, "tsl.yaml")):
            return _lock_in(d)
        parent = os.path.dirname(d)
        if parent == d:
            return False
        d = parent


def _log(home: str, event: str, decision: str, code: str, detail: str) -> None:
    try:
        import time

        logs = os.path.join(home, "logs")
        os.makedirs(logs, exist_ok=True)
        ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        with open(os.path.join(logs, "hook.log"), "a", encoding="utf-8") as fh:
            fh.write(f"{ts} tsl-hook event={event} decision={decision} code={code} detail={detail}\n")
    except OSError:
        pass


def failure_output(event: str, kind: str, detail: str, data: Mapping[str, object], home: str) -> str:
    """Hook JSON for a failure of kind version | crash | timeout (SDD-05 §5.4); '' means allow silently."""
    if event in ("pre-tool", "pre-mcp"):
        if run_active(data, home):
            _log(home, event, "deny", "E-HOOK-01", f"{kind}: {detail}")
            reason = (
                f"E-HOOK-01 Truminds run is active and the policy hook cannot run ({detail}). "
                "Writes stay blocked until this is fixed."
            )
            return json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "deny",
                        "permissionDecisionReason": reason,
                    }
                }
            )
        _log(home, event, "allow", "E-HOOK-01", f"{kind} (no active run): {detail}")
        return ""
    if event == "post-write":
        _log(home, event, "allow", "E-HOOK-01", f"{kind} (fail open): {detail}")
        return json.dumps(
            {
                "systemMessage": f"Truminds: artifact checks did not run ({detail}). "
                "Your file was kept. Fix tsl, then re-run the step's checks."
            }
        )
    if kind == "version":
        _log(home, event, "warn", "E-VER-01", f"{kind}: {detail}")
        return json.dumps({"systemMessage": f"Truminds: {detail}"})
    _log(home, event, "ignore", "E-HOOK-01", f"{kind}: {detail}")
    return ""


def _default_runner(event: str, stdin: str) -> tuple[str, int]:
    from tsl.hooks.dispatch import run

    return run(event, stdin)


def _stdout_emit(text: str) -> None:
    sys.stdout.write(text)
    sys.stdout.flush()


def guarded(
    event: str,
    stdin: str,
    env: Mapping[str, str] | None = None,
    home: object = None,
    runner: Callable[[str, str], tuple[str, int]] = _default_runner,
    emit: Callable[[str], None] = _stdout_emit,
    hard_exit: Callable[[int], None] = os._exit,
) -> int:
    """Run the hook once with version check, budget and fail rules. Returns the process exit code."""
    from tsl import __version__

    env = os.environ if env is None else env
    home = os.fspath(home) if home else os.path.join(os.path.expanduser("~"), ".truminds")  # type: ignore[call-overload]
    try:
        data = json.loads(stdin or "{}")
        if not isinstance(data, dict):
            data = {}
    except ValueError:
        data = {}

    def finish(text: str) -> None:
        if text:
            emit(text + "\n")

    pv = plugin_version(env)
    if pv is not None and pv != __version__:
        finish(
            failure_output(
                event,
                "version",
                f"tsl {__version__} does not match plugin {pv} (E-VER-01). Install tsl {pv}: {INSTALL_HINT}",
                data,
                home,
            )
        )
        return 0

    budget = budget_for(event, env)
    gate = threading.Lock()
    state = {"done": False}

    def on_timeout() -> None:
        with gate:
            if state["done"]:
                return
            state["done"] = True
            finish(failure_output(event, "timeout", f"tsl hook {event} timed out after {budget} s", data, home))
            hard_exit(0)

    timer = threading.Timer(budget, on_timeout)
    timer.daemon = True
    timer.start()
    err: str | None = None
    out, code = "", 0
    try:
        out, code = runner(event, stdin)
    except BaseException as e:  # noqa: BLE001 - any failure must go through the fail rules
        err = f"tsl hook {event} failed with {type(e).__name__}"
    timer.cancel()
    with gate:
        if state["done"]:  # the watchdog already answered
            return 0
        state["done"] = True
        if err is not None or code != 0:
            finish(failure_output(event, "crash", err or f"tsl hook {event} exited with status {code}", data, home))
        else:
            finish(out)
        return 0


def main(event: str) -> int:
    return guarded(event, sys.stdin.read())
