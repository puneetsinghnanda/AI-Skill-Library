"""tsl gate end to end on a local bare-git companion: list, summary, decide, resume."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from e2e_steps import SESSION, do_req_step, next_action, start_run
from helpers import World, git
from tsl.approvals import approvals_md
from tsl.core.paths import feedback_path

TRICKY = "say \"hi\" $HOME `date` 'q'\nsecond line café ✓"
STATUS = {"reject": "REJECTED", "abort": "ABORTED"}


def _flat(text: str) -> str:
    return " ".join(text.split())


def _paused(world: World, owner: str = "eng") -> str:
    run_id = start_run(world, user=owner)
    assert do_req_step(world, run_id, user=owner)["code"] == 0
    code, env = next_action(world, run_id, owner)
    assert code == 4 and env["data"]["action"] == "pause_approval"
    git(world.companion, "commit", "-qam", "paused")
    git(world.companion, "push", "-q", "origin", "main")
    return run_id


def _appr(world: World, run_id: str) -> Path:
    return world.companion / f"runs/{run_id}/approvals.md"


def _remote_head(world: World) -> str:
    return git(world.companion_remote, "rev-parse", "main").strip()


def _gate(world: World, *args: str, user: str = "tl", stdin: str = "") -> tuple[int, Any]:
    code, env, _, err = world.cli(["gate", *args, "--json"], user=user, stdin=stdin)
    assert env is not None, err
    return code, env


def _resume(world: World, run_id: str, user: str = "eng") -> tuple[int, Any]:
    world.sync_companion()
    code, env, _, _ = world.cli(["state", "resume", run_id, "--json"], user=user, session=SESSION)
    return code, env


def _state(world: World, run_id: str) -> dict[str, Any]:
    return json.loads((world.companion / f"runs/{run_id}/state.json").read_text())


def _allow_self_approval(world: World) -> None:
    cfg = world.companion / "tsl.yaml"
    cfg.write_text(cfg.read_text().replace("self_approval: false", "self_approval: true"))
    git(world.companion, "commit", "-qam", "allow self approval")
    git(world.companion, "push", "-q", "origin", "main")


def test_pause_message_list_summary_then_decide_one_commit(world: World) -> None:
    run_id = start_run(world)
    assert do_req_step(world, run_id)["code"] == 0
    code, env = next_action(world, run_id)
    assert code == 4 and env["code"] == "E-RUN-02"
    assert f"/runs/{run_id}" in env["message"]
    assert f"/tsl-gate {run_id}" in env["next"]
    git(world.companion, "commit", "-qam", "paused")
    git(world.companion, "push", "-q", "origin", "main")

    code, env = _gate(world)
    assert code == 0 and [r["run_id"] for r in env["data"]["waiting"]] == [run_id]
    head, text = _remote_head(world), _appr(world, run_id).read_text()
    code, env = _gate(world, run_id)
    assert code == 0 and env["data"]["gate"] == "G-req"
    assert env["data"]["portal"].endswith(f"/runs/{run_id}")
    assert _appr(world, run_id).read_text() == text and _remote_head(world) == head

    code, env = _gate(world, run_id, "approve", "--comment", "looks good")
    assert code == 0 and env["data"]["resumable"] is False
    after = _remote_head(world)
    assert git(world.companion_remote, "rev-list", "--count", f"{head}..{after}").strip() == "1"
    assert "approve G-req" in git(world.companion_remote, "log", "-1", "--format=%s", "main")
    code, env = _resume(world, run_id)
    assert code == 0 and env["data"]["status"] == "RUNNING"


def test_changes_needs_comment_and_feedback_carries_it(world: World) -> None:
    run_id = _paused(world)
    head, text = _remote_head(world), _appr(world, run_id).read_text()
    for d in ("changes", "reject"):
        code, env = _gate(world, run_id, d)
        assert code != 0 and env["code"] == "E-RUN-05"
    assert _appr(world, run_id).read_text() == text and _remote_head(world) == head
    code, env = _gate(world, run_id, "changes", "--comment", "rename X")
    assert code == 0, env
    code, env = _resume(world, run_id)
    assert code == 0, env
    fb = json.loads((world.companion / feedback_path(run_id, "req", 1)).read_text())
    assert fb["comment"] == "rename X"


@pytest.mark.parametrize("decision", ["reject", "abort"])
def test_reject_and_abort_end_states(world: World, decision: str) -> None:
    run_id = _paused(world)
    code, env = _gate(world, run_id, decision, "--comment", "no")
    assert code == 0, env
    code, env = _resume(world, run_id)
    assert code == 0, env
    st = _state(world, run_id)
    assert st["gates"][0]["status"] == STATUS[decision]
    if decision == "abort":
        assert st["status"] == "COMPLETED" and st["end_reason"] == "rejected"


def test_second_identity_approves_owner_resumes(world: World) -> None:
    run_id = _paused(world)
    code, env = _gate(world, run_id, "approve", user="tl")
    assert code == 0 and env["data"]["self_approved"] is False
    code, env = _resume(world, run_id, user="eng")
    assert code == 0 and env["data"]["status"] == "RUNNING"


def test_self_approval_refused_then_allowed_and_resumable(world: World) -> None:
    run_id = _paused(world, owner="tl")
    code, env = _gate(world, run_id, "approve", user="tl")
    assert code == 3 and env["code"] == "E-AUTH-06"
    assert "decision: approve" not in _appr(world, run_id).read_text()
    _allow_self_approval(world)
    code, env = _gate(world, run_id, "approve", user="tl")
    assert code == 0 and env["data"]["resumable"] is True and env["data"]["self_approved"]
    code, env = _resume(world, run_id, user="tl")
    assert code == 0, env


def test_wrong_role_signed_gate_and_tamper(world: World) -> None:
    run_id = _paused(world, owner="tl")
    code, env = _gate(world, run_id, "approve", "--comment", "fine", user="eng")
    assert code == 3 and env["code"] == "E-AUTH-05"
    _allow_self_approval(world)
    code, env = _gate(world, run_id, "approve", "--comment", "fine", user="tl")
    assert code == 0, env
    code, env = _gate(world, run_id, "approve", user="tl")
    assert code != 0 and env["code"] == "E-RUN-05"  # already signed
    appr = _appr(world, run_id)
    appr.write_text(appr.read_text().replace("comment: fine", "comment: fine, and more"))
    git(world.companion, "commit", "-qam", "tamper")
    git(world.companion, "push", "-q", "origin", "main")
    code, env = _resume(world, run_id, user="tl")
    assert code != 0 and env["code"] == "E-RUN-08"


@pytest.mark.parametrize("via", ["comment", "stdin"])
def test_comment_round_trip(world: World, via: str) -> None:
    run_id = _paused(world)
    if via == "comment":
        code, env = _gate(world, run_id, "approve", "--comment", TRICKY)
    else:
        code, env = _gate(world, run_id, "approve", "--comment-file", "-", stdin=TRICKY)
    assert code == 0, env
    world.sync_companion()
    obj = approvals_md.load(_appr(world, run_id))
    assert approvals_md.entry(obj, "G-req")["comment"] == _flat(TRICKY)
    code, env = _resume(world, run_id)
    assert code == 0, env


def test_push_failure_is_clear_and_state_stays_consistent(world: World) -> None:
    run_id = _paused(world)
    hook = world.companion_remote / "hooks" / "pre-receive"
    hook.write_text("#!/bin/sh\nexit 1\n")
    code, env = _gate(world, run_id, "approve", "--comment", "ok")
    assert code == 10 and env["code"] == "E-GIT-01"
    obj = approvals_md.load(_appr(world, run_id))
    assert approvals_md.entry(obj, "G-req")["signature"]["decision"] == "approve"
    assert "approve G-req" in git(world.companion, "log", "-1", "--format=%s")
    hook.unlink()
    signed = git(world.companion, "rev-parse", "HEAD").strip()
    code, env = _gate(world, run_id, "approve", "--comment", "ok")
    assert code == 0, env  # the retry pushes the earlier signature
    assert env["data"]["pushed_earlier_signature"] is True
    assert git(world.companion, "rev-parse", "HEAD").strip() == signed  # not signed twice
    assert _remote_head(world) == signed
    code, env = _gate(world, run_id, "approve", "--comment", "ok")
    assert code != 0 and env["code"] == "E-RUN-05"  # pushed and signed: refused
    code, env = _resume(world, run_id)
    assert code == 0, env
