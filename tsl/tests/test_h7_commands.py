"""H7: safe environment prefixes on tsl commands, and read-only slips retry instead of aborting."""

from __future__ import annotations

import pytest

from e2e_steps import SESSION, do_req_step, start_run
from helpers import World
from test_tool_log_window import _h7
from tsl.core.clock import iso
from tsl.harness.commands import is_read_only, strip_safe_env
from tsl.harness.gates import _tool_allowed


@pytest.mark.parametrize(
    "cmd",
    [
        "cat context/manifest.json",
        "grep -n PatientsPage context/generated/module-map.json | head -5",
        "PYTHONIOENCODING=utf-8 ls runs",
        "git log --oneline -3",
        "git -C ../sample-system show HEAD:api/src/types.ts",
        "find api -name '*.ts'",
    ],
)
def test_read_only_commands(cmd: str) -> None:
    assert is_read_only(cmd)


@pytest.mark.parametrize(
    "cmd",
    [
        "cat a > b",
        "ls; rm -rf x",
        "ls && touch x",
        "cat a | tee b",
        "echo $(id)",
        "find . -delete",
        "find . -exec rm {} ;",
        "git commit -m x",
        "git diff --output=patch.txt",
        "git -c core.pager=./x log",
        "rg --pre ./script x",
        "sort -o out a",
        "python -c 'print(1)'",
        "PATH=/tmp/evil ls",
        "npm install",
        "",
    ],
)
def test_not_read_only_commands(cmd: str) -> None:
    assert not is_read_only(cmd)


def test_safe_env_prefix_is_stripped_and_unsafe_one_is_refused() -> None:
    assert strip_safe_env("PYTHONIOENCODING=utf-8 NO_COLOR=1 tsl verify a.md") == "tsl verify a.md"
    assert strip_safe_env("PATH=/x tsl verify a.md") is None


def test_tsl_with_a_safe_prefix_matches_the_skill_pattern() -> None:
    allowed = ["Read", "Write", "Bash(tsl verify *)"]
    entry = {"tool": "Bash", "target": "PYTHONIOENCODING=utf-8 tsl verify artifacts/x.md"}
    assert _tool_allowed(entry, allowed)
    assert not _tool_allowed({"tool": "Bash", "target": "PATH=/x tsl verify a"}, allowed)


def _append(w: World, run_id: str, target: str, read_only: bool | None) -> None:
    import json

    line = {
        "ts": iso(w.clock()),
        "session_id": "sess-setup",
        "step": "req",
        "attempt": 1,
        "tool": "Bash",
        "target": target,
        "decision": "allow",
        "code": None,
    }
    if read_only is not None:
        line["read_only"] = read_only
    p = w.companion / "runs" / run_id / "tool-log.jsonl"
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(line, sort_keys=True) + "\n")


def test_read_only_slip_retries_instead_of_aborting(world: World) -> None:
    run_id = start_run(world)
    res = do_req_step(world, run_id, until="written")
    _append(world, run_id, "cat context/glossary.md", read_only=True)
    h7 = _h7(world, res["artifact"])
    assert h7["status"] == "fail" and h7["codes"] == ["E-POL-06"], h7
    world.cli(
        ["review", "record", res["artifact"], "--unavailable", "H7 failed", "--json"],
        session=SESSION,
    )
    _code, dec, _, err = world.cli(["decide", res["artifact"], "--json"], session=SESSION)
    assert dec is not None and dec["data"]["outcome"] == "RETRY", (dec, err)


def test_writing_command_still_aborts(world: World) -> None:
    run_id = start_run(world)
    res = do_req_step(world, run_id, until="written")
    _append(world, run_id, "npm install", read_only=False)
    h7 = _h7(world, res["artifact"])
    assert "E-POL-04" in h7["codes"], h7
