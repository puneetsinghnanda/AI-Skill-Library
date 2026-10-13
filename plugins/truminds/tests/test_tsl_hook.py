"""Contract tests for bin/tsl-hook with a fake `tsl` on PATH (SDD-05 §5.2, §5.4; TST-01 §2.3; TC-HK-007 on Linux).

Every failure kind (version mismatch, tsl missing, crash, timeout) is tested for pre-tool and pre-mcp both inside a
run (fail closed: deny with E-HOOK-01) and outside a run (fail open: exit 0, no output), plus the post-write and
session failure rules, stdin pass-through, the session-index route to "run active" and the hook log line.
The real `tsl` is never used: PATH holds only the fake and the system tool folders.
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import time
from pathlib import Path

import pytest

from conftest import PLUGIN

LAUNCHER = PLUGIN / "bin" / "tsl-hook"
PLUGIN_VERSION = json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))["version"]
SHELLS = [s for s in ("sh", "dash", "bash") if shutil.which(s)]
SYSTEM_PATH = os.pathsep.join(p for p in ("/usr/bin", "/bin", "/usr/sbin", "/sbin") if Path(p).is_dir())

FAKE_TSL = """#!/bin/sh
# Fake tsl for launcher tests. Behaviour comes from FAKE_TSL_* environment variables.
if [ "${1:-}" = "--version" ]; then
  echo "tsl ${FAKE_TSL_VERSION:-0.0.0}"
  exit 0
fi
[ "${1:-}" = "hook" ] || exit 64
cat > "${FAKE_TSL_STDIN_COPY:-/dev/null}"
case "${FAKE_TSL_MODE:-ok}" in
  ok) printf '%s' "${FAKE_TSL_OUTPUT:-}"; exit 0 ;;
  crash) echo "Traceback: boom" >&2; exit 3 ;;
  sleep) exec sleep 30 ;;
esac
"""


@pytest.fixture
def env(tmp_path: Path) -> dict[str, str]:
    home = tmp_path / "home"
    home.mkdir()
    fakebin = tmp_path / "fakebin"
    fakebin.mkdir()
    tsl = fakebin / "tsl"
    tsl.write_text(FAKE_TSL, encoding="utf-8")
    tsl.chmod(tsl.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return {
        "HOME": str(home),
        "PATH": f"{fakebin}{os.pathsep}{SYSTEM_PATH}",
        "CLAUDE_PLUGIN_ROOT": str(PLUGIN),
        "TMPDIR": str(tmp_path),
        "FAKE_TSL_VERSION": PLUGIN_VERSION,
        "LC_ALL": "C",
    }


@pytest.fixture
def companion(tmp_path: Path) -> Path:
    """An invented companion repo with tsl.yaml and an empty runs/active folder."""
    root = tmp_path / "CL-1-SYS-ORD-companion"
    (root / "runs" / "active").mkdir(parents=True)
    (root / "artifacts" / "ABC-142").mkdir(parents=True)
    (root / "tsl.yaml").write_text("schema: tsl-config.v1\n", encoding="utf-8")
    return root


def lock(companion: Path) -> Path:
    p = companion / "runs" / "active" / "ABC-142__brownfield-change.lock"
    p.write_text('{"schema": "run-lock.v1"}\n', encoding="utf-8")
    return p


def hook_input(cwd: Path, event: str, session: str = "sess-0001") -> str:
    tool = {"pre-tool": "Write", "pre-mcp": "mcp__tracker__create_issue", "post-write": "Write"}.get(event)
    doc: dict[str, object] = {"session_id": session, "cwd": str(cwd), "hook_event_name": event}
    if tool:
        doc["tool_name"] = tool
        doc["tool_input"] = {"file_path": str(cwd / "artifacts" / "ABC-142" / "req.md")}
    return json.dumps(doc)


def run(
    env: dict[str, str], event: str, stdin: str, shell: str = "sh", cwd: Path | None = None, **extra: str
) -> subprocess.CompletedProcess[str]:
    e = {**env, **extra}
    return subprocess.run(
        [shell, str(LAUNCHER), event],
        input=stdin,
        capture_output=True,
        text=True,
        env=e,
        cwd=cwd or Path(env["HOME"]),
        timeout=60,
        check=False,
    )


def break_tsl(env: dict[str, str], kind: str) -> dict[str, str]:
    """Make the fake tsl fail in one of the four SDD-05 §5.4 ways."""
    e = dict(env)
    if kind == "version-mismatch":
        e["FAKE_TSL_VERSION"] = "9.9.9"
    elif kind == "missing":
        e["PATH"] = SYSTEM_PATH
    elif kind == "crash":
        e["FAKE_TSL_MODE"] = "crash"
    elif kind == "timeout":
        e["FAKE_TSL_MODE"] = "sleep"
        e["TSL_HOOK_BUDGET_S"] = "1"
    return e


def assert_deny(cp: subprocess.CompletedProcess[str]) -> dict[str, object]:
    assert cp.returncode == 0, cp.stderr
    out = json.loads(cp.stdout)
    hso = out["hookSpecificOutput"]
    assert hso["hookEventName"] == "PreToolUse"
    assert hso["permissionDecision"] == "deny"
    assert str(hso["permissionDecisionReason"]).startswith("E-HOOK-01 ")
    return out


FAILURES = ["version-mismatch", "missing", "crash", "timeout"]


# ------------------------------------------------------------------------------------- fail closed / fail open
@pytest.mark.parametrize("shell", SHELLS)
@pytest.mark.parametrize("event", ["pre-tool", "pre-mcp"])
@pytest.mark.parametrize("failure", FAILURES)
def test_in_run_fails_closed(env: dict[str, str], companion: Path, failure: str, event: str, shell: str) -> None:
    lock(companion)
    start = time.monotonic()
    cp = run(break_tsl(env, failure), event, hook_input(companion, event), shell=shell)
    out = assert_deny(cp)
    reason = str(out["hookSpecificOutput"]["permissionDecisionReason"])  # type: ignore[index]
    if failure in ("version-mismatch", "missing"):
        assert f"Install tsl {PLUGIN_VERSION}" in reason
    if failure == "version-mismatch":
        assert "E-VER-01" in reason and "9.9.9" in reason
    if failure == "timeout":
        assert "timed out" in reason
        assert time.monotonic() - start < 6, "the launcher's own budget must stop a hung tsl"


@pytest.mark.parametrize("shell", SHELLS)
@pytest.mark.parametrize("event", ["pre-tool", "pre-mcp"])
@pytest.mark.parametrize("failure", FAILURES)
def test_out_of_run_fails_open(env: dict[str, str], companion: Path, failure: str, event: str, shell: str) -> None:
    cp = run(break_tsl(env, failure), event, hook_input(companion, event), shell=shell)
    assert cp.returncode == 0, cp.stderr
    assert cp.stdout == "", "allow = exit 0 with no output"


@pytest.mark.parametrize("failure", FAILURES)
def test_outside_any_companion_repo_fails_open(env: dict[str, str], tmp_path: Path, failure: str) -> None:
    elsewhere = tmp_path / "scratch"
    elsewhere.mkdir()
    cp = run(break_tsl(env, failure), "pre-tool", hook_input(elsewhere, "pre-tool"))
    assert cp.returncode == 0 and cp.stdout == ""


def test_active_run_found_through_the_session_index(env: dict[str, str], companion: Path, tmp_path: Path) -> None:
    """cwd is outside the companion repo (a product repo), but this session's index points at a live lock."""
    lk = lock(companion)
    sessions = Path(env["HOME"]) / ".truminds" / "sessions"
    sessions.mkdir(parents=True)
    (sessions / "sess-0042.json").write_text(
        json.dumps(
            {
                "schema": "session-index.v1",
                "session_id": "sess-0042",
                "run_id": "run_01JB2C3D4E5F6G7H8J9KMNPQRS",
                "companion": str(companion),
                "lock": str(lk.relative_to(companion)),
                "bound_at": "2026-01-05T09:58:00Z",
            }
        ),
        encoding="utf-8",
    )
    product = tmp_path / "sample-orders"
    product.mkdir()
    cp = run(break_tsl(env, "crash"), "pre-tool", hook_input(product, "pre-tool", session="sess-0042"))
    assert_deny(cp)
    # Same input once the lock is released: the run is over, so the hook fails open.
    lk.unlink()
    cp = run(break_tsl(env, "crash"), "pre-tool", hook_input(product, "pre-tool", session="sess-0042"))
    assert cp.returncode == 0 and cp.stdout == ""


def test_session_id_with_path_characters_is_not_used_as_a_path(env: dict[str, str], tmp_path: Path) -> None:
    product = tmp_path / "p"
    product.mkdir()
    cp = run(break_tsl(env, "crash"), "pre-tool", hook_input(product, "pre-tool", session="../../etc/passwd"))
    assert cp.returncode == 0 and cp.stdout == ""


# ------------------------------------------------------------------------------------- post-write and sessions
@pytest.mark.parametrize("failure", FAILURES)
@pytest.mark.parametrize("in_run", [True, False])
def test_post_write_always_fails_open_with_a_warning(
    env: dict[str, str], companion: Path, failure: str, in_run: bool
) -> None:
    if in_run:
        lock(companion)
    cp = run(break_tsl(env, failure), "post-write", hook_input(companion, "post-write"))
    assert cp.returncode == 0
    out = json.loads(cp.stdout)
    assert set(out) == {"systemMessage"}
    assert "Your file was kept" in out["systemMessage"]


@pytest.mark.parametrize("event", ["session-start", "session-end"])
@pytest.mark.parametrize("failure", ["version-mismatch", "missing"])
def test_session_hooks_warn_when_tsl_is_missing_or_outdated(
    env: dict[str, str], companion: Path, event: str, failure: str
) -> None:
    cp = run(break_tsl(env, failure), event, hook_input(companion, event))
    assert cp.returncode == 0
    msg = json.loads(cp.stdout)["systemMessage"]
    assert f"Install tsl {PLUGIN_VERSION}" in msg and "uv tool install" in msg


@pytest.mark.parametrize("event", ["session-start", "session-end"])
@pytest.mark.parametrize("failure", ["crash", "timeout"])
def test_session_hooks_ignore_a_crash_or_timeout(
    env: dict[str, str], companion: Path, event: str, failure: str
) -> None:
    lock(companion)
    cp = run(break_tsl(env, failure), event, hook_input(companion, event))
    assert cp.returncode == 0 and cp.stdout == ""


# ------------------------------------------------------------------------------------- pass-through
@pytest.mark.parametrize("shell", SHELLS)
@pytest.mark.parametrize("event", ["session-start", "pre-tool", "pre-mcp", "post-write", "session-end"])
def test_healthy_tsl_gets_stdin_and_its_output_passes_through(
    env: dict[str, str], companion: Path, tmp_path: Path, event: str, shell: str
) -> None:
    lock(companion)
    copy = tmp_path / "stdin-copy.json"
    payload = hook_input(companion, event)
    answer = json.dumps(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": "E-POL-01 outside allowed paths",
            }
        }
    )
    cp = run(env, event, payload, shell=shell, FAKE_TSL_STDIN_COPY=str(copy), FAKE_TSL_OUTPUT=answer)
    assert cp.returncode == 0, cp.stderr
    assert cp.stdout == answer, "the launcher never rewrites tsl's decision"
    assert copy.read_text(encoding="utf-8") == payload, "stdin reaches tsl unchanged"


def test_healthy_tsl_allow_is_silent(env: dict[str, str], companion: Path) -> None:
    lock(companion)
    cp = run(env, "pre-tool", hook_input(companion, "pre-tool"))
    assert cp.returncode == 0 and cp.stdout == ""


def test_failures_are_logged_locally(env: dict[str, str], companion: Path) -> None:
    lock(companion)
    run(break_tsl(env, "crash"), "pre-mcp", hook_input(companion, "pre-mcp"))
    log = (Path(env["HOME"]) / ".truminds" / "logs" / "hook.log").read_text(encoding="utf-8")
    assert "event=pre-mcp decision=deny code=E-HOOK-01" in log
    assert "boom" not in log, "the log keeps codes and short details, never tsl's raw output"


def test_budget_override_cannot_raise_the_budget() -> None:
    text = LAUNCHER.read_text(encoding="utf-8")
    assert '-lt "$BUDGET"' in text, "TSL_HOOK_BUDGET_S may only lower the budget"


def test_unknown_event_is_rejected(env: dict[str, str], companion: Path) -> None:
    cp = run(env, "pre-everything", "{}")
    assert cp.returncode == 1 and cp.stdout == ""


def test_no_temp_files_are_left_behind(env: dict[str, str], companion: Path, tmp_path: Path) -> None:
    lock(companion)
    run(break_tsl(env, "timeout"), "pre-tool", hook_input(companion, "pre-tool"))
    run(env, "pre-tool", hook_input(companion, "pre-tool"))
    assert not list(tmp_path.glob("tsl-hook.*"))
