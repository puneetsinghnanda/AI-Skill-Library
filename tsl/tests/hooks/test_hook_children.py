"""Hook children end with the hook (roadmap item 11; tsl/core/proc.py).

A stalled server stands in for a slow network: it accepts connections and never answers. A child
that is still alive keeps its connection open, so "every connection closed" means "nothing left
running", on every OS and without a process list. Nothing leaves this machine.
"""

from __future__ import annotations

import socket
import subprocess
import sys
import textwrap
import threading
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

from tsl.core import proc


class Stalled:
    def __init__(self) -> None:
        self.sock = socket.socket()
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(16)
        self.port = self.sock.getsockname()[1]
        self.conns: list[socket.socket] = []
        threading.Thread(target=self._accept, daemon=True).start()

    def _accept(self) -> None:
        while True:
            try:
                c, _ = self.sock.accept()
            except OSError:
                return
            self.conns.append(c)

    def wait_connected(self, seconds: float = 10) -> None:
        end = time.monotonic() + seconds
        while not self.conns and time.monotonic() < end:
            time.sleep(0.05)
        assert self.conns, "the child never reached the server"

    def open_connections(self, seconds: float = 3) -> int:
        """Connections whose client is still alive after `seconds` (requests are read and dropped)."""
        end = time.monotonic() + seconds
        alive = 0
        for c in self.conns:
            while True:
                c.settimeout(max(end - time.monotonic(), 0.01))
                try:
                    if not c.recv(65536):
                        break  # closed: the client process is gone
                except TimeoutError:
                    alive += 1
                    break
                except OSError:
                    break  # reset: gone
        return alive

    def close(self) -> None:
        for c in [*self.conns, self.sock]:
            c.close()  # lets a leaked client fail and exit


@pytest.fixture
def server() -> Iterator[Stalled]:
    s = Stalled()
    yield s
    s.close()


def repo_with_stalled_remote(tmp_path: Path, port: int) -> Path:
    r = tmp_path / "companion"
    r.mkdir()
    for args in (
        ["init", "-q", "-b", "main"],
        ["-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-q",
         "--allow-empty", "-m", "x"],
        ["remote", "add", "origin", f"http://127.0.0.1:{port}/companion.git"],
    ):  # fmt: skip
        subprocess.run(["git", *args], cwd=r, check=True, capture_output=True)
    return r


@pytest.mark.parametrize("contained", [True, False], ids=["hook", "without-containment"])
def test_watchdog_leaves_no_git_process_behind(
    server: Stalled, tmp_path: Path, contained: bool
) -> None:
    """session-end's heartbeat push stalls; the watchdog answers at 1 s and ends the hook process.
    Without containment git push and its helpers keep the connection open (the item 11 leak)."""
    repo = repo_with_stalled_remote(tmp_path, server.port)
    code = textwrap.dedent(f"""
        from pathlib import Path
        from tsl.core import proc
        from tsl.gitops.git import Git
        from tsl.hooks.entry import guarded

        if {contained!r}:
            proc.contain()  # what `tsl hook-run` does first

        def runner(event, stdin):
            Git(Path({str(repo)!r})).push("main")
            return "", 0

        guarded("session-end", "{{}}", env={{"TSL_HOOK_BUDGET_S": "1"}}, home={str(tmp_path)!r},
                runner=runner)
    """)
    t0 = time.monotonic()
    cp = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=60)
    assert cp.returncode == 0, cp.stderr
    assert time.monotonic() - t0 < 10, "the watchdog ends the hook"
    server.wait_connected()
    assert server.open_connections() == (0 if contained else 1)


GRANDCHILD = textwrap.dedent("""
    import socket, subprocess, sys, time
    port = int(sys.argv[1])
    if len(sys.argv) == 2:  # the child: start a grandchild, then wait for ever
        subprocess.Popen([sys.executable, __file__, str(port), "grandchild"])
        time.sleep(600)
    s = socket.create_connection(("127.0.0.1", port))
    time.sleep(600)
""")


def test_timeout_in_a_hook_ends_the_whole_group(
    server: Stalled, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    script = tmp_path / "tree.py"
    script.write_text(GRANDCHILD, encoding="utf-8")
    monkeypatch.setattr(proc, "_contained", True)
    with pytest.raises(subprocess.TimeoutExpired):
        proc.run([sys.executable, str(script), str(server.port)], timeout=3)
    server.wait_connected()
    assert server.open_connections() == 0
    assert not proc._live


def test_kill_all_ends_running_children(
    server: Stalled, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    script = tmp_path / "tree.py"
    script.write_text(GRANDCHILD, encoding="utf-8")
    monkeypatch.setattr(proc, "_contained", True)
    th = threading.Thread(
        target=lambda: proc.run([sys.executable, str(script), str(server.port)], timeout=60),
        daemon=True,
    )
    th.start()
    server.wait_connected()
    proc.kill_all()
    th.join(10)
    assert not th.is_alive() and server.open_connections() == 0


def test_outside_a_hook_run_is_plain_subprocess_run(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}

    def fake(cmd: list[str], **kw: object) -> subprocess.CompletedProcess[str]:
        seen.update(kw, cmd=cmd)
        return subprocess.CompletedProcess(cmd, 0, "out", "")

    monkeypatch.setattr(subprocess, "run", fake)
    assert proc.run(["git", "status"], timeout=5, cwd="x").stdout == "out"
    assert seen == {
        "cmd": ["git", "status"],
        "input": None,
        "capture_output": True,
        "text": True,
        "timeout": 5,
        "check": False,
        "cwd": "x",
    }
