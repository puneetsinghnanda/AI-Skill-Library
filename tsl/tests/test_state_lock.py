"""Run state and the lock protocol (SDD-02 §11, SDD-12 §3.3, SDD-04 §6.7)."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any

import pytest

import helpers
from e2e_steps import SESSION, next_action, start_run
from helpers import World, git
from tsl.core.errors import TslError
from tsl.core.repo import Companion
from tsl.gitops import git as gitmod
from tsl.schemas.registry import errors

LOCK = "runs/active/ABC-142__brownfield-change.lock"


def _start(
    w: World, user: str = "eng", repo: Path | None = None, ticket: str = "ABC-142"
) -> tuple[int, dict[str, Any]]:
    code, env, _, err = w.cli(
        ["state", "start", "brownfield-change", ticket, "--json"],
        user=user,
        session=SESSION,
        repo=repo,
    )
    assert env is not None, err
    return code, env


def _second_clone(w: World, user: str = "eng2") -> Path:
    other = w.base / "companion-2"
    git(w.base, "clone", "-q", str(w.companion_remote), str(other))
    shutil.copytree(w.companion / ".tsl", other / ".tsl")
    w.login(user)
    return other


def test_start_takes_and_pushes_the_lock(world: World) -> None:
    run_id = start_run(world)
    remote_lock = git(world.companion_remote, "show", f"main:{LOCK}")
    lock = json.loads(remote_lock)
    assert errors("run-lock.v1", lock) == [] and lock["run_id"] == run_id
    state = json.loads((world.companion / f"runs/{run_id}/state.json").read_text())
    assert errors("run-state.v1", state) == [] and state["status"] == "RUNNING"
    idx = json.loads((world.rt().home.root / "sessions" / f"{SESSION}.json").read_text())
    assert errors("session-index.v1", idx) == [] and idx["run_id"] == run_id
    types = [e["type"] for e in world.rt().outbox().events()]
    assert "run.started" in types


def test_second_start_is_locked(world: World) -> None:
    run_id = start_run(world)
    code, env = _start(world)
    assert (code, env["code"]) == (3, "E-LOCK-01")
    assert env["data"]["run_id"] == run_id and env["next"] == f"/truminds:resume {run_id}"


def test_other_laptop_sees_the_lock(world: World) -> None:
    run_id = start_run(world)
    other = _second_clone(world)
    code, env = _start(world, user="eng2", repo=other)
    assert (code, env["code"]) == (3, "E-LOCK-01") and env["data"]["run_id"] == run_id


def test_push_race_loser_drops_its_commit(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    other = _second_clone(world)
    head_before = git(other, "rev-parse", "HEAD")
    real_push = gitmod.Git.push
    fired: list[bool] = []

    def racing_push(self: gitmod.Git, branch: str, remote_branch: str | None = None) -> bool:
        if self.cwd == other and not fired:
            fired.append(True)
            assert start_run(world)  # the first laptop wins between fetch and push
        return real_push(self, branch, remote_branch)

    monkeypatch.setattr(gitmod.Git, "push", racing_push)
    code, env = _start(world, user="eng2", repo=other)
    assert (code, env["code"]) == (3, "E-LOCK-01")
    assert git(other, "rev-parse", "HEAD") == head_before
    assert not (other / LOCK).exists()
    assert not [p for p in (other / "runs").iterdir() if p.name.startswith("run_")]


def test_offline_cannot_take_a_lock(world: World) -> None:
    git(world.companion, "remote", "set-url", "origin", str(world.base / "gone.git"))
    code, env = _start(world)
    assert (code, env["code"]) == (10, "E-LOCK-03")
    assert not (world.companion / LOCK).exists()


def test_rejected_push_three_times(world: World) -> None:
    hook = world.companion_remote / "hooks" / "pre-receive"
    hook.write_text("#!/bin/sh\nexit 1\n")
    hook.chmod(0o755)
    code, env = _start(world)
    assert (code, env["code"]) == (10, "E-LOCK-04")
    assert not (world.companion / LOCK).exists()


def test_show_and_cancel(world: World) -> None:
    run_id = start_run(world)
    code, env, _, _ = world.cli(["state", "show", "--json"])
    assert code == 0 and env is not None and env["data"]["runs"][0]["run_id"] == run_id
    world.login("eng2")
    code, env, _, _ = world.cli(
        ["state", "cancel", run_id, "--reason", "dup", "--json"], user="eng2"
    )
    assert code == 3 and env is not None and env["code"] == "E-RUN-06"
    code, env, _, _ = world.cli(["state", "cancel", run_id, "--reason", "dup", "--json"])
    assert code == 0 and env is not None and env["data"]["end_reason"] == "cancelled"
    assert not (world.companion / LOCK).exists()
    code, env, _, _ = world.cli(["state", "show", "--json"])
    assert env is not None and env["data"]["runs"] == []
    code, env, _, _ = world.cli(["state", "show", "--all", "--json"])
    assert env is not None and env["data"]["runs"][0]["status"] == "COMPLETED"
    code, env, _, _ = world.cli(["state", "show", "run_01J9ZZZZZZZZZZZZZZZZZZZZZZ", "--json"])
    assert code == 3 and env is not None and env["code"] == "E-RUN-04"


def test_unlock_rules(world: World) -> None:
    run_id = start_run(world)
    args = ["state", "unlock", "ABC-142", "brownfield-change", "--reason", "left", "--json"]
    code, env, _, _ = world.cli(args, user="eng")
    assert code == 3 and env is not None and env["code"] == "E-AUTH-04"
    code, env, _, _ = world.cli(args, user="tl")
    assert code == 3 and env is not None and env["code"] == "E-RUN-05"
    world.clock.advance(hours=25)
    world.insights.offline = False
    code, env, _, err = world.cli(args, user="tl")
    assert code == 0, (env, err)
    assert env is not None and env["data"]["run_id"] == run_id
    assert env["data"]["previous_holder"]
    assert LOCK not in git(world.companion_remote, "ls-tree", "-r", "--name-only", "main")


def test_resume_rules(world: World) -> None:
    run_id = start_run(world)
    code, env, _, _ = world.cli(
        ["state", "resume", "run_01J9ZZZZZZZZZZZZZZZZZZZZZZ", "--json"], session=SESSION
    )
    assert code == 3 and env is not None and env["code"] == "E-RUN-04"
    other = _second_clone(world)
    git(other, "pull", "-q")
    code, env, _, _ = world.cli(
        ["state", "resume", run_id, "--json"], user="eng2", repo=other, session=SESSION
    )
    assert code == 3 and env is not None and env["code"] == "E-RUN-06"


def test_next_unknown_run(world: World) -> None:
    code, env, _, _ = world.cli(["next", "run_01J9ZZZZZZZZZZZZZZZZZZZZZZ", "--json"])
    assert code == 3 and env is not None and env["code"] == "E-RUN-04"


def test_repair_and_repin(world: World) -> None:
    run_id = start_run(world)
    _c, nenv = next_action(world, run_id)
    assert nenv["data"]["action"] == "run_skill"
    state_p = world.companion / f"runs/{run_id}/state.json"
    before = json.loads(state_p.read_text())
    state_p.unlink()
    code, env, _, err = world.cli(["state", "repair", run_id, "--json"])
    assert code == 0, (env, err)
    after = json.loads(state_p.read_text())
    assert errors("run-state.v1", after) == [] and after["ticket"] == before["ticket"]
    code, env, _, _ = world.cli(["state", "repin", run_id, "--json"])
    assert code == 0 and env is not None and env["data"]["repinned"] == {}


def test_local_lock_busy(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    from tsl.state import store

    run_id = start_run(world)
    monkeypatch.setattr(store, "LOCAL_WAIT_S", 0.2)
    (world.companion / f"runs/{run_id}/.local.lock").write_text(str(os.getppid()))
    with (
        world.using() as rt,
        pytest.raises(TslError) as e,
        store.RunStore(rt, Companion(world.companion), run_id).local_lock(),
    ):
        pass
    assert e.value.code == "E-RUN-11"
    # a dead holder is cleared
    (world.companion / f"runs/{run_id}/.local.lock").write_text("999999")
    with world.using() as rt, store.RunStore(rt, Companion(world.companion), run_id).local_lock():
        pass


def test_start_preconditions(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    code, env = _start(world, ticket="not a ticket")
    assert (code, env["code"]) == (1, "E-USE-01")
    world.insights.systems[helpers.SYSTEM]["consent"]["recorded"] = False
    code, env = _start(world)
    assert (code, env["code"]) == (3, "E-CONS-01")
    for p in (world.rt("eng").home.cache / "systems").glob("*.json"):
        p.unlink()
    world.insights.systems[helpers.SYSTEM]["lifecycle_state"] = "ARCHIVED"
    code, env = _start(world)
    assert (code, env["code"]) == (3, "E-COMP-07")


def test_start_without_engineer_grant(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    users = json.loads(json.dumps(helpers.USERS))
    users["eng2"]["grants"] = [{"role": "viewer", "scope": "org"}]
    monkeypatch.setattr(helpers, "USERS", users)
    other = _second_clone(world)
    code, env = _start(world, user="eng2", repo=other)
    assert (code, env["code"]) == (3, "E-AUTH-03")


def test_start_needs_a_pack(bare_world: World) -> None:
    code, env = _start(bare_world)
    assert (code, env["code"]) == (3, "E-CTX-01")


def test_start_needs_matching_version(world: World) -> None:
    pj = world.plugin / ".claude-plugin" / "plugin.json"
    meta = json.loads(pj.read_text())
    meta["version"] = "9.9.9"
    pj.write_text(json.dumps(meta))
    code, env = _start(world)
    assert (code, env["code"]) == (3, "E-VER-01")
