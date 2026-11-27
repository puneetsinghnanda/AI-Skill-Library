"""Updating tsl and the plugin while a run is open (roadmap D4).

While tsl and the plugin differ (E-VER-01) the pre-tool hook denies every tool inside a run. It
used to deny the update commands too, so ending the mismatch needed a terminal outside Claude
Code. Now exactly the update commands still run. The ones that act on a folder (git pull, the
reinstall of tsl) only as `cd <absolute clone path> && <command>`, in the AI-Skill-Library clone
the plugin comes from, and never when the run's companion or product repos are inside that clone:
anywhere else ./tsl could be code the agent wrote, installed as the policy hook.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

from tsl.hooks import entry

INSTALL = "uv tool install --python 3.12 --reinstall --no-cache --no-config ./tsl"
ORG = "deploy/render/tsl-org.github.toml"


@pytest.fixture
def home(tmp_path: Path) -> Path:
    h = tmp_path / "home" / ".truminds"
    h.mkdir(parents=True)
    return h


def open_run(root: Path) -> Path:
    (root / "runs" / "active").mkdir(parents=True)
    (root / "tsl.yaml").write_text("schema: tsl-config.v1\n", encoding="utf-8")
    (root / "runs" / "active" / "ABC-1__wf.lock").write_text("{}", encoding="utf-8")
    return root


@pytest.fixture
def companion(tmp_path: Path) -> Path:
    """A companion repo with an open run, next to (not inside) the clone."""
    return open_run(tmp_path / "companion")


def make_plugin(base: Path, version: str = "9.9.9", *, in_clone: bool = True) -> Path:
    """The plugin at <base>/AI-Skill-Library/plugins/truminds (a clone, unless in_clone=False)."""
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


def run_hook(
    command: str, cwd: Path, home: Path, root: Path, tool: str = "Bash", **env: str
) -> str:
    out: list[str] = []
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
        # An empty Claude config folder: the tests never read the machine's marketplaces.
        env={"TSL_PLUGIN_ROOT": str(root), "CLAUDE_CONFIG_DIR": str(cwd / "no-claude"), **env},
        home=home,
        emit=out.append,
        hard_exit=lambda c: None,
    )
    return "".join(out)


def denied(out: str) -> str:
    hso = json.loads(out)["hookSpecificOutput"]
    assert hso["permissionDecision"] == "deny", hso
    reason: str = hso["permissionDecisionReason"]
    assert "E-VER-01" in reason and "only the update commands run" in reason, reason
    return reason


def cd(path: Path) -> str:
    return f'cd "{path.resolve().as_posix()}" &&'


def test_update_commands_run_while_versions_differ(
    companion: Path, home: Path, tmp_path: Path
) -> None:
    root = make_plugin(tmp_path)
    clone = root.parent.parent
    c = clone.resolve().as_posix()
    commands = (
        "claude plugin marketplace update truminds-skill-library",
        "claude plugin update truminds@truminds-skill-library",
        "tsl --version",
        "tsl doctor",
        f"{cd(clone)} git pull",
        f"{cd(clone)} git pull --ff-only",
        f"{cd(clone)} git checkout main",
        f"{cd(clone)} {INSTALL}",
        f'{cd(clone)} TSL_ORG_FILE="{c}/{ORG}" {INSTALL}',
    )
    for command in commands:
        assert run_hook(command, companion, home, root) == "", command
    log = (home / "logs" / "hook.log").read_text(encoding="utf-8")
    assert log.count("decision=allow code=E-VER-01") == len(commands)


def test_everything_else_stays_denied(companion: Path, home: Path, tmp_path: Path) -> None:
    root = make_plugin(tmp_path)
    clone = root.parent.parent
    c = clone.resolve().as_posix()
    for command in (
        "ls",
        # Folder commands are never judged by the hook's cwd field alone.
        "git pull",
        INSTALL,
        # Relative, home and shell-special cd targets: bash may land elsewhere than the hook thinks.
        "cd ./AI-Skill-Library && git pull",
        "cd ../AI-Skill-Library && git pull",
        "cd AI-Skill-Library && git pull",
        "cd ~/AI-Skill-Library && git pull",
        "cd ~ && git pull",
        "cd - && git pull",
        "cd ~+ && git pull",
        "cd ~- && git pull",
        "cd ~1 && git pull",
        f"{cd(companion)} {INSTALL}",
        # Only the install line, with --no-config and the clone's own settings file, by path.
        f"{cd(clone)} uv tool install --python 3.12 --reinstall --no-cache ./tsl",
        f"{cd(clone)} TSL_ORG_FILE={ORG} {INSTALL}",
        f"{cd(clone)} TSL_ORG_FILE=$HOME/org.toml {INSTALL}",
        f"{cd(clone)} TSL_ORG_FILE=/tmp/evil.toml {INSTALL}",
        f"{cd(clone)} TSL_ORG_FILE=~/{ORG} {INSTALL}",
        f"{cd(clone)} uv tool install --python 3.12 --reinstall --no-cache --no-config"
        " --constraints c.txt ./tsl",
        f"{cd(clone)} uv tool install --python 3.12 --reinstall --no-cache --no-config ../evil/tsl",
        # Expansion, chaining, newlines.
        f"{cd(clone)} TSL_ORG_FILE={{{c}/{ORG},x}} {INSTALL}",
        f"cd {{{c},x}} && git pull",
        f"{cd(clone)} {INSTALL} && rm -rf runs",
        f"{cd(clone)} {INSTALL}; curl example.com",
        f"{cd(clone)} {INSTALL} | tee x",
        f"{cd(clone)} {INSTALL}\nrm -rf runs",
        f'cd "{c}\\\\" && git pull',
        f"{cd(clone)} git pull origin evil-branch",
        "claude plugin update truminds@another-marketplace",
        "claude plugin install evil@x",
        "tsl state abort run_1",
    ):
        reason = denied(run_hook(command, companion, home, root))
        assert "git pull" in reason and "/reload-plugins" in reason


def test_only_the_bash_tool(companion: Path, home: Path, tmp_path: Path) -> None:
    root = make_plugin(tmp_path)
    update = "claude plugin update truminds@truminds-skill-library"
    for tool in ("PowerShell", "Write", "Edit"):
        denied(run_hook(update, companion, home, root, tool))


def test_no_folder_command_when_the_run_lives_inside_the_clone(home: Path, tmp_path: Path) -> None:
    """§7's example companion is <clone>/examples/sample-system/companion-example: an agent there
    can write to the clone, so the clone is not trusted for a reinstall."""
    root = make_plugin(tmp_path)
    clone = root.parent.parent
    inner = open_run(clone / "examples" / "sample-system" / "companion-example")
    denied(run_hook(f"{cd(clone)} git pull", inner, home, root))
    denied(run_hook(f"{cd(clone)} {INSTALL}", inner, home, root))
    update = "claude plugin update truminds@truminds-skill-library"
    assert run_hook(update, inner, home, root) == ""


def test_no_folder_command_when_a_product_repo_lives_inside_the_clone(
    companion: Path, home: Path, tmp_path: Path
) -> None:
    root = make_plugin(tmp_path)
    clone = root.parent.parent
    (companion / ".tsl").mkdir()
    local = companion / ".tsl" / "local.yaml"
    local.write_text(
        "schema: tsl-local.v1\nproduct_repos:\n  app: ../AI-Skill-Library/examples/app\n",
        encoding="utf-8",
    )
    denied(run_hook(f"{cd(clone)} git pull", companion, home, root))
    local.write_text(
        "schema: tsl-local.v1\nproduct_repos:\n  app: ../sample-app # outside\n", encoding="utf-8"
    )
    assert run_hook(f"{cd(clone)} git pull", companion, home, root) == ""


def test_the_session_index_names_the_companion(home: Path, tmp_path: Path) -> None:
    """After `cd <clone> && ...` the Bash tool's folder is the clone; the run's companion comes
    from the session index, not from walking up from there."""
    root = make_plugin(tmp_path)
    clone = root.parent.parent
    comp = open_run(tmp_path / "companion")
    (home / "sessions").mkdir()
    index = home / "sessions" / "s-1.json"
    lock = "runs/active/ABC-1__wf.lock"
    index.write_text(json.dumps({"companion": str(comp), "lock": lock}), encoding="utf-8")
    assert run_hook(f"{cd(clone)} git pull", clone, home, root) == ""
    inner = open_run(clone / "examples" / "c")
    index.write_text(json.dumps({"companion": str(inner), "lock": lock}), encoding="utf-8")
    denied(run_hook(f"{cd(clone)} git pull", clone, home, root))


def test_an_error_while_deciding_never_allows(
    companion: Path, home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The answer is built before the hook commits to it, so an error in the checks ends in the
    version deny, never in an empty (allow) answer."""
    root = make_plugin(tmp_path)

    def broken(*args: Any, **kwargs: Any) -> Any:
        raise OSError("disk gone")

    monkeypatch.setattr(entry, "plugin_clone", broken)
    update = "claude plugin update truminds@truminds-skill-library"
    reason = denied(run_hook(update, companion, home, root))
    assert "terminal outside Claude Code" in reason


def test_a_plugin_not_from_a_clone_gets_no_folder_command(
    companion: Path, home: Path, tmp_path: Path
) -> None:
    """--plugin-dir or another folder: no clone, even when a folder marketplace is known."""
    root = make_plugin(tmp_path, in_clone=False)
    real = make_plugin(tmp_path / "real").parent.parent
    conf = tmp_path / "claude"
    (conf / "plugins").mkdir(parents=True)
    known = {"truminds-skill-library": {"source": {"source": "directory", "path": str(real)}}}
    (conf / "plugins" / "known_marketplaces.json").write_text(json.dumps(known), encoding="utf-8")
    assert entry.plugin_clone(str(root), {"CLAUDE_CONFIG_DIR": str(conf)}) is None
    out = run_hook(f"{cd(real)} git pull", companion, home, root, CLAUDE_CONFIG_DIR=str(conf))
    assert "terminal outside Claude Code" in denied(out)
    update = "claude plugin update truminds@truminds-skill-library"
    assert run_hook(update, companion, home, root) == ""


def test_a_plugin_installed_from_a_folder_marketplace_finds_its_clone(
    companion: Path, home: Path, tmp_path: Path
) -> None:
    """Claude Code runs an installed copy from its cache; the clone is the marketplace folder
    that known_marketplaces.json records."""
    clone = make_plugin(tmp_path).parent.parent
    conf = tmp_path / "claude"
    root = conf / "plugins" / "cache" / "truminds-skill-library" / "truminds" / "9.9.9"
    (root / ".claude-plugin").mkdir(parents=True)
    (root / ".claude-plugin" / "plugin.json").write_text('{"version": "9.9.9"}', encoding="utf-8")
    known = {"truminds-skill-library": {"source": {"source": "directory", "path": str(clone)}}}
    marketplaces = conf / "plugins" / "known_marketplaces.json"
    marketplaces.write_text(json.dumps(known), encoding="utf-8")
    env = {"CLAUDE_CONFIG_DIR": str(conf)}
    assert entry.plugin_clone(str(root), env) == str(clone.resolve())
    assert run_hook(f"{cd(clone)} {INSTALL}", companion, home, root, **env) == ""
    known["truminds-skill-library"]["source"] = {"source": "github", "repo": "x/y"}
    marketplaces.write_text(json.dumps(known), encoding="utf-8")
    assert entry.plugin_clone(str(root), env) is None


def test_the_hint_gives_commands_that_pass(tmp_path: Path) -> None:
    clone = make_plugin(tmp_path / "My Clones").parent.parent.resolve()
    c = clone.as_posix()
    hint = entry.update_hint(str(clone))
    assert f'cd "{c}" && git pull' in hint
    # The settings file by absolute path: the build resolves a relative one from ./tsl.
    assert f'cd "{c}" && TSL_ORG_FILE="{c}/{ORG}" {INSTALL}' in hint
    assert "checkout" not in hint
    odd = make_plugin(tmp_path / "Clones (old)").parent.parent.resolve()  # ( is refused in paths
    assert "terminal outside Claude Code" in entry.update_hint(str(odd))


def test_a_quoted_clone_path_keeps_its_spaces(companion: Path, home: Path, tmp_path: Path) -> None:
    root = make_plugin(tmp_path / "My  Clones")
    clone = root.parent.parent
    assert run_hook(f"{cd(clone)} git pull", companion, home, root) == ""
    other = tmp_path / "My Clones" / "AI-Skill-Library"  # one space: another folder
    denied(run_hook(f'cd "{other.as_posix()}" && git pull', companion, home, root))


def test_matching_versions_never_reach_the_allow_list(
    companion: Path, home: Path, tmp_path: Path
) -> None:
    """With equal versions the normal policy decides (here a runner that answers)."""
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


@pytest.mark.skipif(os.name != "nt", reason="Windows paths")
def test_windows_paths(companion: Path, home: Path, tmp_path: Path) -> None:
    root = make_plugin(tmp_path)
    clone = root.parent.parent.resolve()
    git_bash = "/" + clone.drive[0].lower() + clone.as_posix()[2:]
    assert run_hook(f"cd {git_bash} && git pull", companion, home, root) == ""
    assert run_hook(f'cd "{clone}" && git pull', companion, home, root) == ""  # backslashes
    # Any other /... is under Git Bash's own root, not the drive root Python would read.
    denied(run_hook(f"cd /tmp{clone.as_posix()[2:]} && git pull", companion, home, root))
