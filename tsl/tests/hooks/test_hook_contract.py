"""Golden stdin/stdout contracts for `tsl hook <event>` (SDD-05 §5, SDD-04 §6.14).

Each fixture pair is `<case>.stdin.json` (what Claude Code sends) and `<case>.expect.json`
(setup, exit code, exact stdout, hook.log decision and the hook.decision event body).
Placeholders {companion}, {product} and {run_id} are filled from the temp world.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from e2e_steps import SESSION, next_action, start_run
from helpers import World, git, intent_artifact, ticket_snapshot
from tsl.approvals import approvals_md
from tsl.hooks.dispatch import run as run_hook
from tsl.schemas.registry import errors, event_schema_id

FIX = Path(__file__).parent / "fixtures"
CASES = sorted(p for p in FIX.glob("*/*.stdin.json"))


def _fill(obj: Any, subs: dict[str, str]) -> Any:
    text = json.dumps(obj)
    for k, v in subs.items():
        text = text.replace("{" + k + "}", v)
    return json.loads(text)


def _artifact(w: World, run_id: str, *, bad: bool) -> None:
    code, env = next_action(w, run_id)
    assert code == 0 and env["data"]["action"] == "run_skill", env
    art = env["data"]["artifact_path"]
    ticket_rel = f"artifacts/ABC-142/{run_id}/ticket.md"
    tp = w.companion / ticket_rel
    tp.parent.mkdir(parents=True, exist_ok=True)
    tp.write_text(ticket_snapshot(run_id), encoding="utf-8")
    code, inp, _, err = w.cli(["verify", art, "--inputs", "--json"], session=SESSION)
    assert code == 0 and inp is not None, err
    text = intent_artifact(
        inp["data"]["envelope"], ticket_rel, drop_section="Unknown" if bad else None
    )
    rt = w.rt("eng", SESSION)
    pre = {
        "session_id": SESSION,
        "cwd": str(w.companion),
        "tool_name": "Write",
        "tool_input": {"file_path": str(w.companion / art)},
    }
    assert run_hook(
        "pre-tool", json.dumps(pre), env=rt.env, home=rt.home.root, rt_factory=lambda: rt
    ) == ("", 0)
    (w.companion / art).write_text(text, encoding="utf-8")


def _approval(w: World, run_id: str) -> None:
    path = w.companion / f"runs/{run_id}/approvals.md"
    approvals_md.append_entry(
        path,
        run_id,
        "W-1",
        "tech_lead",
        "external_write",
        [],
        "Post the review summary on the ticket",
        action={"tool": "mcp__jira__add_comment", "target": "ABC-142"},
    )
    path.write_text(
        path.read_text().replace(
            "decision:          # approve | reject | changes | abort", "decision: approve"
        )
    )
    git(w.companion, "add", "-A")
    git(w.companion, "commit", "-qm", "external write gate")
    git(w.companion, "push", "-q", "origin", "main")
    code, env, _, err = w.cli(["approve", run_id, "W-1", "--json"], user="tl")
    assert code == 0, (env, err)
    w.sync_companion()
    rt = w.rt("eng", SESSION)
    # session-start caches the approver's key so pre-mcp can verify without network
    run_hook(
        "session-start",
        json.dumps({"session_id": SESSION, "cwd": str(w.companion)}),
        env=rt.env,
        home=rt.home.root,
        rt_factory=lambda: rt,
    )


def _setup(w: World, setup: str) -> str:
    parts = setup.split("+")
    run_id = start_run(w) if parts[0] == "run" else "run_NONE"
    rt = w.rt("eng", SESSION)
    for p in parts[1:]:
        if p == "broken-policy":
            (rt.home.root / "sessions" / f"{SESSION}.policy.json").write_text("{not json")
        elif p == "approval":
            _approval(w, run_id)
        elif p in ("good-artifact", "bad-artifact"):
            _artifact(w, run_id, bad=p == "bad-artifact")
        elif p == "broken-state":
            (w.companion / f"runs/{run_id}/state.json").write_text('{"status": "RUNNING"}')
        elif p == "logged-out":
            w.identities["eng"].logged_in = False
        elif p == "old-plugin":
            pj = w.plugin / ".claude-plugin" / "plugin.json"
            meta = json.loads(pj.read_text())
            meta["version"] = "9.9.9"
            pj.write_text(json.dumps(meta))
        else:  # pragma: no cover - fixture typo
            raise AssertionError(f"unknown setup {p}")
    return run_id


@pytest.mark.parametrize("stdin_path", CASES, ids=lambda p: f"{p.parent.name}/{p.name[:-11]}")
def test_hook_golden(world: World, stdin_path: Path) -> None:
    event = stdin_path.parent.name
    expect = json.loads(stdin_path.with_name(stdin_path.name[:-11] + ".expect.json").read_text())
    run_id = _setup(world, expect["setup"])
    subs = {"companion": str(world.companion), "product": str(world.product), "run_id": run_id}
    payload = _fill(json.loads(stdin_path.read_text()), subs)
    payload = {"session_id": SESSION, "cwd": str(world.companion), **payload}
    rt = world.rt("eng", SESSION)
    log = rt.home.root / "logs" / "hook.log"
    before = log.read_text().count("\n") if log.is_file() else 0

    out, code = run_hook(
        event, json.dumps(payload), env=rt.env, home=rt.home.root, rt_factory=lambda: rt
    )

    assert code == expect["exit"]
    want = _fill(expect["stdout"], subs)
    assert (json.loads(out) if out else None) == want
    lines = log.read_text().splitlines()
    assert len(lines) == before + 1, "exactly one hook.log line per invocation"
    assert expect["log_contains"] in json.dumps(json.loads(lines[-1]), sort_keys=True)
    # fast-path hooks use the system clock, so pick this hook's own events
    events = [
        e
        for e in rt.outbox().events()
        if e["type"] == "hook.decision" and e["body"]["hook"] == event
    ]
    body = events[-1]["body"]
    assert not errors(event_schema_id("hook.decision", 1), body), body
    assert {k: body.get(k) for k in expect["event"]} == expect["event"]


def test_unknown_event_and_garbage_stdin_are_silent(world: World) -> None:
    rt = world.rt("eng", SESSION)
    assert run_hook("nonsense", "{}", env=rt.env, home=rt.home.root, rt_factory=lambda: rt) == (
        "",
        0,
    )
    out, code = run_hook(
        "pre-tool", "not json", env=rt.env, home=rt.home.root, rt_factory=lambda: rt
    )
    assert (out, code) == ("", 0)


def test_pre_tool_fast_path_imports_nothing_heavy(tmp_path: Path) -> None:
    """NFR-02: no session index -> exit 0, no output, no heavy imports (SDD-04 §11)."""
    import subprocess
    import sys

    code = (
        "import json, sys\n"
        "from pathlib import Path\n"
        "from tsl.hooks.dispatch import run\n"
        "out, rc = run('pre-tool', json.dumps({'session_id': 's-none', 'tool_name': 'Write',"
        " 'tool_input': {'file_path': '/tmp/x'}}), env={}, home=Path(sys.argv[1]))\n"
        "heavy = sorted({m.split('.')[0] for m in sys.modules} & "
        "{'typer', 'jsonschema', 'cryptography', 'msal', 'httpx', 'pydantic', 'yaml'})\n"
        "print(json.dumps([out, rc, heavy]))\n"
    )
    p = subprocess.run(
        [sys.executable, "-c", code, str(tmp_path)], capture_output=True, text=True, check=True
    )
    assert json.loads(p.stdout) == ["", 0, []]
