"""Fail rules of `tsl hook <event>` that used to live in bin/tsl-hook (SDD-05 §5.4, SDD-04 §11, E-VER-01).

Inside an open run (lock file under runs/active/) any crash, overrun or version mismatch of pre-tool and pre-mcp
denies with E-HOOK-01 (fail closed); outside a run it allows (fail open). post-write allows with a systemMessage;
session hooks warn on a version mismatch and ignore a crash or timeout.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from tsl import __version__
from tsl.hooks import entry


@pytest.fixture
def home(tmp_path: Path) -> Path:
    h = tmp_path / "home" / ".truminds"
    h.mkdir(parents=True)
    return h


@pytest.fixture
def companion(tmp_path: Path) -> Path:
    root = tmp_path / "companion"
    (root / "runs" / "active").mkdir(parents=True)
    (root / "tsl.yaml").write_text("schema: tsl-config.v1\n", encoding="utf-8")
    return root


def plugin(tmp_path: Path, version: str) -> Path:
    root = tmp_path / "plugin"
    (root / ".claude-plugin").mkdir(parents=True, exist_ok=True)
    (root / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"version": version}), encoding="utf-8"
    )
    return root


def lock(companion: Path) -> None:
    (companion / "runs" / "active" / "ABC-1__wf.lock").write_text("{}", encoding="utf-8")


def stdin(cwd: Path, event: str = "pre-tool") -> str:
    return json.dumps(
        {"session_id": "s-1", "cwd": str(cwd), "tool_name": "Write", "hook_event_name": event}
    )


def call(
    event: str,
    cwd: Path,
    home: Path,
    tmp_path: Path,
    *,
    version: str | None = None,
    runner: Callable[[str, str], tuple[str, int]] | None = None,
    budget: str | None = None,
) -> tuple[int, str, list[int]]:
    out: list[str] = []
    exits: list[int] = []
    env = {"TSL_PLUGIN_ROOT": str(plugin(tmp_path, version or __version__))}
    if budget:
        env["TSL_HOOK_BUDGET_S"] = budget
    rc = entry.guarded(
        event,
        stdin(cwd, event),
        env=env,
        home=home,
        emit=out.append,
        hard_exit=exits.append,
        **({"runner": runner} if runner else {}),  # type: ignore[arg-type]
    )
    return rc, "".join(out), exits


def boom(event: str, text: str) -> tuple[str, int]:
    raise RuntimeError("boom")


def nonzero(event: str, text: str) -> tuple[str, int]:
    return "", 3


def hang(event: str, text: str) -> tuple[str, int]:
    time.sleep(2)
    return "", 0


def ok(event: str, text: str) -> tuple[str, int]:
    return '{"x":1}', 0


def deny_json(out: str) -> dict[str, Any]:
    hso: dict[str, Any] = json.loads(out)["hookSpecificOutput"]
    assert hso["permissionDecision"] == "deny" and hso["permissionDecisionReason"].startswith(
        "E-HOOK-01 "
    )
    return hso


FAILURES = ["version", "crash", "exit", "timeout"]


def trigger(
    kind: str, event: str, cwd: Path, home: Path, tmp_path: Path
) -> tuple[int, str, list[int]]:
    if kind == "version":
        return call(event, cwd, home, tmp_path, version="9.9.9", runner=ok)
    if kind == "crash":
        return call(event, cwd, home, tmp_path, runner=boom)
    if kind == "exit":
        return call(event, cwd, home, tmp_path, runner=nonzero)
    return call(event, cwd, home, tmp_path, runner=hang, budget="1")


@pytest.mark.parametrize("event", ["pre-tool", "pre-mcp"])
@pytest.mark.parametrize("kind", FAILURES)
def test_in_run_fails_closed(
    kind: str, event: str, companion: Path, home: Path, tmp_path: Path
) -> None:
    lock(companion)
    rc, out, exits = trigger(kind, event, companion, home, tmp_path)
    assert rc == 0 or exits == [0]
    reason = deny_json(out)["permissionDecisionReason"]
    if kind == "version":
        assert "E-VER-01" in reason and "9.9.9" in reason and "Install tsl 9.9.9" in reason
    if kind == "timeout":
        assert exits == [0] and "timed out" in reason
    log = (home / "logs" / "hook.log").read_text(encoding="utf-8")
    assert f"event={event} decision=deny code=E-HOOK-01" in log


@pytest.mark.parametrize("event", ["pre-tool", "pre-mcp"])
@pytest.mark.parametrize("kind", FAILURES)
def test_out_of_run_fails_open(
    kind: str, event: str, companion: Path, home: Path, tmp_path: Path
) -> None:
    rc, out, _ = trigger(kind, event, companion, home, tmp_path)
    assert rc == 0
    assert out == ""
    assert "decision=allow" in (home / "logs" / "hook.log").read_text(encoding="utf-8")


def test_outside_any_companion_repo_fails_open(home: Path, tmp_path: Path) -> None:
    elsewhere = tmp_path / "scratch"
    elsewhere.mkdir()
    _, out, _ = trigger("crash", "pre-tool", elsewhere, home, tmp_path)
    assert out == ""


def test_session_index_finds_the_run(companion: Path, home: Path, tmp_path: Path) -> None:
    lock(companion)
    (home / "sessions").mkdir()
    (home / "sessions" / "s-1.json").write_text(
        json.dumps({"companion": str(companion), "lock": "runs/active/ABC-1__wf.lock"}),
        encoding="utf-8",
    )
    product = tmp_path / "product"
    product.mkdir()
    _, out, _ = call("pre-tool", product, home, tmp_path, runner=boom)
    deny_json(out)
    (companion / "runs" / "active" / "ABC-1__wf.lock").unlink()
    _, out, _ = call("pre-tool", product, home, tmp_path, runner=boom)
    assert out == ""


@pytest.mark.parametrize("kind", FAILURES)
@pytest.mark.parametrize("in_run", [True, False])
def test_post_write_fails_open_with_warning(
    kind: str, in_run: bool, companion: Path, home: Path, tmp_path: Path
) -> None:
    if in_run:
        lock(companion)
    _, out, _ = trigger(kind, "post-write", companion, home, tmp_path)
    msg = json.loads(out)
    assert set(msg) == {"systemMessage"} and "Your file was kept" in msg["systemMessage"]


@pytest.mark.parametrize("event", ["session-start", "session-end"])
def test_session_hooks_warn_on_version_mismatch(
    event: str, companion: Path, home: Path, tmp_path: Path
) -> None:
    _, out, _ = trigger("version", event, companion, home, tmp_path)
    assert "Install tsl 9.9.9" in json.loads(out)["systemMessage"]


@pytest.mark.parametrize("event", ["session-start", "session-end"])
@pytest.mark.parametrize("kind", ["crash", "exit", "timeout"])
def test_session_hooks_ignore_crash_and_timeout(
    kind: str, event: str, companion: Path, home: Path, tmp_path: Path
) -> None:
    lock(companion)
    _, out, _ = trigger(kind, event, companion, home, tmp_path)
    assert out == ""


def test_healthy_run_passes_output_through_and_no_watchdog_fires(
    companion: Path, home: Path, tmp_path: Path
) -> None:
    rc, out, exits = call("pre-tool", companion, home, tmp_path, runner=ok)
    assert (rc, out, exits) == (0, '{"x":1}\n', [])


def test_budget_can_only_be_lowered() -> None:
    assert entry.budget_for("pre-tool", {}) == 8
    assert entry.budget_for("pre-tool", {"TSL_HOOK_BUDGET_S": "1"}) == 1
    assert entry.budget_for("pre-tool", {"TSL_HOOK_BUDGET_S": "99"}) == 8
    assert entry.budget_for("pre-tool", {"TSL_HOOK_BUDGET_S": "x"}) == 8
    assert entry.budget_for("post-write", {}) == 85
    assert entry.budget_for("session-end", {}) == 12


def test_unreadable_plugin_json_counts_as_mismatch(
    companion: Path, home: Path, tmp_path: Path
) -> None:
    lock(companion)
    out: list[str] = []
    entry.guarded(
        "pre-tool",
        stdin(companion),
        env={"TSL_PLUGIN_ROOT": str(tmp_path / "nope")},
        home=home,
        emit=out.append,
        runner=ok,
    )
    assert "plugin unknown" in deny_json("".join(out))["permissionDecisionReason"]


def test_cli_end_to_end_version_mismatch_denies_in_run(companion: Path, tmp_path: Path) -> None:
    """Real `tsl hook` process: the entry is wired into the CLI, stdin and stdout pass through."""
    lock(companion)
    fake_home = tmp_path / "h"
    fake_home.mkdir()
    env = {
        "PATH": "",
        "SYSTEMROOT": "C:\\Windows",
        "HOME": str(fake_home),
        "USERPROFILE": str(fake_home),
        "TSL_PLUGIN_ROOT": str(plugin(tmp_path, "9.9.9")),
    }
    cp = subprocess.run(
        [sys.executable, "-m", "tsl", "hook", "pre-tool"],
        input=stdin(companion),
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
        check=False,
    )
    assert cp.returncode == 0, cp.stderr
    assert "E-VER-01" in deny_json(cp.stdout)["permissionDecisionReason"]


def test_hang_before_stdin_read_is_denied_within_budget(
    companion: Path, home: Path, tmp_path: Path
) -> None:
    lock(companion)
    out: list[str] = []
    exits: list[int] = []

    def slow_stdin() -> str:
        time.sleep(3)
        return ""

    t0 = time.perf_counter()
    done = threading.Event()

    def stop(c: int) -> None:
        exits.append(c)
        done.set()

    def go() -> None:
        entry.guarded(
            "pre-tool",
            slow_stdin,
            env={"TSL_HOOK_BUDGET_S": "1", "TSL_PLUGIN_ROOT": str(plugin(tmp_path, __version__))},
            home=home,
            emit=out.append,
            hard_exit=stop,
        )

    # cwd cannot come from the unread stdin, so run from the companion repo: the cwd walk finds the lock.
    old = os.getcwd()
    os.chdir(companion)
    try:
        th = threading.Thread(target=go, daemon=True)
        th.start()
        assert done.wait(2.5), "watchdog must answer while stdin is still blocked"
    finally:
        os.chdir(old)
    assert time.perf_counter() - t0 < 2.5 and exits == [0]
    deny_json("".join(out))


def test_budget_counts_from_process_start(companion: Path, home: Path, tmp_path: Path) -> None:
    lock(companion)
    out_l: list[str] = []
    exits: list[int] = []
    entry.guarded(
        "pre-tool",
        stdin(companion),
        env={"TSL_HOOK_BUDGET_S": "5"},
        home=home,
        runner=hang,
        emit=out_l.append,
        hard_exit=exits.append,
        started=time.perf_counter() - 4.5,
    )
    assert exits == [0] and "timed out" in deny_json("".join(out_l))["permissionDecisionReason"]


def test_plugin_root_argument_drives_the_version_check(
    companion: Path, home: Path, tmp_path: Path
) -> None:
    lock(companion)
    out_l: list[str] = []
    entry.guarded(
        "pre-tool",
        stdin(companion),
        env={},
        home=home,
        runner=ok,
        emit=out_l.append,
        plugin_root=str(plugin(tmp_path, "9.9.9")),
    )
    assert "E-VER-01" in deny_json("".join(out_l))["permissionDecisionReason"]


def test_import_failure_before_dispatch_goes_through_the_fail_rule(
    companion: Path, home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lock(companion)
    monkeypatch.setitem(
        sys.modules, "tsl", None
    )  # `from tsl import __version__` raises ImportError
    out_l: list[str] = []
    entry.guarded("pre-tool", stdin(companion), env={}, home=home, runner=ok, emit=out_l.append)
    assert "Error" in deny_json("".join(out_l))["permissionDecisionReason"]
