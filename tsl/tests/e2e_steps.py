"""Shared steps for end-to-end runs on the temp companion repo (invented data)."""

from __future__ import annotations

import json
from typing import Any

from helpers import World, intent_artifact, review_json, ticket_snapshot
from tsl.hooks.dispatch import run as run_hook

SESSION = "sess-0001"


def start_run(
    w: World, workflow: str = "brownfield-change", ticket: str = "ABC-142", user: str = "eng"
) -> str:
    code, env, _out, err = w.cli(
        ["state", "start", workflow, ticket, "--json"], user=user, session=SESSION
    )
    assert code == 0, (env, err)
    assert env is not None
    return str(env["data"]["run_id"])


def next_action(w: World, run_id: str, user: str = "eng") -> tuple[int, dict[str, Any]]:
    code, env, _, err = w.cli(["next", run_id, "--json"], user=user, session=SESSION)
    assert env is not None, err
    return code, env


def hook(w: World, event: str, payload: dict[str, Any], user: str = "eng") -> tuple[str, int]:
    rt = w.rt(user, SESSION)
    data = {"session_id": SESSION, "cwd": str(w.companion), **payload}
    return run_hook(event, json.dumps(data), env=rt.env, home=rt.home.root, rt_factory=lambda: rt)


def write_artifact(w: World, rel: str, text: str, user: str = "eng") -> tuple[str, int]:
    """What Claude does: pre-tool hook, the write itself, then the post-write hook."""
    target = str(w.companion / rel)
    out, _code = hook(
        w,
        "pre-tool",
        {
            "hook_event_name": "PreToolUse",
            "tool_name": "Write",
            "tool_input": {"file_path": target, "content": "..."},
        },
        user,
    )
    assert out == "", out
    p = w.companion / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return hook(
        w,
        "post-write",
        {
            "hook_event_name": "PostToolUse",
            "tool_name": "Write",
            "tool_input": {"file_path": target},
        },
        user,
    )


def do_req_step(
    w: World,
    run_id: str,
    *,
    variant: dict[str, Any] | None = None,
    findings: list[dict[str, Any]] | None = None,
    score: int = 5,
    expect_block: bool = False,
    user: str = "eng",
    until: str = "decide",
) -> dict[str, Any]:
    code, env = next_action(w, run_id, user)
    assert code == 0 and env["data"]["action"] == "run_skill", env
    art = env["data"]["artifact_path"]
    ticket_rel = f"artifacts/ABC-142/{run_id}/ticket.md"
    tp = w.companion / ticket_rel
    if not tp.exists():
        tp.parent.mkdir(parents=True, exist_ok=True)
        tp.write_text(ticket_snapshot(run_id), encoding="utf-8")
    code, inp, _, err = w.cli(["verify", art, "--inputs", "--json"], user=user, session=SESSION)
    assert code == 0, (inp, err)
    assert inp is not None
    text = intent_artifact(inp["data"]["envelope"], ticket_rel, **(variant or {}))
    out, hcode = write_artifact(w, art, text, user)
    assert hcode == 0
    if expect_block:
        assert json.loads(out)["decision"] == "block", out
        return {"blocked": json.loads(out), "artifact": art}
    assert out == "", out
    if until == "written":
        return {"artifact": art}
    code, pkg, _, err = w.cli(["review", "prepare", art, "--json"], user=user, session=SESSION)
    assert code == 0, (pkg, err)
    assert pkg is not None
    package = json.loads((w.companion / pkg["data"]["package_path"]).read_text())
    if until == "prepared":
        return {"artifact": art, "package": package}
    code, rec, _, err = w.cli(
        ["review", "record", art, "--json"],
        user=user,
        session=SESSION,
        stdin=review_json(package, findings=findings, score=score),
    )
    assert code == 0, (rec, err)
    if until == "recorded":
        return {"artifact": art, "package": package}
    code, dec, _, err = w.cli(["decide", art, "--json"], user=user, session=SESSION)
    assert dec is not None, err
    return {"code": code, "env": dec, "artifact": art, "package": package}
