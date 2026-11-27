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


def _append(
    w: World,
    run_id: str,
    target: str,
    read_only: bool | None,
    decision: str = "allow",
    code: str | None = None,
) -> None:
    import json

    line = {
        "ts": iso(w.clock()),
        "session_id": "sess-setup",
        "step": "req",
        "attempt": 1,
        "tool": "Bash",
        "target": target,
        "decision": decision,
        "code": code,
    }
    if read_only is not None:
        line["read_only"] = read_only
    p = w.companion / "runs" / run_id / "tool-log.jsonl"
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(line, sort_keys=True) + "\n")


def test_refused_before_it_ran_is_logged_but_not_held_against_the_step(world: World) -> None:
    run_id = start_run(world)
    res = do_req_step(world, run_id, until="written")
    _append(world, run_id, "docker info", read_only=None, decision="deny", code="E-POL-06")
    h7 = _h7(world, res["artifact"])
    assert h7["status"] == "pass", h7
    # A deny the hook did not refuse up front (here a write outside scope) still fails H7.
    _append(world, run_id, "rm -rf api", read_only=None, decision="deny", code="E-POL-01")
    h7 = _h7(world, res["artifact"])
    assert h7["status"] == "fail" and h7["codes"] == ["E-POL-01"], h7


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


def test_step_runner_bash_is_only_its_own_tsl_commands() -> None:
    # B1: the forked step runner may not run the run loop (next, review, decide, pr).
    runner = "truminds:step-runner"
    allowed = ["Read", "Write", "Bash(tsl verify *)"]
    for target in (
        "tsl verify artifacts/x.md --json",
        "tsl step brief artifacts/x.md --context full",
    ):
        assert _tool_allowed({"tool": "Bash", "target": target, "agent_type": runner}, allowed)
    for target in ("tsl decide artifacts/x.md --json", "tsl next r1 --json", "tsl pr r1"):
        assert _tool_allowed({"tool": "Bash", "target": target}, allowed)  # main session
        assert not _tool_allowed({"tool": "Bash", "target": target, "agent_type": runner}, allowed)
    # One command only: fnmatch's * would match a chained run-loop command after it.
    for target in (
        "tsl verify artifacts/x.md --json && tsl decide artifacts/x.md --json",
        "tsl verify artifacts/x.md; tsl next r1",
        "tsl verify artifacts/x.md | tsl pr r1",
        "tsl verify $(tsl decide a.md)",
    ):
        assert not _tool_allowed({"tool": "Bash", "target": target, "agent_type": runner}, allowed)


def test_a_refused_read_line_does_not_break_h7(world: World) -> None:
    # B1 review: refusals of any tool (Read, WebFetch ...) are logged; tool-log.v1 must accept
    # them, or H7 fails the run with E-POL-05 on every later verify.
    import json

    run_id = start_run(world)
    res = do_req_step(world, run_id, until="written")
    line = {
        "ts": iso(world.clock()),
        "session_id": "sess-setup",
        "step": "req",
        "attempt": 1,
        "tool": "Read",
        "target": "runs/run_x/state.json",
        "decision": "deny",
        "code": "E-POL-06",
    }
    p = world.companion / "runs" / run_id / "tool-log.jsonl"
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(line, sort_keys=True) + "\n")
    h7 = _h7(world, res["artifact"])
    assert h7["status"] == "pass", h7


def test_step_runner_run_loop_command_fails_h7(world: World) -> None:
    import json

    run_id = start_run(world)
    res = do_req_step(world, run_id, until="written")
    p = world.companion / "runs" / run_id / "tool-log.jsonl"
    line = {
        "ts": iso(world.clock()),
        "session_id": "sess-setup",
        "step": "req",
        "attempt": 1,
        "tool": "Bash",
        "target": f"tsl decide {res['artifact']} --json",
        "decision": "allow",
        "code": None,
        "agent_type": "truminds:step-runner",
    }
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(line, sort_keys=True) + "\n")
    h7 = _h7(world, res["artifact"])
    assert h7["status"] == "fail" and h7["codes"] == ["E-POL-04"], h7


def test_only_the_pre_tool_refusal_logs_deny_e_pol_06() -> None:
    # H7 skips deny/E-POL-06 lines as "never ran"; any other writer of that pair would let an
    # executed call past H7 unseen.
    import re
    from pathlib import Path

    import tsl

    src = Path(tsl.__file__).parent
    pat = re.compile(r"""["']deny["']\s*,\s*["']E-POL-06["']""")
    hits = [p for p in src.rglob("*.py") if pat.search(p.read_text(encoding="utf-8"))]
    assert [p.relative_to(src).as_posix() for p in hits] == ["hooks/pre_tool.py"]
    text = (src / "hooks" / "pre_tool.py").read_text(encoding="utf-8")
    assert len(pat.findall(text)) == 1
    assert pat.search(text[text.index("def _refuse(") : text.index("def _target(")])
