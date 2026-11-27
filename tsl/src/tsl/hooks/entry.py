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
    root = resolve_plugin_root(env, root)
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
# update needed a terminal outside Claude Code. These Bash commands, and only these, still run,
# each as the whole command with nothing chained:
# - anywhere: `tsl --version`, `tsl doctor`; and the two `claude plugin ... update` lines, which
#   copy the plugin from the clone when it comes from one, so then only when the clone is trusted;
# - in the AI-Skill-Library clone the plugin comes from, and only as `cd <absolute clone path> &&
#   <command>`: `git pull`, `git checkout main` and the reinstall of tsl. Never judged by the
#   hook's cwd field alone, which may not be where the Bash tool runs.
# The clone is trusted only when no folder the run's agent may write to (companions, product
# repos) is inside it or contains it.
# A path is plain characters only, so no shell expansion can turn it into more arguments: no
# braces ({a,--index-url=...} would add one), globs, quotes inside, $ or `. In double quotes it may
# also hold spaces and a backslash before a plain character (a Windows path), never a backslash
# before the closing quote (bash reads that as an escaped quote). A ~ may only appear in a Windows
# short name (JAPMAN~1, RUNNER~1) after a letter or digit, where bash leaves it alone.
_PLAIN = r"(?:[A-Za-z0-9._/:+@%=-]|(?<=[A-Za-z0-9])~[0-9])+"
_QUOTED = r'"(?:[A-Za-z0-9._/:+@%=~ -]|\\(?=[A-Za-z0-9._~ -]))+"'
_PATH = rf"(?:{_QUOTED}|{_PLAIN})"
_CD = re.compile(rf"cd (?P<dir>{_PATH}) && (?P<rest>.+)")
_TSL_INFO = re.compile(r"tsl(?:\.exe)? (?:--version|doctor(?: --json)?)")
_PLUGIN_UPDATE = (
    re.compile(r"claude plugin marketplace update truminds-skill-library"),
    re.compile(r"claude plugin update truminds@truminds-skill-library"),
)
# The install takes no other option; --no-config so no uv.toml or pyproject setting in the folder
# changes it; TSL_ORG_FILE (sign-in and service settings built into tsl) only as the absolute path
# of the clone's own settings file (the build resolves a relative one from ./tsl, where it is not):
# the agent picks neither the build inputs nor the service. The clone's .git config and hooks run
# on git pull, so the clone must stay outside what the agent may write: the folder commands are
# refused when the run's companion or product repos are inside the clone.
_UPDATE_IN_CLONE = (re.compile(r"git pull(?: --ff-only)?"), re.compile(r"git checkout main"))
_INSTALL = re.compile(
    rf"(?:TSL_ORG_FILE=(?P<org>{_PATH}) )?"
    r"uv tool install --python 3\.12 --reinstall --no-cache --no-config \./tsl"
)
ORG_FILE = ("deploy", "render", "tsl-org.github.toml")
MARKETPLACE = "truminds-skill-library"


def _absolute(p: str) -> bool:
    """An absolute path that bash and this hook resolve the same way. On Windows: C:/..., C:\\...
    or Git Bash's /c/...; never another /... (Git Bash maps it under its own root) or ~ (bash takes
    $HOME, Python USERPROFILE). Elsewhere: /...."""
    p = p[1:-1] if p.startswith('"') else p
    if os.name == "nt":
        return re.match(r"(?:[A-Za-z]:[/\\]|/[A-Za-z](?:/|$))", p) is not None
    return p.startswith("/")


def _local_path(p: str) -> str:
    """An absolute path (see _absolute) as this OS names it: Git Bash /c/... is C:/... here."""
    p = p[1:-1] if p.startswith('"') else p
    m = re.fullmatch(r"/([A-Za-z])(/.*)?", p)
    if os.name == "nt" and m:
        p = f"{m.group(1)}:{m.group(2) or '/'}"
    return os.path.realpath(p)


def _same(a: str, b: str) -> bool:
    return os.path.normcase(a) == os.path.normcase(b)


def _inside(path: str, folder: str) -> bool:
    try:
        return _same(os.path.commonpath([os.path.realpath(path), folder]), folder)
    except ValueError:  # different drives
        return False


def resolve_plugin_root(env: Mapping[str, str], root: str | None = None) -> str | None:
    """The plugin root: the launcher's --plugin-root, else TSL_PLUGIN_ROOT / CLAUDE_PLUGIN_ROOT."""
    return root or env.get("TSL_PLUGIN_ROOT") or env.get("CLAUDE_PLUGIN_ROOT") or None


def _is_clone(d: str) -> bool:
    return os.path.isfile(os.path.join(d, "tsl", "pyproject.toml")) and os.path.isfile(
        os.path.join(d, "plugins", "truminds", ".claude-plugin", "plugin.json")
    )


def plugin_clone(root: str | None, env: Mapping[str, str] | None = None) -> str | None:
    """The AI-Skill-Library clone the plugin comes from, or None.

    Either the plugin is read from the clone itself (<clone>/plugins/truminds), or Claude Code runs
    an installed copy (~/.claude/plugins/cache/<marketplace>/truminds/<version>) of a marketplace
    added from a folder: then the clone is that folder, as known_marketplaces.json records it. A
    plugin loaded from anywhere else (--plugin-dir, a GitHub marketplace) has no clone."""
    if not root:
        return None
    up = os.path.realpath(os.path.join(root, os.pardir, os.pardir))
    if _is_clone(up) and _same(os.path.join(up, "plugins", "truminds"), os.path.realpath(root)):
        return up
    parts = os.path.realpath(root).replace("\\", "/").split("/")
    # Only the truminds plugin of this marketplace: the hint names both in its update commands.
    if len(parts) < 5 or parts[-5:-1] != ["plugins", "cache", MARKETPLACE, "truminds"]:
        return None
    env = os.environ if env is None else env
    conf = env.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude")
    try:
        with open(os.path.join(conf, "plugins", "known_marketplaces.json"), encoding="utf-8") as fh:
            src = json.load(fh)[MARKETPLACE]["source"]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    path = src.get("path") if isinstance(src, dict) and src.get("source") == "directory" else None
    if not isinstance(path, str) or not path:
        return None
    folder = os.path.realpath(path)
    return folder if _is_clone(folder) else None


def _run_folders(data: Mapping[str, object], home: str) -> list[str] | None:
    """Every folder the open run's agent may write to: the companion named by the session index
    and the one found by the tsl.yaml walk from cwd (both, as either may be the open run's), and
    their product repos. None when no companion is found or a local.yaml can't be read."""
    comps: list[str] = []
    sid = data.get("session_id")
    if isinstance(sid, str) and sid and not (set(sid) - _SID_CHARS):
        try:
            with open(os.path.join(home, "sessions", sid + ".json"), encoding="utf-8") as fh:
                c = json.load(fh).get("companion")
            if isinstance(c, str) and c:
                comps.append(os.path.realpath(c))
        except (OSError, ValueError, AttributeError):
            pass
    cwd = data.get("cwd")
    d = os.path.realpath(cwd if isinstance(cwd, str) and cwd else os.getcwd())
    while not os.path.isfile(os.path.join(d, "tsl.yaml")) and os.path.dirname(d) != d:
        d = os.path.dirname(d)
    if os.path.isfile(os.path.join(d, "tsl.yaml")):
        comps.append(d)
    if not comps:
        return None
    folders = list(comps)
    for comp in comps:
        local = os.path.join(comp, ".tsl", "local.yaml")
        if not os.path.isfile(local):
            continue
        # As Companion.local_paths reads it (yaml.safe_load: flow style, quotes, wrapped lines,
        # a # inside a path); yaml is imported only here, on a version mismatch in a run.
        try:
            from pathlib import Path

            from tsl.core.jsonio import read_yaml

            repos = read_yaml(Path(local))["product_repos"]
            paths = [str(p) for p in repos.values()] if isinstance(repos, dict) else None
        except Exception:
            return None
        if paths is None:
            return None
        for p in paths:
            folders.append(os.path.realpath(p if os.path.isabs(p) else os.path.join(comp, p)))
    return folders


def _clone_trusted(data: Mapping[str, object], clone: str, home: str) -> bool:
    """False when the open run's agent may have written to the clone: a run folder is inside it,
    or it is inside a run folder (a parent folder or monorepo as a product repo)."""
    folders = _run_folders(data, home)
    return folders is not None and not any(_inside(f, clone) or _inside(clone, f) for f in folders)


def update_hint(clone: str | None) -> str:
    """How to end the mismatch: the commands update_command_allowed lets through in a run."""
    head = (
        "While a run is open, only the update commands run until the versions match, each as its "
        "own command with the Bash tool. "
    )
    anywhere = (
        "claude plugin marketplace update truminds-skill-library; claude plugin update "
        "truminds@truminds-skill-library; then /reload-plugins or restart Claude Code. "
        "See docs/testing/team-setup-guide.md section 7a."
    )
    c = clone.replace(os.sep, "/") if clone else None
    if c is None or not re.fullmatch(_QUOTED, f'"{c}"'):
        return head + (
            "tsl cannot be updated from here (your plugin does not come from an AI-Skill-Library "
            "clone on this machine, or its path has characters this check refuses), so update tsl "
            "from a terminal outside Claude Code (in your clone: git pull, then the uv tool "
            f"install line of section 5); from here: {anywhere}"
        )
    return head + (
        f'In the clone, each as one command: cd "{c}" && git pull (on the branch you update '
        f'from, usually main); cd "{c}" && TSL_ORG_FILE="{c}/{"/".join(ORG_FILE)}" uv tool '
        f"install --python 3.12 --reinstall --no-cache --no-config ./tsl. Then: {anywhere}"
    )


def update_command_allowed(data: Mapping[str, object], clone: str | None, home: str) -> bool:
    """True when this pre-tool call is one of the update commands above, run where it may run."""
    if data.get("tool_name") != "Bash":
        return False
    ti = data.get("tool_input")
    command = ti.get("command") if isinstance(ti, dict) else None
    if not isinstance(command, str) or "\n" in command or "\r" in command:
        return False
    command = command.strip()  # not collapsed: a quoted path keeps its own spaces
    m = _CD.fullmatch(command)
    where = None
    if m:
        if not _absolute(m.group("dir")):
            return False
        where, command = _local_path(m.group("dir")), m.group("rest")
    if _TSL_INFO.fullmatch(command):
        return True
    if any(p.fullmatch(command) for p in _PLUGIN_UPDATE):
        # From a clone they copy its plugins/truminds (hooks included) into the plugin cache:
        # the same trust as git pull and the reinstall. From GitHub (no clone) they don't.
        return clone is None or _clone_trusted(data, clone, home)
    if where is None or clone is None or not _same(where, clone):
        return False
    if not _clone_trusted(data, clone, home):
        return False  # the agent could have written to the clone it would now build from
    if any(p.fullmatch(command) for p in _UPDATE_IN_CLONE):
        return True
    install = _INSTALL.fullmatch(command)
    if install is None:
        return False
    org = install.group("org")
    if org is None:
        return True
    own = os.path.realpath(os.path.join(clone, *ORG_FILE))
    return _absolute(org) and _same(_local_path(org), own)


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
            # Decide first, with the watchdog still running: the file reads below can be slow,
            # and an error in them must end in the version deny, never in an empty (allow)
            # answer. Only then take the gate and answer.
            data = parse()
            try:
                clone = plugin_clone(resolve_plugin_root(env, plugin_root), env)
                allowed = event == "pre-tool" and update_command_allowed(data, clone, home)
                hint = update_hint(clone)
            except Exception:
                allowed, hint = False, update_hint(None)
            timer.cancel()
            with gate:
                if state["done"]:
                    return 0
                state["done"] = True
                if allowed:
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
                    f"Install tsl {pv}. {hint}"
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
