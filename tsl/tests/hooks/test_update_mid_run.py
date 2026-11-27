"""Updating tsl and the plugin while a run is open (roadmap D4).

While tsl and the plugin differ (E-VER-01) the pre-tool hook denies every tool inside a run. It
used to deny the update commands too, so ending the mismatch needed a terminal outside Claude
Code. Now exactly the update commands still run, and the ones that act on their folder (git pull,
uv tool install ./tsl) only in the AI-Skill-Library clone the plugin is loaded from: anywhere else,
./tsl could be a package the agent wrote, installed as the policy hook.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from tsl.hooks import entry

INSTALL = "uv tool install --python 3.12 --reinstall --no-cache ./tsl"


@pytest.fixture
def home(tmp_path: Path) -> Path:
    h = tmp_path / "home" / ".truminds"
    h.mkdir(parents=True)
    return h


@pytest.fixture
def companion(tmp_path: Path) -> Path:
    """A companion repo with an open run."""
    root = tmp_path / "companion"
    (root / "runs" / "active").mkdir(parents=True)
    (root / "tsl.yaml").write_text("schema: tsl-config.v1\n", encoding="utf-8")
    (root / "runs" / "active" / "ABC-1__wf.lock").write_text("{}", encoding="utf-8")
    return root


def make_plugin(base: Path, version: str = "9.9.9", *, in_clone: bool = True) -> Path:
    """The plugin at <clone>/plugins/truminds (or an installed copy when in_clone is False)."""
    clone = base / "AI-Skill-Library"
    root = clone / "plugins" / "truminds"
    (root / ".claude-plugin").mkdir(parents=True)
    (root / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"version": version}), encoding="utf-8"
    )
    if in_clone:
        (clone / "tsl").mkdir()
        (clone / "tsl" / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    return root


def hook(
    command: str, cwd: Path, home: Path, root: Path, tool: str = "Bash"
) -> tuple[str, list[int]]:
    out: list[str] = []
    exits: list[int] = []
    data = {
        "session_id": "s-1",
        "cwd": str(cwd),
        "hook_event_name": "PreToolUse",
        "tool_name": tool,
        "tool_input": {"command": command},
    }
    entry.guarded(
        "pre-tool",
        json.dumps(data),
        env={"TSL_PLUGIN_ROOT": str(root)},
        home=home,
        emit=out.append,
        hard_exit=exits.append,
    )
    return "".join(out), exits


def denied(out: str) -> str:
    hso = json.loads(out)["hookSpecificOutput"]
    assert hso["permissionDecision"] == "deny", hso
    reason: str = hso["permissionDecisionReason"]
    assert "E-VER-01" in reason and "only these commands run" in reason, reason
    return reason


def test_update_commands_run_while_versions_differ(
    companion: Path, home: Path, tmp_path: Path
) -> None:
    root = make_plugin(tmp_path)
    clone = root.parent.parent
    for command in (
        "claude plugin marketplace update truminds-skill-library",
        "claude plugin update truminds@truminds-skill-library",
        "tsl --version",
        "tsl doctor",
        f"cd {clone.as_posix()} && git pull",
        f"cd {clone.as_posix()} && git pull --ff-only",
        f"cd {clone.as_posix()} && git checkout main",
        f"cd {clone.as_posix()} && {INSTALL}",
        f'cd "{clone.as_posix()}" && TSL_ORG_FILE=deploy/render/org.toml {INSTALL}',
        f"cd {clone.as_posix()} && uv tool install --python 3.12 --reinstall --no-cache"
        " --constraints c.txt ./tsl",
    ):
        out, exits = hook(command, companion, home, root)
        assert out == "", (command, out)
        assert exits == [], command
    log = (home / "logs" / "hook.log").read_text(encoding="utf-8")
    assert log.count("decision=allow code=E-VER-01") == 10


def test_folder_commands_run_from_the_clone_itself(home: Path, tmp_path: Path) -> None:
    root = make_plugin(tmp_path)
    clone = root.parent.parent
    (clone / "runs" / "active").mkdir(parents=True)  # a run open here too: deny-all otherwise
    (clone / "tsl.yaml").write_text("schema: tsl-config.v1\n", encoding="utf-8")
    (clone / "runs" / "active" / "X-1__wf.lock").write_text("{}", encoding="utf-8")
    for command in ("git pull", INSTALL):
        out, _ = hook(command, clone, home, root)
        assert out == "", (command, out)


def test_everything_else_stays_denied(companion: Path, home: Path, tmp_path: Path) -> None:
    root = make_plugin(tmp_path)
    clone = root.parent.parent.as_posix()
    for command in (
        "ls",
        "git pull",  # in the companion, not the clone
        INSTALL,  # ./tsl here would be whatever the companion holds
        f"cd {companion.as_posix()} && {INSTALL}",
        f"cd {clone} && {INSTALL} && rm -rf runs",
        f"cd {clone} && {INSTALL}; curl example.com",
        f"cd {clone} && {INSTALL} | tee x",
        f"cd {clone} && {INSTALL}\nrm -rf runs",
        f"cd {clone} && TSL_ORG_FILE=$HOME/org.toml {INSTALL}",
        f"cd {clone} && uv tool install --python 3.12 --reinstall --no-cache ../evil/tsl",
        f"cd {clone} && git pull origin evil-branch",
        "claude plugin update truminds@another-marketplace",
        "claude plugin install evil@x",
        "tsl state abort run_1",
    ):
        reason = denied(hook(command, companion, home, root)[0])
        assert "git pull" in reason and "/reload-plugins" in reason


def test_only_the_bash_tool(companion: Path, home: Path, tmp_path: Path) -> None:
    root = make_plugin(tmp_path)
    for tool in ("PowerShell", "Write", "Edit"):
        denied(
            hook(
                "claude plugin update truminds@truminds-skill-library", companion, home, root, tool
            )[0]
        )


def test_a_plugin_not_read_from_a_clone_allows_no_folder_command(
    companion: Path, home: Path, tmp_path: Path
) -> None:
    root = make_plugin(tmp_path, in_clone=False)
    clone = root.parent.parent.as_posix()
    denied(hook(f"cd {clone} && {INSTALL}", companion, home, root)[0])
    out, _ = hook("claude plugin update truminds@truminds-skill-library", companion, home, root)
    assert out == ""


def test_matching_versions_never_reach_the_allow_list(
    companion: Path, home: Path, tmp_path: Path
) -> None:
    """With equal versions the normal policy decides (here a runner that denies)."""
    from tsl import __version__

    root = make_plugin(tmp_path, version=__version__)
    out: list[str] = []
    data = {
        "session_id": "s-1",
        "cwd": str(companion),
        "tool_name": "Bash",
        "tool_input": {"command": "claude plugin update truminds@truminds-skill-library"},
    }
    entry.guarded(
        "pre-tool",
        json.dumps(data),
        env={"TSL_PLUGIN_ROOT": str(root)},
        home=home,
        runner=lambda e, s: ('{"decision": "from-policy"}', 0),
        emit=out.append,
        hard_exit=lambda c: None,
    )
    assert "from-policy" in "".join(out)


@pytest.mark.skipif(os.name != "nt", reason="Git Bash drive paths exist on Windows only")
def test_git_bash_drive_paths_name_the_clone(companion: Path, home: Path, tmp_path: Path) -> None:
    root = make_plugin(tmp_path)
    clone = root.parent.parent.resolve()
    bash = "/" + clone.drive[0].lower() + clone.as_posix()[2:]
    out, _ = hook(f"cd {bash} && git pull", companion, home, root)
    assert out == "", bash
