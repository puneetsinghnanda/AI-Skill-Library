"""tsl state show --progress: one run's progress for the Mods progress panel (SDD-04 §6, SDD-05).

Read only and local: state.json, approvals.md and open-questions.md of the companion repo. No
network, no git pull, no lock, so the panel can call it after every tsl command. Anything that
cannot be read is left out rather than failing: the panel is a view, never a gate.
"""

from __future__ import annotations

from typing import Any

from tsl.approvals import approvals_md, questions_md
from tsl.core.paths import approvals_path, questions_path
from tsl.core.repo import Companion
from tsl.core.runtime import Runtime
from tsl.state.store import all_runs, latest, read_state_raw

OPEN = ("RUNNING", "PAUSED_INPUT", "PAUSED_APPROVAL")
SETTLED = ("DONE", "ACCEPTED", "APPROVED")
MAX_QUESTIONS = 10
TEXT = 300


def _bound(st: dict[str, Any], session: str | None) -> bool:
    act = st.get("active_session") or {}
    return bool(session) and act.get("session_id") == str(session)[:128]


def _read(comp: Companion, rid: str) -> dict[str, Any] | None:
    """A run's state.json, or None when it cannot be read: one broken file (merge markers, a
    crash mid-write) must not blank the panel for every other run."""
    try:
        return read_state_raw(comp, rid)
    except Exception:
        return None


def _from_index(
    rt: Runtime | None, comp: Companion, session: str
) -> tuple[str, dict[str, Any]] | None:
    """The run this session's index names (the hooks write it on start and resume), if it is
    in this companion repo and still bound: one file read instead of every run's state.json."""
    if rt is None:
        return None
    try:
        import json
        from pathlib import Path

        p = rt.home.session(session)
        if not p.is_file():
            return None
        idx = json.loads(p.read_text(encoding="utf-8"))
        if Path(str(idx["companion"])).resolve() != comp.root.resolve():
            return None
        rid = str(idx["run_id"])
    except Exception:
        return None
    st = _read(comp, rid)
    return (rid, st) if st and _bound(st, session) else None


def pick(
    comp: Companion, session: str | None, rt: Runtime | None = None
) -> tuple[str, dict[str, Any]] | None:
    """The run the panel shows: the run bound to this Claude session (state.json
    active_session), open runs before finished ones, the latest update first; else none.

    Only a bound run: a run stays bound to the session that started or resumed it, also while
    it is paused, and a new session binds it on resume. Falling back to "your latest open run"
    picked runs abandoned weeks ago (a companion repo keeps every run), so the panel shows
    nothing until this session starts or resumes one; /truminds:status lists them all."""
    if not session:
        return None
    hit = _from_index(rt, comp, session)
    if hit is not None:
        return hit
    found: list[tuple[bool, str, str, dict[str, Any]]] = []
    for rid in all_runs(comp):
        st = _read(comp, rid)
        if st and _bound(st, session):
            found.append((st.get("status") in OPEN, str(st.get("updated_at", "")), rid, st))
    if not found:
        return None
    _, _, rid, st = max(found, key=lambda x: (x[0], x[1], x[2]))
    return rid, st


def _steps(st: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for s in st.get("steps", []):
        a = latest(s)
        out.append(
            {
                "id": s["id"],
                "kind": s.get("kind", "skill"),
                "status": s["status"],
                "attempt": int(a["n"]) if a else None,
                "band": (a or {}).get("band"),
            }
        )
    return out


def _waiting(comp: Companion, rid: str, st: dict[str, Any]) -> dict[str, Any] | None:
    status = st.get("status")
    if status == "PAUSED_INPUT":
        return {
            "kind": "input",
            "gate": None,
            "role": None,
            "command": f"/truminds:resume {rid}",
            "file": questions_path(rid),
        }
    if status != "PAUSED_APPROVAL":
        return None
    from tsl.approvals.service import waiting_gates

    try:
        obj = approvals_md.load(comp.path(approvals_path(rid)))
    except Exception:  # a view: a broken approvals.md shows the gate without its role
        obj = {"entries": []}
    gates = waiting_gates(st, obj)
    if gates:
        e = approvals_md.entry(obj, gates[0]) or {}
        return {
            "kind": "approval",
            "gate": gates[0],
            "role": e.get("role"),
            "command": f"/tsl-gate {rid}",
            "file": None,
        }
    signed = waiting_gates(st, obj, signed=True)
    # Signed but not resumed yet: the run owner resumes it. The decision says what resuming
    # does (approve, reject, changes, abort), so the panel never shows a reject as approved.
    gate = signed[0] if signed else None
    e = (approvals_md.entry(obj, gate) or {}) if gate else {}
    return {
        "kind": "resume",
        "gate": gate,
        "role": None,
        "decision": e.get("decision"),
        "command": f"/truminds:resume {rid}",
        "file": None,
    }


def _questions(comp: Companion, rid: str, st: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {"open_blocking": 0, "open_non_blocking": 0, "items": []}
    p = comp.path(questions_path(rid))
    if not p.is_file():
        return out
    try:
        qs = questions_md.parse(p.read_text(encoding="utf-8"))["questions"]
    except Exception:  # a view: an unreadable file shows no questions
        return out
    # Accepted on resume (answered_sha256), with or without an answer: a non-blocking question
    # left empty takes its default then, and is no longer open.
    done = set(((st.get("questions") or {}).get("answered_sha256") or {}).keys())
    open_ = [
        q
        for q in questions_md.effective(qs).values()
        if not q.get("answer") and str(q.get("id")) not in done
    ]
    open_.sort(key=lambda q: (not q.get("blocking"), str(q["id"])))
    out["open_blocking"] = sum(1 for q in open_ if q.get("blocking"))
    out["open_non_blocking"] = len(open_) - out["open_blocking"]
    out["items"] = [
        {
            "id": str(q["id"]),
            "blocking": bool(q.get("blocking")),
            "ask": q.get("ask"),
            "text": " ".join(str(q.get("question", "")).split())[:TEXT],
        }
        for q in open_[:MAX_QUESTIONS]
    ]
    return out


def _current(st: dict[str, Any], steps: list[dict[str, Any]]) -> str | None:
    """The step the run is on. tsl decide clears the cursor after every decision, also the one
    that pauses the run, so fall back to the step that waits, else the first one not settled."""
    cur = (st.get("cursor") or {}).get("step")
    if cur:
        return str(cur)
    if st.get("status") == "COMPLETED":
        return None
    waits = next((s for s in steps if s["status"] in ("WAITING_INPUT", "WAITING_APPROVAL")), None)
    if waits is not None:
        return str(waits["id"])
    todo = next((s for s in steps if s["status"] not in SETTLED), None)
    return str(todo["id"]) if todo else None


def progress(
    rt: Runtime, comp: Companion, run_id: str | None, session: str | None
) -> dict[str, Any] | None:
    """The progress of `run_id`, or of the run pick() chooses; None when there is none."""
    if run_id:
        st = _read(comp, run_id)
        if st is None:
            from tsl.core.errors import TslError

            raise TslError("E-RUN-04", run_id=run_id)
        rid = run_id
    else:
        got = pick(comp, session, rt)
        if got is None:
            return None
        rid, st = got
    steps = _steps(st)
    cur = _current(st, steps)
    idx = next((i for i, s in enumerate(steps) if s["id"] == cur), None)
    return {
        "run_id": rid,
        "ticket": st["ticket"],
        "workflow": st["workflow"],
        "status": st["status"],
        "end_reason": st.get("end_reason"),
        "updated_at": st["updated_at"],
        "bound": _bound(st, session),
        "current": cur,
        "position": {"n": idx + 1, "of": len(steps)} if idx is not None else None,
        "steps": steps,
        "waiting": _waiting(comp, rid, st),
        "questions": _questions(comp, rid, st)
        if st["status"] != "COMPLETED"
        else {"open_blocking": 0, "open_non_blocking": 0, "items": []},
    }
