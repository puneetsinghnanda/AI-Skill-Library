"""A loaded run: state, snapshot, pinned skills and helpers shared by run-bound commands."""

from __future__ import annotations

from functools import cached_property
from typing import Any

from tsl.core.clock import parse_iso
from tsl.core.config import ORG_DEFAULTS
from tsl.core.errors import TslError
from tsl.core.hashing import sha256_file
from tsl.core.jsonio import read_yaml
from tsl.core.paths import artifact_path, questions_path, snapshot_path
from tsl.core.repo import Companion
from tsl.core.runtime import Runtime
from tsl.orchestrator import skills as skillmod
from tsl.orchestrator.skills import Skill
from tsl.orchestrator.workflow import skill_name, step_id, step_kind
from tsl.state import lock as lockmod
from tsl.state.store import RunStore, final_ok_attempt, find_step
from tsl.telemetry.emit import emit


def _why(exc: Any) -> str:
    """': <why>. <what to do>' from the GitError that stopped a sync, or '' (D2)."""
    if exc is None:
        return ""
    return f": {exc.detail}" + (f". {exc.next}" if exc.next else "")


SESSION_WINDOW_S = 15 * 60
# The session-end hook's own save lands a moment after ended_at; later activity is a live holder.
ENDED_SLACK_S = 5


class RunCtx:
    def __init__(self, rt: Runtime, comp: Companion, run_id: str) -> None:
        self.rt = rt
        self.comp = comp
        self.run_id = run_id
        self.store = RunStore(rt, comp, run_id)
        self.state = self.store.load()

    def reload(self) -> dict[str, Any]:
        self.state = self.store.load()
        return self.state

    @cached_property
    def snapshot(self) -> dict[str, Any]:
        data = read_yaml(self.comp.path(snapshot_path(self.run_id)))
        if not isinstance(data, dict):
            raise TslError("E-RUN-04", run_id=self.run_id)
        return data

    @property
    def ticket(self) -> str:
        return str(self.state["ticket"])

    @property
    def workflow_id(self) -> str:
        return str(self.state["workflow"]).split("@", 1)[0]

    def step_def(self, sid: str) -> dict[str, Any]:
        for s in self.snapshot["steps"]:
            if step_id(s) == sid:
                return dict(s)
        raise TslError("E-RUN-09", step=sid, run_id=self.run_id)

    def step(self, sid: str) -> dict[str, Any]:
        return find_step(self.state, sid)

    @cached_property
    def installed(self) -> dict[str, Skill]:
        return skillmod.installed(self.rt.plugin_root())

    def skill_for(self, sid: str) -> Skill:
        name = skill_name(self.step_def(sid))
        pinned = self.state["pinned"]["skills"].get(name)
        sk = self.installed.get(name)
        if sk is None or sk.version != pinned:
            raise TslError(
                "E-RUN-10",
                detail=f"{name}@{pinned} (installed {sk.version if sk else 'none'})",
                run_id=self.run_id,
            )
        return sk

    def artifact_rel(self, sid: str) -> str:
        return artifact_path(self.ticket, self.run_id, sid)

    def retry_limits(self, sid: str) -> dict[str, int]:
        base = dict(ORG_DEFAULTS["retry"])
        base.update((self.snapshot.get("defaults") or {}).get("retry") or {})
        base.update(self.step_def(sid).get("retry") or {})
        return {k: min(int(v), ORG_DEFAULTS["retry"][k]) for k, v in base.items()}

    @property
    def max_rework(self) -> int:
        return int(
            (self.snapshot.get("defaults") or {}).get("max_rework", ORG_DEFAULTS["max_rework"])
        )

    @property
    def requires_fresh_pack(self) -> bool:
        return bool(self.snapshot.get("requires_fresh_pack", True))

    def emit(self, type_: str, body: dict[str, Any], with_run: bool = True) -> None:
        emit(
            self.rt,
            type_,
            body,
            self.run_id if with_run else None,
            enabled=self.comp.config.telemetry_enabled,
        )

    # ---- guards (SDD-02 §11)
    def assert_lock_held(self) -> None:
        if self.state["status"] == "COMPLETED":
            return
        if not lockmod.lock_is_held(self.comp, self.state):
            prev = self.state["status"]

            def close(st: dict[str, Any]) -> None:
                st["status"], st["end_reason"], st["cursor"] = "COMPLETED", "lock_released", None

            self.state = self.store.update(close)
            self.emit(
                "run.status_changed",
                {"from": prev, "to": "COMPLETED", "reason_code": "lock_released"},
            )
            raise TslError("E-LOCK-02", run_id=self.run_id)

    def assert_session(self) -> None:
        """Another session holds the run. It may take it over when that session closed (the
        session-end hook set ended_at) or did nothing for SESSION_WINDOW_S; else E-RUN-11
        with when it was last active, so the engineer can say whether it is gone (D2)."""
        sid = self.rt.session_id()
        act = self.state.get("active_session")
        if not sid or not act or act.get("session_id") == sid:
            return
        from tsl.core.clock import iso
        from tsl.state.stuck import last_activity

        stamps = [self.state.get("heartbeat_at"), act.get("since")]
        known = [parse_iso(str(s)) for s in stamps if s]
        if (seen := last_activity(self.comp.root, self.run_id, self.state)) is not None:
            known.append(seen)
        last = max(known) if known else None
        if act.get("ended_at"):
            # Closed, unless it did something after: a session resumed with the same id
            # (claude --resume) is the holder again, and the question below applies.
            ended = parse_iso(str(act["ended_at"]))
            if last is None or (last - ended).total_seconds() <= ENDED_SLACK_S:
                return
        if last and (self.rt.clock() - last).total_seconds() < SESSION_WINDOW_S:
            raise TslError(
                "E-RUN-11",
                run_id=self.run_id,
                data={
                    "holder": {
                        "session_id": str(act.get("session_id"))[:12],
                        "last_activity_at": iso(last),
                        "since": act.get("since"),
                    }
                },
            )

    # ---- inputs (SDD-02 §3.3)
    def resolve_inputs(self, sid: str) -> list[dict[str, Any]]:
        sdef = self.step_def(sid)
        sk = self.skill_for(sid)
        binds: dict[str, str] = dict(sdef.get("inputs") or {})
        out: list[dict[str, Any]] = []
        seen: set[str] = set()

        def add(
            name: str, rel: str, schema: str | None, producer: str | None, required: bool
        ) -> None:
            if rel in seen:
                return
            seen.add(rel)
            p = self.comp.path(rel)
            out.append(
                {
                    "name": name,
                    "path": rel,
                    "schema": schema,
                    "step": producer,
                    "required": required,
                    "sha256": sha256_file(p) if p.is_file() else None,
                }
            )

        for inp in sk.meta["inputs"]:
            name, src = str(inp["name"]), inp["source"]
            req = bool(inp.get("required", True))
            if src == "run":
                add(
                    name,
                    f"artifacts/{self.ticket}/{self.run_id}/ticket.md",
                    inp.get("schema"),
                    None,
                    req,
                )
            elif src == "context":
                add(name, str(inp["path"]), None, None, req)
            elif src == "artifact":
                b = binds.get(name) or next(
                    (v for k, v in binds.items() if self._binding_schema(v) == inp.get("schema")),
                    None,
                )
                if b:
                    prod = b.split(".", 1)[0]
                    add(name, self._final_artifact(prod), inp.get("schema"), prod, req)
                elif req:
                    out.append(
                        {
                            "name": name,
                            "path": "",
                            "schema": inp.get("schema"),
                            "step": None,
                            "required": True,
                            "sha256": None,
                        }
                    )
        for name, b in binds.items():
            if b == "run.ticket":
                add(
                    name,
                    f"artifacts/{self.ticket}/{self.run_id}/ticket.md",
                    "ticket-snapshot.v1",
                    None,
                    True,
                )
            elif b.startswith("context."):
                sec = b.split(".", 1)[1].split("#", 1)[0]
                rel = (
                    f"context/{sec}" if "/" in sec or sec.endswith(".json") else f"context/{sec}.md"
                )
                add(name, rel, None, None, True)
            elif name not in {str(i["name"]) for i in sk.meta["inputs"]}:
                prod = b.split(".", 1)[0]
                add(name, self._final_artifact(prod), self._binding_schema(b), prod, True)
        return out

    def _binding_schema(self, b: str) -> str | None:
        if b == "run.ticket" or b.startswith("context."):
            return None
        prod, outname = b.split(".", 1)
        try:
            psk = self.skill_for(prod)
        except TslError:
            return None
        return next(
            (str(o.get("schema")) for o in psk.meta["outputs"] if o["name"] == outname), None
        )

    def _final_artifact(self, sid: str) -> str:
        st = self.step(sid)
        a = final_ok_attempt(st)
        return str(a["artifact"]) if a and a.get("artifact") else self.artifact_rel(sid)

    def final_sha(self, sid: str) -> str | None:
        a = final_ok_attempt(self.step(sid))
        return str(a["artifact_sha256"]) if a and a.get("artifact_sha256") else None

    def progress(self, sid: str) -> dict[str, int]:
        ids = [step_id(s) for s in self.snapshot["steps"]]
        return {"index": ids.index(sid) + 1, "total": len(ids)}

    def kinds(self) -> dict[str, str]:
        return {step_id(s): step_kind(s) for s in self.snapshot["steps"]}

    def questions_rel(self) -> str:
        return questions_path(self.run_id)

    def push_best_effort(self, message: str, warnings: list[dict[str, str]]) -> None:
        from tsl.gitops.git import GitError

        try:
            self.comp.git.commit(
                message,
                [
                    f"runs/{self.run_id}",
                    f"artifacts/{self.ticket}/{self.run_id}",
                    lockmod.lock_rel(self.state),
                ],
                trailer=f"Tsl-Run: {self.run_id}",
            )
        except GitError as exc:
            hint = f". {exc.next}" if exc.next else ""
            warnings.append(
                {"code": "E-GIT-01", "message": f"commit failed; files kept locally{hint}"}
            )
            return
        if not self.comp.git.sync_push(self.comp.config.companion_branch):
            warnings.append(
                {
                    "code": "E-GIT-01",
                    "message": "push failed; commits kept locally, next push retries"
                    + _why(self.comp.git.last_error),
                }
            )
