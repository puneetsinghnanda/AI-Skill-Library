"""run-state.v1 persistence: optimistic rev, atomic writes, same-machine lock (SDD-02 §11.2)."""

from __future__ import annotations

import contextlib
import os
import time
from collections.abc import Callable, Iterator
from typing import Any

from tsl.core.clock import iso
from tsl.core.errors import TslError
from tsl.core.jsonio import read_json, write_json
from tsl.core.paths import state_path
from tsl.core.repo import Companion
from tsl.core.runtime import Runtime

LOCAL_WAIT_S = 5.0


class RevConflict(Exception):
    pass


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


class RunStore:
    def __init__(self, rt: Runtime, comp: Companion, run_id: str) -> None:
        self.rt = rt
        self.comp = comp
        self.run_id = run_id
        self.path = comp.path(state_path(run_id))

    def exists(self) -> bool:
        return self.path.is_file()

    def load(self) -> dict[str, Any]:
        if not self.path.is_file():
            raise TslError("E-RUN-04", run_id=self.run_id)
        from tsl.schemas.registry import errors, readable

        data = read_json(self.path)
        sid = readable(str(data.get("schema", "")), state_path(self.run_id))
        errs = errors(sid or "run-state.v1", data)
        if errs:
            raise TslError(
                "E-CFG-01",
                file=state_path(self.run_id),
                pointer=errs[0].pointer,
                reason=errs[0].message,
            )
        return dict(data)

    def save(self, state: dict[str, Any], expected_rev: int) -> dict[str, Any]:
        from tsl.schemas.registry import errors

        if self.path.is_file():
            current = read_json(self.path)
            if int(current.get("rev", 0)) != expected_rev:
                raise RevConflict()
        state["rev"] = expected_rev + 1
        now = iso(self.rt.clock())
        state["updated_at"] = now
        state["heartbeat_at"] = now
        errs = errors("run-state.v1", state)
        if errs:
            raise TslError(
                "E-INT-01",
                f"state would be invalid: {errs[0].pointer} {errs[0].message}",
                log_id="state",
            )
        write_json(self.path, state)
        return state

    def update(self, fn: Callable[[dict[str, Any]], Any]) -> dict[str, Any]:
        """Re-read rev, apply, write rev+1; re-apply once on conflict, then E-RUN-11."""
        for _ in range(2):
            st = self.load()
            rev = int(st["rev"])
            fn(st)
            try:
                return self.save(st, rev)
            except RevConflict:
                continue
        raise TslError("E-RUN-11", run_id=self.run_id)

    @contextlib.contextmanager
    def local_lock(self) -> Iterator[None]:
        """runs/<run_id>/.local.lock with O_CREAT|O_EXCL; wait up to 5 s; dead pid removed."""
        p = self.comp.path(f"runs/{self.run_id}/.local.lock")
        p.parent.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + LOCAL_WAIT_S
        while True:
            try:
                fd = os.open(str(p), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                os.write(fd, str(os.getpid()).encode())
                os.close(fd)
                break
            except FileExistsError:
                try:
                    pid = int(p.read_text().strip() or "0")
                except (OSError, ValueError):
                    pid = 0
                if not _pid_alive(pid):
                    with contextlib.suppress(OSError):
                        p.unlink()
                    continue
                if time.monotonic() >= deadline:
                    raise TslError("E-RUN-11", run_id=self.run_id) from None
                time.sleep(0.1)
        try:
            yield
        finally:
            with contextlib.suppress(OSError):
                p.unlink()


def find_step(state: dict[str, Any], sid: str) -> dict[str, Any]:
    steps: list[dict[str, Any]] = state["steps"]
    for s in steps:
        if s["id"] == sid:
            return s
    raise TslError("E-RUN-09", step=sid, run_id=state["run_id"])


def latest(step: dict[str, Any]) -> dict[str, Any] | None:
    attempts: list[dict[str, Any]] = step.get("attempts") or []
    return attempts[-1] if attempts else None


def final_ok_attempt(step: dict[str, Any]) -> dict[str, Any] | None:
    """Latest attempt with PASS/PWF, or the latest when the step was ACCEPTED at a gate."""
    attempts: list[dict[str, Any]] = step.get("attempts", [])
    for a in attempts[::-1]:
        if a.get("outcome") in ("PASS", "PASS-WITH-FINDINGS"):
            return a
        if step.get("status") == "ACCEPTED" and a.get("outcome") == "ESCALATE":
            return a
    return None


def all_runs(comp: Companion) -> list[str]:
    runs = comp.path("runs")
    if not runs.is_dir():
        return []
    return sorted(
        p.name for p in runs.iterdir() if p.name.startswith("run_") and (p / "state.json").is_file()
    )


def read_state_raw(comp: Companion, run_id: str) -> dict[str, Any] | None:
    p = comp.path(state_path(run_id))
    if not p.is_file():
        return None
    data = read_json(p)
    return data if isinstance(data, dict) else None


def write_new(rt: Runtime, comp: Companion, state: dict[str, Any]) -> None:
    from tsl.schemas.registry import errors

    errs = errors("run-state.v1", state)
    if errs:
        raise TslError(
            "E-INT-01", f"state invalid: {errs[0].pointer} {errs[0].message}", log_id="state"
        )
    write_json(comp.path(state_path(state["run_id"])), state)
