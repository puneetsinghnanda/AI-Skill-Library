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
    st: dict[str, Any] = json.loads((world.companion / f"runs/{run_id}/state.json").read_text())
    return st


def _entry(world: World, run_id: str, gate: str) -> dict[str, Any]:
    e = approvals_md.entry(approvals_md.load(_appr(world, run_id)), gate)
    assert e is not None
    return e


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
    assert _entry(world, run_id, "G-req")["comment"] == _flat(TRICKY)
    code, env = _resume(world, run_id)
    assert code == 0, env


def test_push_failure_is_clear_and_state_stays_consistent(world: World) -> None:
    run_id = _paused(world)
    hook = world.companion_remote / "hooks" / "pre-receive"
    hook.write_text("#!/bin/sh\nexit 1\n")
    hook.chmod(0o755)
    code, env = _gate(world, run_id, "approve", "--comment", "ok")
    assert code == 10 and env["code"] == "E-GIT-01"
    assert _entry(world, run_id, "G-req")["signature"]["decision"] == "approve"
    assert "approve G-req" in git(world.companion, "log", "-1", "--format=%s")
    code, env = _gate(world, run_id, "reject", "--comment", "other")  # not the signed decision
    assert code != 0 and env["code"] == "E-RUN-05"
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


def _external_write_waiting(world: World) -> str:
    """A running run with one unsigned external-write entry (W-1) pushed to the companion."""
    run_id = _paused(world)
    assert _gate(world, run_id, "approve")[0] == 0
    code, env = _resume(world, run_id)
    assert code == 0 and env["data"]["status"] == "RUNNING"
    approvals_md.append_entry(
        _appr(world, run_id),
        run_id,
        "W-1",
        "tech_lead",
        "external_write",
        [],
        "post the summary to the ticket",
        action={"tool": "mcp__jira__add_comment", "target": "SMP-1"},
    )
    git(world.companion, "add", "-A")
    git(world.companion, "commit", "-qm", "external write waits")
    git(world.companion, "push", "-q", "origin", "main")
    return run_id


def test_external_write_gate_is_listed_inferred_and_signed(world: World) -> None:
    run_id = _external_write_waiting(world)
    code, env = _gate(world)
    assert code == 0 and [(r["run_id"], r["gate"]) for r in env["data"]["waiting"]] == [
        (run_id, "W-1")
    ]
    code, env = _gate(world, run_id)
    assert code == 0 and env["data"]["gate"] == "W-1", env
    code, env = _gate(world, run_id, "approve", "--comment", "go")  # no --gate: W-1 is inferred
    assert code == 0 and env["data"]["gate"] == "W-1", env
    e = _entry(world, run_id, "W-1")
    assert e["decision"] == "approve" and e["comment"] == "go"
    assert e["action"] == {"tool": "mcp__jira__add_comment", "target": "SMP-1"}
    sig = e["signature"]
    assert sig["kind"] == "external_write" and sig["action"] == e["action"]
    code, env = _gate(world)
    assert code == 0 and env["data"]["waiting"] == []  # signed: no longer waiting


def test_several_waiting_gates_need_gate_option(world: World) -> None:
    run_id = _paused(world)
    path = _appr(world, run_id)
    approvals_md.append_entry(
        path,
        run_id,
        "W-1",
        "tech_lead",
        "external_write",
        [],
        "x",
        action={"tool": "mcp__jira__add_comment", "target": "SMP-9"},
    )
    git(world.companion, "add", "-A")
    git(world.companion, "commit", "-qm", "w")
    git(world.companion, "push", "-q", "origin", "main")
    head = _remote_head(world)
    code, env = _gate(world, run_id, "approve")
    assert code != 0 and env["code"] == "E-RUN-05" and "--gate G-req or W-1" in env["message"]
    assert _remote_head(world) == head
    code, env = _gate(world, run_id, "--gate", "W-1")
    assert code == 0 and "--gate W-1" in env["message"].splitlines()[-1]
    code, env = _gate(world, run_id, "approve", "--gate", "W-1")
    assert code == 0 and env["data"]["gate"] == "W-1", env
    assert _entry(world, run_id, "G-req")["signature"] is None


HAND_WRITTEN = """
## W-2 · required role: tech_lead
decision:
comment: old first line
old second line
Action: tool=mcp__jira__add_comment target=SMP-2
Reason for gate: written by hand
"""


def test_set_decision_keeps_other_fields_and_replaces_only_the_comment(tmp_path: Path) -> None:
    p = tmp_path / "approvals.md"
    p.write_text("---\nschema: approvals.v1\nrun_id: run_X\n---\n" + HAND_WRITTEN, "utf-8")
    approvals_md.set_decision(p, "W-2", "changes", "new\ncomment")
    e = approvals_md.entry(approvals_md.parse(p.read_text("utf-8")), "W-2")
    assert e is not None
    assert e["decision"] == "changes" and e["comment"] == "new comment"
    assert e["action"] == {"tool": "mcp__jira__add_comment", "target": "SMP-2"}
    assert e["reason"] == "written by hand"
    text = p.read_text("utf-8")
    assert "old second line" not in text and "old first line" not in text


def test_set_decision_adds_missing_decision_and_comment_lines(tmp_path: Path) -> None:
    p = tmp_path / "approvals.md"
    body = (
        "\n## W-3 · required role: tech_lead\nAction: tool=t target=y\n"
        "Reason for gate: no fields\n\n## G-req · required role: tech_lead\ndecision:\ncomment:\n"
    )
    p.write_text("---\nschema: approvals.v1\nrun_id: run_X\n---\n" + body, "utf-8")
    approvals_md.set_decision(p, "W-3", "reject", "not this target")
    obj = approvals_md.parse(p.read_text("utf-8"))
    e, other = approvals_md.entry(obj, "W-3"), approvals_md.entry(obj, "G-req")
    assert e is not None and other is not None
    assert e["decision"] == "reject" and e["comment"] == "not this target"
    assert e["action"] == {"tool": "t", "target": "y"} and e["reason"] == "no fields"
    assert other["decision"] is None and other["comment"] is None


def test_resign_replaces_own_signature_after_resume_refused_it(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tsl.insights.client import HttpResult

    run_id = _paused(world)
    assert _gate(world, run_id, "approve", "--comment", "ok")[0] == 0
    first = _entry(world, run_id, "G-req")["signature"]
    world.sync_companion()
    cache = world.rt().home.key_cache("x").parent
    for f in cache.glob("*.json") if cache.exists() else []:
        f.unlink()
    with monkeypatch.context() as mp:
        mp.setattr(world.insights, "get_key", lambda token, key_id: HttpResult(404, None))
        code, env = _resume(world, run_id)
    assert env["code"] == "E-AUTH-11", env
    fix = f"tsl gate {run_id} <decision> --gate G-req --resign"
    assert fix in env["message"] + str(env["next"])
    # The fix the message names works: the approver signs again, the owner resumes.
    code, env = _gate(world, run_id, "approve", "--gate", "G-req", user="eng")
    assert code != 0 and env["code"] == "E-RUN-05"  # --resign missing: still refused
    code, env = _gate(world, run_id, "approve", "--gate", "G-req", "--resign", user="eng")
    assert code != 0 and env["code"] == "E-RUN-05"  # not eng's signature
    world.clock.tick(60) if hasattr(world.clock, "tick") else None
    code, env = _gate(world, run_id, "approve", "--comment", "again", "--gate", "G-req", "--resign")
    assert code == 0, env
    e = _entry(world, run_id, "G-req")
    assert e["comment"] == "again" and e["signature"]["signature"] != first["signature"]
    assert _appr(world, run_id).read_text().count("tsl:signature-begin G-req") == 1
    code, env = _resume(world, run_id)
    assert code == 0 and env["data"]["status"] == "RUNNING", env


def test_broken_approvals_file_of_one_run_does_not_hide_other_gates(world: World) -> None:
    import shutil

    good = _paused(world)
    broken = good[:-1] + ("0" if good[-1] != "0" else "1")  # a second paused run, file damaged
    shutil.copytree(world.companion / f"runs/{good}", world.companion / f"runs/{broken}")
    st = _state(world, good)
    st["run_id"] = broken
    (world.companion / f"runs/{broken}/state.json").write_text(json.dumps(st))
    _appr(world, broken).write_text("---\nschema: [\n---\n## G-req · required role: tech_lead\n")
    with pytest.raises(Exception):  # noqa: B017 - the file really is unreadable
        approvals_md.load(_appr(world, broken))
    git(world.companion, "add", "-A")
    git(world.companion, "commit", "-qm", "break one file")
    git(world.companion, "push", "-q", "origin", "main")
    code, env = _gate(world)
    assert code == 0 and [r["run_id"] for r in env["data"]["waiting"]] == [good]


def test_decide_does_not_need_the_summary(world: World) -> None:
    run_id = _paused(world)
    e = _entry(world, run_id, "G-req")
    from tsl.core.paths import sibling

    rec = world.companion / sibling(e["artifacts"][0]["path"], ".verification.json")
    world_text = rec.read_text() if rec.is_file() else None
    rec.write_text("{not json")
    code, env = _gate(world, run_id)
    assert code == 0 and "verification" not in env["data"]  # summary: only the quality line goes
    if world_text is None:
        rec.unlink()
    else:
        rec.write_text(world_text)
    code, env = _gate(world, run_id, "approve")
    assert code == 0, env


def test_stdin_is_read_as_utf8_whatever_the_code_page(monkeypatch: pytest.MonkeyPatch) -> None:
    import io
    import sys

    from tsl.cli.app import _utf8_streams

    raw = "Größe → kleiner".encode()
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(raw), encoding="cp1252"))
    _utf8_streams()
    assert sys.stdin.read() == "Größe → kleiner"
