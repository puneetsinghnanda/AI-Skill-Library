"""Fast entry for `tsl hook <event>` (SDD-05 §5.2, §5.4). Standard library only until dispatch.

`bin/tsl-hook` is a builtin-only shell launcher that runs `tsl hook-run <event>` once (and applies
the fail rule itself if tsl cannot start). Everything else the old launcher did lives here:

- version check: `tsl` must equal the plugin version (plugin.json under `--plugin-root`), E-VER-01;
- time budget (8 s pre-tool / pre-mcp, 12 s session hooks, 85 s post-write; TSL_HOOK_BUDGET_S may
  only lower it), enforced by a watchdog timer, because the launcher no longer supervises tsl;
- failure rules of SDD-05 §5.4: pre-tool / pre-mcp deny with E-HOOK-01 inside a run (fail closed)
  and allow outside one; post-write allows with a systemMessage; session hooks warn (version) or
  ignore (crash, timeout).

"Inside a run" = a run lock exists: found through ~/.truminds/sessions/<session_id>.json, or by
walking up from the hook's cwd to the folder holding tsl.yaml (any lock in runs/active/ there keeps
writes closed).
"""

from __future__ import annotations

import json
import os
import re
import sys
import threading
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

# import time of this module: the closest point to process start we can see
_T0 = time.perf_counter()

BUDGET_S = {
    "session-start": 12,
    "session-end": 12,
    "subagent-stop": 12,
    "pre-tool": 8,
    "pre-mcp": 8,
    "post-write": 85,
}
_SID_CHARS = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_.-")


def budget_for(event: str, env: Mapping[str, str]) -> int:
    budget = BUDGET_S.get(event, 8)
    raw = env.get("TSL_HOOK_BUDGET_S", "")
    if raw.isascii() and raw.isdigit() and 1 <= int(raw) < budget:
        budget = int(raw)
    return budget


def plugin_version(env: Mapping[str, str], root: str | None = None) -> str | None:
    """None when no plugin root is known (manual `tsl hook` call); 'unknown' when plugin.json is
    unreadable.

    The launcher passes the root as `--plugin-root`; TSL_PLUGIN_ROOT / CLAUDE_PLUGIN_ROOT are only
    a fallback (used by tests and manual calls).
    """
    root = root or env.get("TSL_PLUGIN_ROOT") or env.get("CLAUDE_PLUGIN_ROOT")
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
        return any(
            n.endswith(".lock") and os.path.isfile(os.path.join(active, n))
            for n in os.listdir(active)
        )
    except OSError:
        return False


def run_active(data: Mapping[str, object], home: str) -> bool:
    """Conservative: True when tsl can't rule out an open run for this session or companion."""
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


# Updating while a run is open (roadmap D4). While tsl and the plugin differ (E-VER-01) the hook
# denies every tool in a run, which used to include the commands that end the mismatch, so the
# update needed a terminal outside Claude Code. These Bash commands, and only these, still run:
# each must be the whole command (optionally after `cd <dir> &&`), with nothing chained.
_PATH = r"""(?:"[^"$`\\]+"|[^\s;&|`$()<>'"\\]+)"""
_CD = re.compile(rf"cd (?P<dir>{_PATH}) && (?P<rest>.+)")
_UPDATE_ANYWHERE = (
    re.compile(r"claude plugin marketplace update truminds-skill-library"),
    re.compile(r"claude plugin update truminds@truminds-skill-library"),
    re.compile(r"tsl(?:\.exe)? (?:--version|doctor(?: --json)?)"),
)
# These act on the folder they run in: `uv tool install ./tsl` installs whatever ./tsl is there,
# so they run only in the AI-Skill-Library clone the plugin itself is loaded from.
_UPDATE_IN_CLONE = (
    re.compile(
        rf"(?:TSL_ORG_FILE={_PATH} )?uv tool install --python 3\.12 --reinstall --no-cache"
        rf"(?: --constraints {_PATH})? \./tsl"
    ),
    re.compile(r"git pull(?: --ff-only)?"),
    re.compile(r"git checkout main"),
)


def _local_path(p: str, base: str) -> str:
    """A cd target as this OS names it: Git Bash /c/Users/... is C:/Users/... on Windows."""
    p = p.strip('"')
    m = re.fullmatch(r"/([A-Za-z])(/.*)?", p)
    if os.name == "nt" and m:
        p = f"{m.group(1)}:{m.group(2) or '/'}"
    return os.path.realpath(os.path.join(base, p))


def plugin_clone(root: str | None) -> str | None:
    """The AI-Skill-Library clone a plugin is read from (<clone>/plugins/truminds), or None when
    the plugin is not read from a clone (for example an installed copy)."""
    if not root:
        return None
    clone = os.path.realpath(os.path.join(root, os.pardir, os.pardir))
    same = os.path.realpath(os.path.join(clone, "plugins", "truminds")) == os.path.realpath(root)
    ok = same and os.path.isfile(os.path.join(clone, "tsl", "pyproject.toml"))
    return clone if ok else None


def update_hint(clone: str | None) -> str:
    """What to run, from Claude Code, to end the mismatch: exactly the commands allowed above."""
    where = f"in {clone.replace(os.sep, '/')}" if clone else "in your AI-Skill-Library clone"
    return (
        "Update from here with the Bash tool (only these commands run until the versions match): "
        f"{where}: git pull; then TSL_ORG_FILE=<your tsl-org file, no $> uv tool install "
        "--python 3.12 --reinstall --no-cache ./tsl (each as its own command, optionally after "
        "cd <clone> &&); then claude plugin marketplace update truminds-skill-library and "
        "claude plugin update truminds@truminds-skill-library; then /reload-plugins or restart "
        "Claude Code. See docs/testing/team-setup-guide.md section 7a."
    )


def update_command_allowed(data: Mapping[str, object], clone: str | None) -> bool:
    """True when this pre-tool call is one of the update commands above, run where it may run."""
    if data.get("tool_name") != "Bash":
        return False
    ti = data.get("tool_input")
    command = ti.get("command") if isinstance(ti, dict) else None
    if not isinstance(command, str) or "\n" in command or "\r" in command:
        return False
    command = " ".join(command.split())
    cwd = data.get("cwd")
    where = os.path.realpath(cwd) if isinstance(cwd, str) and cwd else os.getcwd()
    m = _CD.fullmatch(command)
    if m:
        where, command = _local_path(m.group("dir"), where), m.group("rest")
    if any(p.fullmatch(command) for p in _UPDATE_ANYWHERE):
        return True
    in_clone = clone is not None and os.path.normcase(where) == os.path.normcase(clone)
    return in_clone and any(p.fullmatch(command) for p in _UPDATE_IN_CLONE)


def _log(home: str, event: str, decision: str, code: str, detail: str) -> None:
    try:
        logs = os.path.join(home, "logs")
        os.makedirs(logs, exist_ok=True)
        ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        with open(os.path.join(logs, "hook.log"), "a", encoding="utf-8") as fh:
            fh.write(
                f"{ts} tsl-hook event={event} decision={decision} code={code} detail={detail}\n"
            )
    except OSError:
        pass


def failure_output(
    event: str, kind: str, detail: str, data: Mapping[str, object], home: str
) -> str:
    """Hook JSON for a failure of kind version | crash | timeout (SDD-05 §5.4).

    '' means allow silently.
    """
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
    stdin: str | Callable[[], str],
    env: Mapping[str, str] | None = None,
    home: object = None,
    runner: Callable[[str, str], tuple[str, int]] = _default_runner,
    emit: Callable[[str], None] = _stdout_emit,
    hard_exit: Callable[[int], None] = os._exit,
    plugin_root: str | None = None,
    started: float | None = None,
) -> int:
    """Run the hook once with version check, budget and fail rules.

    Always returns 0 (a failure is an answer). The watchdog starts first, before stdin is read or
    tsl is imported, and its budget is counted from `started` (a time.perf_counter() value), so a
    hang anywhere still ends in the fail rule. Anything that escapes (e.g. a failing import) goes
    through the same rule.
    """
    env = os.environ if env is None else env
    default_home = os.path.join(os.path.expanduser("~"), ".truminds")
    home = os.fspath(home) if home else default_home  # type: ignore[call-overload]
    budget = budget_for(event, env)
    left = budget - (time.perf_counter() - (time.perf_counter() if started is None else started))
    gate = threading.Lock()
    state = {"done": False}
    box: dict[str, str] = {"stdin": ""}

    def parse() -> dict[str, object]:
        try:
            data = json.loads(box["stdin"] or "{}")
        except ValueError:
            return {}
        return data if isinstance(data, dict) else {}

    def finish(text: str) -> None:
        if text:
            emit(text + "\n")

    def on_timeout() -> None:
        with gate:
            if state["done"]:
                return
            state["done"] = True
            finish(
                failure_output(
                    event, "timeout", f"tsl hook {event} timed out after {budget} s", parse(), home
                )
            )
            # Children (git push and its helpers) would outlive os._exit (item 11). Only when proc
            # is loaded: importing it here could wait on an import lock the stuck thread holds.
            proc = sys.modules.get("tsl.core.proc")
            if proc is not None:
                proc.kill_all()
            hard_exit(0)

    timer = threading.Timer(max(left, 0.0), on_timeout)
    timer.daemon = True
    timer.start()
    err: str | None = None
    out, code = "", 0
    try:
        box["stdin"] = stdin() if callable(stdin) else stdin
        from tsl import __version__

        pv = plugin_version(env, plugin_root)
        if pv is not None and pv != __version__:
            timer.cancel()
            with gate:
                if state["done"]:
                    return 0
                state["done"] = True
                data = parse()
                clone = plugin_clone(
                    plugin_root or env.get("TSL_PLUGIN_ROOT") or env.get("CLAUDE_PLUGIN_ROOT")
                )
                if event == "pre-tool" and update_command_allowed(data, clone):
                    _log(
                        home,
                        event,
                        "allow",
                        "E-VER-01",
                        f"update command: tsl {__version__}, plugin {pv}",
                    )
                    return 0
                detail = (
                    f"tsl {__version__} does not match plugin {pv} (E-VER-01). "
                    f"Install tsl {pv}. {update_hint(clone)}"
                )
                finish(failure_output(event, "version", detail, data, home))
                return 0
        out, code = runner(event, box["stdin"])
    except BaseException as e:
        err = f"tsl hook {event} failed with {type(e).__name__}"
    timer.cancel()
    with gate:
        if state["done"]:  # the watchdog already answered
            return 0
        state["done"] = True
        if err is not None or code != 0:
            finish(
                failure_output(
                    event,
                    "crash",
                    err or f"tsl hook {event} exited with status {code}",
                    parse(),
                    home,
                )
            )
        else:
            finish(out)
        return 0


def main(event: str, argv: list[str] | None = None) -> int:
    """Entry for `tsl hook-run <event> [--plugin-root <dir>]` (and the older `tsl hook <event>`)."""
    started = _T0
    from tsl.core import proc

    proc.contain()  # children of this hook end with it (item 11)
    root = None
    rest = list(argv or [])
    if len(rest) >= 2 and rest[0] == "--plugin-root":
        root = rest[1]
    return guarded(event, sys.stdin.read, plugin_root=root, started=started)
