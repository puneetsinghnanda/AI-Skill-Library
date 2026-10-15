"""Run lock: one file per ticket and workflow, taken by git push (SDD-02 §11.1, SDD-12 §3.3)."""

from __future__ import annotations

import contextlib
from typing import Any

from tsl.core.clock import iso, parse_iso
from tsl.core.errors import TslError
from tsl.core.jsonio import atomic_write, loads_strict, read_json, write_json
from tsl.core.paths import lock_path
from tsl.core.repo import Companion
from tsl.core.runtime import Runtime
from tsl.gitops.git import GitError


def read_lock(comp: Companion, rel: str, ref: str | None = None) -> dict[str, Any] | None:
    if ref is not None:
        raw = comp.git.show(ref, rel)
        if raw is None:
            return None
        data = loads_strict(raw.decode("utf-8"))
    else:
        p = comp.path(rel)
        if not p.is_file():
            return None
        data = read_json(p)
    return data if isinstance(data, dict) else None


def lock_body(rt: Runtime, run_id: str, holder: str, key_id: str) -> dict[str, Any]:
    now = iso(rt.clock())
    return {
        "schema": "run-lock.v1",
        "run_id": run_id,
        "holder": holder,
        "key_id": key_id,
        "created_at": now,
        "heartbeat_at": now,
    }


def _held(lock: dict[str, Any], ticket: str, workflow: str) -> TslError:
    return TslError(
        "E-LOCK-01",
        ticket=ticket,
        workflow=workflow,
        holder=lock.get("holder", "?"),
        run_id=lock.get("run_id", "?"),
        next=f"/truminds:resume {lock.get('run_id')}",
        data={"run_id": lock.get("run_id"), "holder": lock.get("holder")},
    )


def take_lock(
    rt: Runtime,
    comp: Companion,
    ticket: str,
    workflow: str,
    run_id: str,
    files: dict[str, str],
    lock: dict[str, Any],
) -> None:
    """Write lock + run files, commit, push with 3 retries; E-LOCK-01/03/04 (SDD-12 §3.3)."""
    rel = lock_path(ticket, workflow)
    git = comp.git
    branch = comp.config.companion_branch
    remote = f"origin/{branch}"
    try:
        git.fetch()
    except GitError:
        raise TslError("E-LOCK-03") from None
    if git.resolve(remote) is not None:
        held = read_lock(comp, rel, remote)
        if held:
            raise _held(held, ticket, workflow)
        try:
            git.rebase(remote)
        except GitError as exc:
            raise exc.tsl() from None
    local = read_lock(comp, rel)
    if local:
        raise _held(local, ticket, workflow)
    write_json(comp.path(rel), lock)
    for path, text in files.items():
        atomic_write(comp.path(path), text)
    written = [rel, *files]
    run_folder = f"runs/{run_id}"
    extra = [p for p in files if not p.startswith(run_folder + "/")]
    try:
        git.commit(
            f"tsl({run_id}): start {workflow} {ticket}",
            [rel, run_folder, *extra],
            trailer=f"Tsl-Run: {run_id}",
        )
    except GitError as exc:
        _cleanup(comp, written)
        raise exc.tsl() from None

    def undo() -> None:
        with contextlib.suppress(GitError):
            git.drop_last_commit()
        _cleanup(comp, written)

    for _ in range(3):
        if git.push(branch):
            return
        try:
            git.fetch()
        except GitError:
            undo()
            raise TslError("E-LOCK-03") from None
        held = read_lock(comp, rel, remote)
        if held:
            undo()
            raise _held(held, ticket, workflow)
        try:
            git.rebase(remote)
        except GitError:
            break
    undo()
    raise TslError("E-LOCK-04")


def _cleanup(comp: Companion, rels: list[str]) -> None:
    """Remove the files this attempt wrote, then any folder it left empty."""
    for r in rels:
        p = comp.path(r)
        with contextlib.suppress(OSError):
            p.unlink()
        parent = p.parent
        while parent != comp.root and parent.name not in ("runs", "active"):
            with contextlib.suppress(OSError):
                parent.rmdir()  # only succeeds when empty
            parent = parent.parent


def heartbeat(rt: Runtime, comp: Companion, state: dict[str, Any]) -> None:
    rel = lock_path(state["ticket"], state["workflow"].split("@", 1)[0])
    lk = read_lock(comp, rel)
    if lk and lk.get("run_id") == state["run_id"]:
        lk["heartbeat_at"] = iso(rt.clock())
        write_json(comp.path(rel), lk)


def lock_rel(state: dict[str, Any]) -> str:
    return lock_path(state["ticket"], state["workflow"].split("@", 1)[0])


def lock_is_held(comp: Companion, state: dict[str, Any]) -> bool:
    lk = read_lock(comp, lock_rel(state))
    return bool(lk and lk.get("run_id") == state["run_id"])


def release(rt: Runtime, comp: Companion, state: dict[str, Any], reason: str) -> bool:
    """Delete the lock (if ours), commit and push best effort. Returns True when pushed."""
    rel = lock_rel(state)
    lk = read_lock(comp, rel)
    if lk and lk.get("run_id") == state["run_id"]:
        comp.path(rel).unlink()
    try:
        comp.git.commit(
            f"tsl({state['run_id']}): {reason}",
            [rel, f"runs/{state['run_id']}", f"artifacts/{state['ticket']}/{state['run_id']}"],
            trailer=f"Tsl-Run: {state['run_id']}",
        )
    except GitError:
        return False
    return comp.git.sync_push(comp.config.companion_branch)


def is_stale(
    rt: Runtime, comp: Companion, state: dict[str, Any] | None, lock: dict[str, Any]
) -> bool:
    """DEF-06: no state change for gates.lock_timeout_hours."""
    hours = comp.config.gates.lock_timeout_hours
    stamp = (state or {}).get("updated_at") or lock.get("heartbeat_at")
    if not stamp:
        return True
    return (rt.clock() - parse_iso(str(stamp))).total_seconds() > hours * 3600
