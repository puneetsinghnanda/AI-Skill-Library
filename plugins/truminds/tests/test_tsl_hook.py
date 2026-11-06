"""Contract tests for bin/tsl-hook with a fake `tsl` on PATH (SDD-05 §5.2, §5.4; TST-01 §2.3; TC-HK-007 on Linux).

The launcher is a builtin-only shell script that `exec`s `tsl hook <event>` once. It handles only "tsl is not
installed" itself (tested here for every event, inside and outside a run, with the session-index route and the hook
log line); the version check, time budget and crash / timeout rules live in tsl (tsl/tests/hooks/test_entry.py).
Here: stdin and stdout pass-through, the exec contract, unknown events, the plugin root handed to tsl.
The real `tsl` is never used: PATH holds only the fake and the system tool folders.
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

from conftest import PLUGIN

LAUNCHER = PLUGIN / "bin" / "tsl-hook"
PLUGIN_VERSION = json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))["version"]
SHELLS = [s for s in ("sh", "dash", "bash") if shutil.which(s)]
SYSTEM_PATH = os.pathsep.join(p for p in ("/usr/bin", "/bin", "/usr/sbin", "/sbin") if Path(p).is_dir())

FAKE_TSL = """#!/bin/sh
# Fake tsl for launcher tests. Behaviour comes from FAKE_TSL_* environment variables.
[ -z "${FAKE_TSL_OLD:-}" ] || { echo "Error: No such command 'hook-run'." >&2; exit 2; }
[ "${1:-}" = "hook-run" ] || exit 64
cat > "${FAKE_TSL_STDIN_COPY:-/dev/null}"
[ -z "${FAKE_TSL_ARGV_COPY:-}" ] || printf '%s|%s\\n' "$*" "$$" > "$FAKE_TSL_ARGV_COPY"
printf '%s' "${FAKE_TSL_OUTPUT:-}"
exit "${FAKE_TSL_EXIT:-0}"
"""


@pytest.fixture
def env(tmp_path: Path) -> dict[str, str]:
    home = tmp_path / "home"
    home.mkdir()
    fakebin = tmp_path / "fakebin"
    fakebin.mkdir()
    tsl = fakebin / "tsl"
    tsl.write_text(FAKE_TSL, encoding="utf-8", newline="\n")
    tsl.chmod(tsl.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return {
        "HOME": str(home),
        "PATH": f"{fakebin}{os.pathsep}{SYSTEM_PATH}",
        "CLAUDE_PLUGIN_ROOT": str(PLUGIN),
        "TMPDIR": str(tmp_path),
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


def missing(env: dict[str, str]) -> dict[str, str]:
    e = dict(env)
    e["PATH"] = SYSTEM_PATH
    return e


def assert_deny(cp: subprocess.CompletedProcess[str]) -> dict[str, object]:
    assert cp.returncode == 0, cp.stderr
    out = json.loads(cp.stdout)
    hso = out["hookSpecificOutput"]
    assert hso["hookEventName"] == "PreToolUse"
    assert hso["permissionDecision"] == "deny"
    assert str(hso["permissionDecisionReason"]).startswith("E-HOOK-01 ")
    return out


# ------------------------------------------------------------------------------------- tsl missing
@pytest.mark.parametrize("shell", SHELLS)
@pytest.mark.parametrize("event", ["pre-tool", "pre-mcp"])
def test_missing_tsl_in_run_fails_closed(env: dict[str, str], companion: Path, event: str, shell: str) -> None:
    lock(companion)
    cp = run(missing(env), event, hook_input(companion, event), shell=shell)
    out = assert_deny(cp)
    assert f"Install tsl {PLUGIN_VERSION}" in str(out["hookSpecificOutput"]["permissionDecisionReason"])  # type: ignore[index]


@pytest.mark.parametrize("shell", SHELLS)
@pytest.mark.parametrize("event", ["pre-tool", "pre-mcp"])
def test_missing_tsl_out_of_run_fails_open(env: dict[str, str], companion: Path, event: str, shell: str) -> None:
    cp = run(missing(env), event, hook_input(companion, event), shell=shell)
    assert cp.returncode == 0, cp.stderr
    assert cp.stdout == "", "allow = exit 0 with no output"


def test_missing_tsl_outside_any_companion_repo_fails_open(env: dict[str, str], tmp_path: Path) -> None:
    elsewhere = tmp_path / "scratch"
    elsewhere.mkdir()
    cp = run(missing(env), "pre-tool", hook_input(elsewhere, "pre-tool"))
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
    assert_deny(run(missing(env), "pre-tool", hook_input(product, "pre-tool", session="sess-0042")))
    lk.unlink()
    cp = run(missing(env), "pre-tool", hook_input(product, "pre-tool", session="sess-0042"))
    assert cp.returncode == 0 and cp.stdout == ""


def test_session_id_with_path_characters_is_not_used_as_a_path(env: dict[str, str], tmp_path: Path) -> None:
    product = tmp_path / "p"
    product.mkdir()
    cp = run(missing(env), "pre-tool", hook_input(product, "pre-tool", session="../../etc/passwd"))
    assert cp.returncode == 0 and cp.stdout == ""


@pytest.mark.parametrize("in_run", [True, False])
def test_missing_tsl_post_write_fails_open_with_a_warning(env: dict[str, str], companion: Path, in_run: bool) -> None:
    if in_run:
        lock(companion)
    cp = run(missing(env), "post-write", hook_input(companion, "post-write"))
    assert cp.returncode == 0
    out = json.loads(cp.stdout)
    assert set(out) == {"systemMessage"}
    assert "Your file was kept" in out["systemMessage"]


@pytest.mark.parametrize("event", ["session-start", "session-end"])
def test_session_hooks_warn_when_tsl_is_missing(env: dict[str, str], companion: Path, event: str) -> None:
    cp = run(missing(env), event, hook_input(companion, event))
    assert cp.returncode == 0
    msg = json.loads(cp.stdout)["systemMessage"]
    assert f"Install tsl {PLUGIN_VERSION}" in msg and "uv tool install" in msg


def test_missing_tsl_is_logged_locally(env: dict[str, str], companion: Path) -> None:
    lock(companion)
    run(missing(env), "pre-mcp", hook_input(companion, "pre-mcp"))
    log = (Path(env["HOME"]) / ".truminds" / "logs" / "hook.log").read_text(encoding="utf-8")
    assert "event=pre-mcp decision=deny code=E-HOOK-01" in log


def test_no_temp_files_are_left_behind(env: dict[str, str], companion: Path, tmp_path: Path) -> None:
    lock(companion)
    run(missing(env), "pre-tool", hook_input(companion, "pre-tool"))
    run(env, "pre-tool", hook_input(companion, "pre-tool"))
    assert not list(tmp_path.glob("tsl-hook.*"))


# ------------------------------------------------------------------------------------- pass-through (exec)
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


def test_backslash_paths_in_stdin_reach_tsl_unchanged(env: dict[str, str], tmp_path: Path) -> None:
    copy = tmp_path / "stdin-copy.json"
    payload = json.dumps({"session_id": "s", "cwd": "C:\\Users\\a b\\repo", "tool_name": "Read"})
    cp = run(env, "pre-tool", payload, FAKE_TSL_STDIN_COPY=str(copy))
    assert cp.returncode == 0
    assert json.loads(copy.read_text(encoding="utf-8"))["cwd"] == "C:\\Users\\a b\\repo"


def test_launcher_runs_tsl_once_and_hands_it_the_plugin_root(env: dict[str, str], tmp_path: Path) -> None:
    argv = tmp_path / "argv.txt"
    cp = run(env, "pre-tool", "{}", FAKE_TSL_ARGV_COPY=str(argv))
    assert cp.returncode == 0
    args, _pid = argv.read_text(encoding="utf-8").strip().split("|")
    assert args == f"hook-run pre-tool --plugin-root {PLUGIN}"


def test_inherited_tsl_plugin_root_is_ignored(env: dict[str, str], tmp_path: Path) -> None:
    argv = tmp_path / "argv.txt"
    run(env, "pre-tool", "{}", FAKE_TSL_ARGV_COPY=str(argv), TSL_PLUGIN_ROOT="/elsewhere")
    assert "/elsewhere" not in argv.read_text(encoding="utf-8")


# ------------------------------------------------------------------------------------- tsl dies (non-zero exit)
@pytest.mark.parametrize("shell", SHELLS)
@pytest.mark.parametrize("event", ["pre-tool", "pre-mcp"])
@pytest.mark.parametrize("fake", [{"FAKE_TSL_EXIT": "1"}, {"FAKE_TSL_OLD": "1"}], ids=["crash", "old-tsl"])
def test_tsl_dying_in_a_run_fails_closed(
    env: dict[str, str], companion: Path, event: str, shell: str, fake: dict[str, str]
) -> None:
    lock(companion)
    cp = run(env, event, hook_input(companion, event), shell=shell, cwd=companion, **fake)
    assert_deny(cp)
    log = (Path(env["HOME"]) / ".truminds" / "logs" / "hook.log").read_text(encoding="utf-8")
    assert f"event={event} decision=deny code=E-HOOK-01" in log


@pytest.mark.parametrize("fake", [{"FAKE_TSL_EXIT": "1"}, {"FAKE_TSL_OLD": "1"}], ids=["crash", "old-tsl"])
def test_tsl_dying_out_of_a_run_fails_open(env: dict[str, str], companion: Path, fake: dict[str, str]) -> None:
    cp = run(env, "pre-tool", hook_input(companion, "pre-tool"), cwd=companion, **fake)
    assert cp.returncode == 0 and cp.stdout == ""


def test_post_write_when_tsl_dies_warns_and_exits_zero(env: dict[str, str], companion: Path) -> None:
    cp = run(env, "post-write", hook_input(companion, "post-write"), cwd=companion, FAKE_TSL_EXIT="1")
    assert cp.returncode == 0 and "systemMessage" in cp.stdout


def test_launcher_hot_path_uses_no_external_commands() -> None:
    """Everything before the first `exec` runs on every tool call: builtins only."""
    text = LAUNCHER.read_text(encoding="utf-8")
    hot = text[: text.index("# ----", text.index('"$c" hook-run'))]
    for tool in ("sed ", "date ", "dirname", "mktemp", "cat ", "head ", "$(", "`", "tsl --version"):
        assert tool not in hot.split("\n\n", 1)[1], tool


def test_unknown_event_is_rejected(env: dict[str, str], companion: Path) -> None:
    cp = run(env, "pre-everything", "{}")
    assert cp.returncode == 1 and cp.stdout == ""
