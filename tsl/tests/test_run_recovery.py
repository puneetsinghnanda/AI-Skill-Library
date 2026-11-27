"""Stuck and broken run recovery (roadmap D2): a companion sync that a killed command left
half-finished is repaired before the next sync, a closed session never keeps a run busy, a live
one is named with its last activity, and a run with no progress says so in --progress, the
session-start reminder and tsl doctor --run."""

from __future__ import annotations

import datetime as dt
import json
import os
import time
from pathlib import Path
from typing import Any

import pytest

from e2e_steps import SESSION, hook, next_action, start_run
from helpers import World, git
from tsl.approvals import ide_questions
from tsl.core.clock import iso
from tsl.gitops.git import REPAIR_HINT, STALE_GIT_LOCK_S, Git, GitError
from tsl.state import stuck

OTHER = "sess-0002"


# ------------------------------------------------------------------------- a killed companion sync


def _two_clones(base: Path) -> tuple[Path, Path]:
    remote, work, other = base / "remote.git", base / "work", base / "other"
    git(base, "init", "-q", "--bare", "-b", "main", str(remote))
    for d in (work, other):
        git(base, "clone", "-q", str(remote), str(d))
        git(d, "config", "user.email", "t@example.com")
        git(d, "config", "user.name", "t")
    (work / "runs").mkdir()
    (work / "runs" / "state.json").write_text('{"rev": 1}\n', encoding="utf-8")
    git(work, "add", ".")
    git(work, "commit", "-q", "-m", "base")
    git(work, "push", "-q", "origin", "main")
    git(other, "pull", "-q", "origin", "main")
    return work, other


def _half_sync(repo: Path, other: Path, branch: str = "main") -> str:
    """Leave `repo` as a killed `tsl` sync does: a rebase onto origin stopped after its first
    commit, with a clean working tree. Returns the local branch tip before the sync."""
    (other / "theirs.txt").write_text("from GitHub\n", encoding="utf-8")
    git(other, "add", ".")
    git(other, "commit", "-q", "-m", "theirs")
    git(other, "push", "-q", "origin", "main")
    for n in (1, 2):
        (repo / f"mine{n}.txt").write_text(f"{n}\n", encoding="utf-8")
        git(repo, "add", ".")
        git(repo, "commit", "-q", "-m", f"mine {n}")
    tip = git(repo, "rev-parse", "HEAD")
    git(repo, "fetch", "-q", "origin")
    Git(repo).run("rebase", "-q", "--exec", "false", "origin/main", check=False)
    assert Git(repo).leftovers()["rebase"] == f"refs/heads/{branch}"
    return tip


def test_a_killed_sync_is_repaired_and_keeps_every_file(tmp_path: Path) -> None:
    work, other = _two_clones(tmp_path)
    tip = _half_sync(work, other)
    # tsl wrote while the sync was half-finished: a rebase --abort alone would drop these.
    (work / "runs" / "state.json").write_text('{"rev": 2}\n', encoding="utf-8")
    (work / "runs" / "new.json").write_text("{}\n", encoding="utf-8")
    (work / "runs" / ".local.lock").write_text("123", encoding="utf-8")  # held by a process
    done = Git(work).repair("main")
    assert [d["what"] for d in done] == ["rebase"]
    assert Git(work).leftovers()["rebase"] is None
    assert git(work, "rev-parse", "HEAD") == tip  # local commits kept
    assert (work / "runs" / "state.json").read_text(encoding="utf-8") == '{"rev": 2}\n'
    assert (work / "runs" / "new.json").is_file()
    assert (work / "runs" / ".local.lock").read_text(encoding="utf-8") == "123"
    assert Git(work).repair("main") == []  # nothing left to repair
    assert Git(work).sync_push("main")  # and the sync now goes through
    assert (work / "theirs.txt").is_file()


def test_a_rebase_of_another_branch_is_left_alone(tmp_path: Path) -> None:
    work, other = _two_clones(tmp_path)
    git(work, "switch", "-q", "-c", "mine")
    _half_sync(work, other, "mine")
    with pytest.raises(GitError) as e:
        Git(work).repair("main")
    assert "refs/heads/mine" in e.value.detail and "git rebase --abort" in str(e.value.next)
    assert Git(work).leftovers()["rebase"] == "refs/heads/mine"


def test_only_a_stale_git_lock_is_removed(tmp_path: Path) -> None:
    work, _ = _two_clones(tmp_path)
    lock = work / ".git" / "index.lock"
    lock.write_text("", encoding="utf-8")
    assert Git(work).repair("main") == []  # fresh: a git command may be running now
    old = time.time() - STALE_GIT_LOCK_S - 5
    os.utime(lock, (old, old))
    assert [d["what"] for d in Git(work).repair("main")] == ["git-lock"]
    assert not lock.exists()


def test_no_commit_lands_on_a_half_finished_sync(tmp_path: Path) -> None:
    # Repairing (rebase --abort) would drop a commit made on the half-finished rebase.
    work, other = _two_clones(tmp_path)
    _half_sync(work, other)
    (work / "runs" / "state.json").write_text('{"rev": 3}\n', encoding="utf-8")
    with pytest.raises(GitError) as e:
        Git(work).commit("tsl: decide", ["runs"])
    assert e.value.next == REPAIR_HINT
    assert (work / "runs" / "state.json").read_text(encoding="utf-8") == '{"rev": 3}\n'


def test_git_errors_say_network_only_when_it_may_be_the_network(tmp_path: Path) -> None:
    work, _ = _two_clones(tmp_path)
    git(work, "remote", "set-url", "origin", str(tmp_path / "gone.git"))
    with pytest.raises(GitError) as e:
        Git(work).fetch()
    assert e.value.next is None  # E-GIT-01's own hint: network and access
    (work / ".git" / "index.lock").write_text("", encoding="utf-8")
    with pytest.raises(GitError) as e:
        Git(work).run("add", "-A")
    assert e.value.next == REPAIR_HINT


# ------------------------------------------------------------------ resume and cancel, end to end


def _companion_half_sync(world: World, tmp_path: Path) -> None:
    other = tmp_path / "other-companion"
    git(tmp_path, "clone", "-q", str(world.companion_remote), str(other))
    for d in (other, world.companion):
        git(d, "config", "user.email", "t@example.com")
        git(d, "config", "user.name", "t")
    _half_sync(world.companion, other)


def test_resume_after_a_killed_sync_repairs_it_in_one_command(world: World, tmp_path: Path) -> None:
    run_id = start_run(world)
    _companion_half_sync(world, tmp_path)
    code, env, _, err = world.cli(["state", "resume", run_id, "--json"], session=SESSION)
    assert code == 0 and env is not None, (env, err)
    assert [r["what"] for r in env["data"]["repaired"]] == ["rebase"]
    assert Git(world.companion).leftovers()["rebase"] is None
    assert (world.companion / "theirs.txt").is_file()  # synced after the repair


def test_cancel_after_a_killed_sync_reaches_github(world: World, tmp_path: Path) -> None:
    run_id = start_run(world)
    _companion_half_sync(world, tmp_path)
    code, env, _, err = world.cli(["state", "cancel", run_id, "--reason", "test", "--json"])
    assert code == 0 and env is not None, (env, err)
    assert [r["what"] for r in env["data"]["repaired"]] == ["rebase"]
    git(world.companion, "fetch", "-q", "origin")
    on_github = git(world.companion, "ls-tree", "-r", "--name-only", "origin/main", "runs/active")
    # the run lock was released on GitHub, not only locally
    assert not [p for p in on_github.splitlines() if p.endswith(".lock")]


# --------------------------------------------------------------------------- sessions (E-RUN-11)


def _resume(world: World, run_id: str, *extra: str) -> tuple[int, dict[str, Any]]:
    code, env, _, err = world.cli(["state", "resume", run_id, *extra, "--json"], session=OTHER)
    assert env is not None, err
    return code, env


def test_a_closed_session_never_keeps_the_run_busy(world: World) -> None:
    # The session-end hook used to refresh the heartbeat: a closed session looked alive for
    # 15 more minutes, and resuming it at once gave E-RUN-11.
    run_id = start_run(world)
    next_action(world, run_id)
    assert hook(world, "session-end", {"hook_event_name": "SessionEnd"}) == ("", 0)
    st = json.loads((world.companion / f"runs/{run_id}/state.json").read_text("utf-8"))
    assert st["active_session"]["session_id"] == SESSION and st["active_session"]["ended_at"]
    code, env = _resume(world, run_id)
    assert code == 0, env
    st = json.loads((world.companion / f"runs/{run_id}/state.json").read_text("utf-8"))
    assert st["active_session"]["session_id"] == OTHER and "ended_at" not in st["active_session"]


def test_a_live_session_is_named_with_its_last_activity(world: World) -> None:
    run_id = start_run(world)
    next_action(world, run_id)
    code, env = _resume(world, run_id)
    assert env["code"] == "E-RUN-11"
    holder = env["data"]["holder"]
    assert holder["session_id"] == SESSION[:12] and holder["last_activity_at"] == iso(world.clock())
    code, env = _resume(world, run_id, "--take-over")  # the engineer said it is closed
    assert code == 0, env


def test_a_tool_call_counts_as_activity_not_only_a_state_save(world: World) -> None:
    run_id = start_run(world)
    next_action(world, run_id)
    world.clock.advance(minutes=20)  # no state save for 20 min: looked dead
    log = world.companion / f"runs/{run_id}/tool-log.jsonl"
    with log.open("a", encoding="utf-8") as fh:  # but the step wrote a file a minute ago
        fh.write(json.dumps({"ts": iso(world.clock() - dt.timedelta(minutes=1))}) + "\n")
    assert _resume(world, run_id)[1]["code"] == "E-RUN-11"
    world.clock.advance(minutes=15)
    assert _resume(world, run_id)[0] == 0


# --------------------------------------------------------------------------------- stuck runs


def _progress(world: World) -> dict[str, Any]:
    code, env, _, err = world.cli(["state", "show", "--progress", "--json"], session=SESSION)
    assert code == 0 and env is not None, err
    return dict(env["data"]["progress"])


def test_a_step_with_no_activity_past_its_limit_is_stuck(world: World) -> None:
    run_id = start_run(world)
    next_action(world, run_id)  # req attempt 1 is open
    world.clock.advance(minutes=29)
    assert _progress(world)["stuck"] is None
    world.clock.advance(minutes=2)
    s = _progress(world)["stuck"]
    assert (s["phase"], s["minutes"], s["limit_min"]) == ("run_step", 31, 30)
    assert s["command"] == f"/truminds:resume {run_id}" and run_id in s["cancel"]


def test_waiting_on_the_engineer_is_not_stuck(world: World) -> None:
    run_id = start_run(world)
    next_action(world, run_id)
    ide_questions.raised(
        world.companion,
        run_id,
        "req",
        1,
        [{"id": "Q-01", "text": "Q-01: x?"}],
        source="hook",
        at=iso(world.clock()),
        tool_use_id="t1",
    )
    world.clock.advance(hours=2)
    assert _progress(world)["stuck"] is None


def test_phases_and_limits() -> None:
    between = {"status": "RUNNING", "cursor": None}
    step = {"status": "RUNNING", "cursor": {"step": "ut", "attempt": 1}}
    review = {**step, "current_action": {"action": "run_reviewer", "step": "ut"}}
    stale = {**step, "current_action": {"action": "run_reviewer", "step": "impl"}}
    assert [stuck.phase(s) for s in (between, step, review, stale)] == [
        "between",
        "run_step",
        "run_reviewer",
        "run_step",  # an action for another step is not what is open now
    ]
    assert [stuck.limit_min(s, 30) for s in (between, step, review)] == [10, 30, 15]
    assert stuck.limit_min(between, 6) == 5  # never below 5 minutes


def test_only_running_runs_are_stuck(tmp_path: Path) -> None:
    now = dt.datetime(2026, 11, 27, 12, 0, tzinfo=dt.UTC)
    old = {"updated_at": "2026-11-27T08:00:00Z", "cursor": {"step": "ut"}}
    assert stuck.stuck(tmp_path, "run_x", {**old, "status": "RUNNING"}, now) is not None
    for status in ("PAUSED_INPUT", "PAUSED_APPROVAL", "COMPLETED"):
        assert stuck.stuck(tmp_path, "run_x", {**old, "status": status}, now) is None


def test_the_reminder_and_doctor_say_the_run_is_stuck(world: World, tmp_path: Path) -> None:
    run_id = start_run(world)
    next_action(world, run_id)
    world.clock.advance(minutes=45)
    out, _ = hook(world, "session-start", {"hook_event_name": "SessionStart", "source": "startup"})
    ctx = json.loads(out)["hookSpecificOutput"]["additionalContext"]
    assert f"Unfinished run {run_id}" in ctx and "no progress since" in ctx and "(45 min)" in ctx
    _companion_half_sync(world, tmp_path)
    _, env, _, err = world.cli(["doctor", "--run", "--json"])
    assert env is not None, err
    checks = {c["id"]: c for c in env["data"]["checks"]}
    assert checks["companion-sync"]["status"] == "fail"
    assert f"/truminds:resume {run_id}" in checks["companion-sync"]["fix"]
    prog = checks[f"run-progress-{run_id}"]
    assert prog["status"] == "warn" and "no progress since" in prog["detail"]


# ------------------------------------------------------------------ review of #78 (Yash, 27 Nov)


def _conflicting(work: Path, other: Path) -> None:
    """A commit of ours and one on GitHub change the same line of the same file."""
    (other / "runs" / "state.json").write_text('{"rev": "theirs"}\n', encoding="utf-8")
    git(other, "commit", "-q", "-am", "theirs")
    git(other, "push", "-q", "origin", "main")
    (work / "runs" / "state.json").write_text('{"rev": "mine"}\n', encoding="utf-8")
    git(work, "commit", "-q", "-am", "mine")
    git(work, "fetch", "-q", "origin")


def test_tsl_never_leaves_a_conflicted_sync_behind(tmp_path: Path) -> None:
    # rebase() named the conflict but left the rebase in progress for repair() to trip on.
    work, other = _two_clones(tmp_path)
    _conflicting(work, other)
    tip = git(work, "rev-parse", "HEAD")
    with pytest.raises(GitError) as e:
        Git(work).rebase("origin/main")
    assert "runs/state.json" in e.value.detail and "nothing was lost" in e.value.detail
    assert Git(work).leftovers()["rebase"] is None and git(work, "rev-parse", "HEAD") == tip


def test_a_sync_stopped_on_a_conflict_keeps_the_files_written_since(tmp_path: Path) -> None:
    # As an older tsl left it: the rebase stopped on a conflict; tsl wrote a file after.
    work, other = _two_clones(tmp_path)
    (work / "notes.json").write_text("v1\n", encoding="utf-8")
    git(work, "add", ".")
    git(work, "commit", "-q", "-m", "notes")
    _conflicting(work, other)
    Git(work).run("rebase", "-q", "origin/main", check=False)
    assert Git(work).unmerged() == ["runs/state.json"]
    (work / "notes.json").write_text("v2 written after the conflict\n", encoding="utf-8")
    done = Git(work).repair("main")
    assert [d["what"] for d in done] == ["rebase", "conflict"]
    assert "runs/state.json" in done[1]["detail"]
    assert (work / "notes.json").read_text(encoding="utf-8") == "v2 written after the conflict\n"
    assert Git(work).leftovers()["rebase"] is None and not Git(work).unmerged()


def test_the_newest_file_wins_over_an_autostashed_copy(tmp_path: Path) -> None:
    # state.json was dirty when the sync started (autostashed), and written again after the
    # kill: the abort put back the older copy, and the newer one was left in git stash.
    work, other = _two_clones(tmp_path)
    (other / "theirs.txt").write_text("x\n", encoding="utf-8")
    git(other, "add", ".")
    git(other, "commit", "-q", "-m", "theirs")
    git(other, "push", "-q", "origin", "main")
    (work / "mine.txt").write_text("x\n", encoding="utf-8")
    git(work, "add", ".")
    git(work, "commit", "-q", "-m", "mine")
    git(work, "fetch", "-q", "origin")
    (work / "runs" / "state.json").write_text('{"rev": 2}\n', encoding="utf-8")
    Git(work).run("rebase", "--autostash", "--exec", "false", "origin/main", check=False)
    assert Git(work).leftovers()["rebase"]
    (work / "runs" / "state.json").write_text('{"rev": 3}\n', encoding="utf-8")
    assert [d["what"] for d in Git(work).repair("main")] == ["rebase"]
    assert (work / "runs" / "state.json").read_text(encoding="utf-8") == '{"rev": 3}\n'
    assert not git(work, "stash", "list")


def test_a_file_the_abort_would_refuse_to_overwrite_is_kept(tmp_path: Path) -> None:
    # The sync stopped before our second commit was replayed; its file was then written
    # again. git rebase --abort refuses to overwrite it unless it is moved aside first.
    work, other = _two_clones(tmp_path)
    _half_sync(work, other)  # mine1 replayed, mine2 not yet
    assert not (work / "mine2.txt").exists()
    (work / "mine2.txt").write_text("newest\n", encoding="utf-8")
    assert [d["what"] for d in Git(work).repair("main")] == ["rebase"]
    assert (work / "mine2.txt").read_text(encoding="utf-8") == "newest\n"


def test_a_repair_killed_after_its_abort_is_finished_by_the_next(tmp_path: Path) -> None:
    work, other = _two_clones(tmp_path)
    _half_sync(work, other)
    (work / "runs" / "state.json").write_text('{"rev": 9}\n', encoding="utf-8")
    g = Git(work)
    g._set_aside()
    g.run("rebase", "--abort")  # killed here: the files are only in .git/tsl-repair
    assert (work / "runs" / "state.json").read_text(encoding="utf-8") != '{"rev": 9}\n'
    assert [d["what"] for d in g.repair("main")] == ["files"]
    assert (work / "runs" / "state.json").read_text(encoding="utf-8") == '{"rev": 9}\n'
    assert not (g.git_dir() / "tsl-repair").exists()


def test_a_failed_sync_says_why(tmp_path: Path) -> None:
    work, other = _two_clones(tmp_path)
    git(work, "switch", "-q", "-c", "mine")
    _half_sync(work, other, "mine")
    g = Git(work)
    assert g.sync_push("main") is False  # stopped by the repair
    assert g.last_error is not None and "refs/heads/mine" in g.last_error.detail
    (tmp_path / "second").mkdir()
    work2, other2 = _two_clones(tmp_path / "second")
    _conflicting(work2, other2)
    g2 = Git(work2)
    assert g2.sync_push("main") is False  # stopped by a conflict during the rebase
    assert g2.last_error is not None and "runs/state.json" in g2.last_error.detail


def test_a_closed_session_that_comes_back_is_the_holder_again(world: World) -> None:
    # The same session id active again after the session-end hook (claude --resume): its new
    # activity makes it a live holder, so another session gets the question, not the run.
    run_id = start_run(world)
    next_action(world, run_id)
    hook(world, "session-end", {"hook_event_name": "SessionEnd"})
    world.clock.advance(minutes=2)
    log = world.companion / f"runs/{run_id}/tool-log.jsonl"
    with log.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"ts": iso(world.clock())}) + "\n")
    assert _resume(world, run_id)[1]["code"] == "E-RUN-11"


def test_a_run_whose_verifier_is_running_is_not_stuck(world: World) -> None:
    run_id = start_run(world)
    next_action(world, run_id)
    world.clock.advance(minutes=45)
    lock = world.companion / f"runs/{run_id}/.local.lock"
    lock.write_text(str(os.getpid()), encoding="utf-8")  # tsl verify holds it while it runs
    assert _progress(world)["stuck"] is None
    lock.write_text("999999", encoding="utf-8")  # a dead process: no longer busy
    assert _progress(world)["stuck"] is not None


# ---------------------------------------------------------- live review of #78 (Yash, 27 Nov)


def test_a_preamble_call_exits_zero_and_still_says_what_failed(world: World) -> None:
    # Claude Code refuses a skill whose !`...` preamble exits non-zero, so /truminds:resume never
    # showed E-RUN-11 and never asked "Is that session closed?". --exit-zero keeps the envelope.
    run_id = start_run(world)
    next_action(world, run_id)
    code, env, _, _ = world.cli(["state", "resume", run_id, "--json"], session=OTHER)
    assert code != 0 and env is not None and env["code"] == "E-RUN-11"
    code, env, _, _ = world.cli(["state", "resume", run_id, "--json", "--exit-zero"], session=OTHER)
    assert code == 0 and env is not None and env["ok"] is False and env["code"] == "E-RUN-11"
    assert env["data"]["holder"]["last_activity_at"]


def test_finishing_an_interrupted_repair_never_overwrites_a_newer_file(tmp_path: Path) -> None:
    # The repair died after its abort; tsl then wrote state.json again before the next sync.
    work, other = _two_clones(tmp_path)
    _half_sync(work, other)
    (work / "runs" / "state.json").write_text('{"rev": 9}\n', encoding="utf-8")
    (work / "runs" / "other.json").write_text("{}\n", encoding="utf-8")
    g = Git(work)
    g._set_aside()
    g.run("rebase", "--abort")  # killed here
    (work / "runs" / "state.json").write_text('{"rev": 10}\n', encoding="utf-8")  # newer
    done = g.repair("main")
    assert [d["what"] for d in done] == ["files"] and "runs/state.json" in done[0]["detail"]
    assert (work / "runs" / "state.json").read_text(encoding="utf-8") == '{"rev": 10}\n'
    assert (work / "runs" / "other.json").read_text(encoding="utf-8") == "{}\n"  # restored
