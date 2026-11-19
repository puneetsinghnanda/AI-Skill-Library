"""Child processes that end with the hook that started them (roadmap item 11). Stdlib only.

A hook whose watchdog fires ends with os._exit (hooks/entry.py). The children it started do not
end with it: `git push` and git's own helpers (remote-http, the credential helper) are re-parented
and keep running, now with no timeout at all. Inside a hook process, run() therefore starts each
child as the leader of its own process group and keeps it in a list, so a timeout, or the watchdog
through kill_all(), ends the whole group. Once kill_all() has started, run() starts no new child:
a `git push` that would follow a short command finishing during the kills is refused instead of
leaking. Claude Code ends a timed-out hook by walking its process tree, which still reaches these
groups.

Outside a hook, run() is plain subprocess.run, so CLI commands keep the terminal (an ssh passphrase
prompt still works).
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import threading
from typing import Any, Literal, overload

_contained = False
_closing = False  # set by kill_all(): no new children after it
_live: set[subprocess.Popen[Any]] = set()
_lock = threading.Lock()


def contain() -> None:
    """Called once by the hook entry: from now on children get their own group and are tracked."""
    global _contained
    _contained = True


@overload
def run(
    cmd: list[str],
    *,
    timeout: float,
    input_: str | None = None,
    text: Literal[True] = True,
    **kw: Any,
) -> subprocess.CompletedProcess[str]: ...
@overload
def run(
    cmd: list[str], *, timeout: float, input_: bytes | None = None, text: Literal[False], **kw: Any
) -> subprocess.CompletedProcess[bytes]: ...
def run(
    cmd: list[str],
    *,
    timeout: float,
    input_: str | bytes | None = None,
    text: bool = True,
    **kw: Any,
) -> subprocess.CompletedProcess[Any]:
    """subprocess.run(cmd, capture_output=True, check=False) whose child cannot outlive a hook."""
    if not _contained:
        return subprocess.run(
            cmd, input=input_, capture_output=True, text=text, timeout=timeout, check=False, **kw
        )
    with _lock:  # start and register together, so kill_all() sees every child
        if _closing:
            raise OSError("the hook is ending; no new child processes")
        p = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL if input_ is None else subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=text,
            start_new_session=sys.platform != "win32",
            **kw,
        )
        _live.add(p)
    try:
        out, err = p.communicate(input_, timeout=timeout)
    except subprocess.TimeoutExpired:
        _kill(p)
        p.communicate(timeout=5)  # bounded: a descendant outside the group may hold the pipe
        raise
    finally:
        with _lock:
            _live.discard(p)
    return subprocess.CompletedProcess(cmd, p.returncode, out, err)


def _kill(p: subprocess.Popen[Any]) -> None:
    """End the child and everything it started."""
    try:
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/T", "/F", "/PID", str(p.pid)],
                capture_output=True,
                timeout=5,
                check=False,
            )
        else:
            os.killpg(p.pid, signal.SIGKILL)
    except (OSError, subprocess.SubprocessError):
        pass  # already gone


def kill_all() -> None:
    """End every child still running; the watchdog calls this just before os._exit."""
    global _closing
    with _lock:
        _closing = True
        live = list(_live)
    for p in live:
        _kill(p)
