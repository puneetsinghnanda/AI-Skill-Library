"""Projection handlers, one per event type (SDD-08 §7.2-§7.4). Idempotent upserts only.

Each event's projection and its ``projected_at`` mark commit together, so counter increments
happen exactly once. Late and out-of-order events are handled by the rules in §7.3.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from sqlalchemy import Connection, text

from app.obs import metrics

NIL = "00000000-0000-0000-0000-000000000000"
END_REASONS = {
    "pr_opened",
    "completed",
    "aborted",
    "rejected",
    "cancelled",
    "lock_released",
    "archived",
}
BAND_RANK = {"Low": 0, "Medium": 1, "High": 2}


class Parked(Exception):
    """The event cannot be projected yet (for example an unknown system code); retried later."""

    def __init__(self, code: str, backoff_s: int = 60) -> None:
        super().__init__(code)
        self.code = code
        self.backoff_s = backoff_s


@dataclass(frozen=True)
class Ev:
    event_id: str
    received_at: datetime
    occurred_at: datetime
    clock_skew: bool
    type: str
    schema_version: int
    run_id: str | None
    user_id: str | None
    source: str
    body: dict[str, Any]

    @property
    def t(self) -> datetime:
        """Time used for aggregation: ``received_at`` when the client clock was skewed (§4.1)."""
        return self.received_at if self.clock_skew else self.occurred_at

    @property
    def day(self) -> date:
        return self.t.date()


Handler = Callable[[Connection, Ev], None]


# ----------------------------------------------------------------------------- helpers
def ensure_run(conn: Connection, run_id: str, t: datetime, user_id: str | None = None) -> Any:
    conn.execute(
        text(
            "INSERT INTO runs (id, is_partial, updated_at, user_id) VALUES (:r, true, :t, "
            "CAST(:u "
            "AS uuid)) "
            "ON CONFLICT (id) DO UPDATE SET updated_at = greatest(runs.updated_at, "
            "EXCLUDED.updated_at), "
            "user_id = coalesce(runs.user_id, EXCLUDED.user_id)"
        ),
        {"r": run_id, "t": t, "u": user_id},
    )
    return conn.execute(
        text(
            "SELECT id, system_id::text AS system_id, user_id::text AS user_id, "
            "status_changed_at "
            "FROM runs WHERE id = :r"
        ),
        {"r": run_id},
    ).one()


def status_wins(conn: Connection, run: Any, ev: Ev) -> bool:
    """§7.3: a status change applies only if newer; on a tie the larger event id wins."""
    sca = run.status_changed_at
    if sca is None or ev.occurred_at > sca:
        return True
    if ev.occurred_at < sca:
        return False
    last = conn.execute(
        text(
            "SELECT max(event_id) FROM events_raw WHERE run_id = :r AND occurred_at = :t AND "
            "projected_at IS NOT NULL "
            "AND type IN ('run.started', 'run.status_changed')"
        ),
        {"r": run.id, "t": sca},
    ).scalar()
    return last is None or ev.event_id > last


def _need_run(ev: Ev) -> str:
    if not ev.run_id:
        raise Parked("missing_run_id", 86400)
    return ev.run_id


def touch_session(conn: Connection, run_id: str, session_id: str | None, t: datetime) -> None:
    if not session_id:
        return
    conn.execute(
        text(
            "INSERT INTO run_sessions (run_id, session_id, first_seen_at, last_seen_at) VALUES "
            "(:r, "
            ""
            ":s, :t, :t) "
            "ON CONFLICT (run_id, session_id) DO UPDATE SET first_seen_at = "
            "least(run_sessions.first_seen_at, :t), "
            "last_seen_at = greatest(run_sessions.last_seen_at, :t)"
        ),
        {"r": run_id, "s": session_id, "t": t},
    )


def user_daily(
    conn: Connection, day: date, user_id: str | None, system_id: str | None, col: str
) -> None:
    if not user_id:
        return
    conn.execute(
        text(
            f"INSERT INTO user_daily (day, user_id, system_id, {col}) VALUES (:d, CAST(:u AS "
            "uuid), CAST(:s AS uuid), 1) "
            f"ON CONFLICT (day, user_id, system_id) DO UPDATE SET {col} = user_daily.{col} + 1"
        ),
        {"d": day, "u": user_id, "s": system_id or NIL},
    )


def skill_version_exists(conn: Connection, skill: str, version: str) -> bool:
    return (
        conn.execute(
            text("SELECT 1 FROM skill_versions WHERE skill_id = :k AND version = :v"),
            {"k": skill, "v": version},
        ).first()
        is not None
    )


def key_exists(conn: Connection, key_id: str) -> str | None:
    """The key's owner id, or None when unknown."""
    return conn.execute(
        text("SELECT user_id::text FROM keys WHERE key_id = :k"), {"k": key_id}
    ).scalar()


def anchor(conn: Connection, ev: Ev, kind: str, sha: str | None, key_id: str | None) -> None:
    """SDD-07 §7.2: store only when the key belongs to the event's user; first event wins."""
    if not sha or not key_id:
        return
    owner = key_exists(conn, key_id)
    if owner is None or owner != ev.user_id:
        metrics.ANCHOR_MISMATCH.inc()
        return
    conn.execute(
        text(
            "INSERT INTO signature_anchors (sha256, kind, key_id, event_id, anchored_at) VALUES "
            "(:h, :k, :key, :e, :t) "
            "ON CONFLICT (sha256) DO UPDATE SET anchored_at = "
            "least(signature_anchors.anchored_at, "
            "EXCLUDED.anchored_at), "
            "event_id = CASE WHEN EXCLUDED.anchored_at < signature_anchors.anchored_at THEN "
            "EXCLUDED.event_id "
            "ELSE signature_anchors.event_id END"
        ),
        {"h": sha, "k": kind, "key": key_id, "e": ev.event_id, "t": ev.received_at},
    )


def recompute_run(conn: Connection, run_id: str) -> None:
    """``current_step_id`` (highest seq, then attempt) and ``lowest_band`` (final attempts) "
    "(§7.3)."""
    cur = conn.execute(
        text(
            "SELECT step_id, seq FROM steps WHERE run_id = :r AND (started_at IS NOT NULL OR "
            "decided_at IS NOT NULL) "
            "ORDER BY seq DESC NULLS LAST, attempt DESC LIMIT 1"
        ),
        {"r": run_id},
    ).first()
    finals = (
        conn.execute(
            text(
                "SELECT DISTINCT ON (step_id) band FROM steps WHERE run_id = :r ORDER BY "
                "step_id, "
                "attempt DESC"
            ),
            {"r": run_id},
        )
        .scalars()
        .all()
    )
    bands = [b for b in finals if b in BAND_RANK]
    lowest = min(bands, key=lambda b: BAND_RANK[b]) if bands else None
    conn.execute(
        text(
            "UPDATE runs SET current_step_id = :s, current_seq = :q, lowest_band = :b WHERE id = :r"
        ),
        {
            "s": cur.step_id if cur else None,
            "q": cur.seq if cur else None,
            "b": lowest,
            "r": run_id,
        },
    )


# ----------------------------------------------------------------------------- handlers
def session_event(conn: Connection, ev: Ev) -> None:
    b = ev.body
    if ev.user_id:
        conn.execute(
            text(
                "INSERT INTO devices (device_id, user_id, os, plugin_version, tsl_version, "
                "outbox_depth, outbox_oldest_at, "
                "first_seen_at, last_seen_at, last_session_id) VALUES (:d, CAST(:u AS uuid), "
                ":os, "
                ":pv, :tv, :od, :oo, :t, :t, :s) "
                "ON CONFLICT (device_id) DO UPDATE SET "
                "first_seen_at = least(devices.first_seen_at, EXCLUDED.first_seen_at), "
                "os = CASE WHEN EXCLUDED.last_seen_at >= devices.last_seen_at THEN "
                "coalesce(EXCLUDED.os, devices.os) ELSE devices.os END, "
                "plugin_version = CASE WHEN EXCLUDED.last_seen_at >= devices.last_seen_at "
                "  THEN coalesce(EXCLUDED.plugin_version, devices.plugin_version) ELSE "
                "devices.plugin_version END, "
                "tsl_version = CASE WHEN EXCLUDED.last_seen_at >= devices.last_seen_at "
                "  THEN coalesce(EXCLUDED.tsl_version, devices.tsl_version) ELSE "
                "devices.tsl_version END, "
                "outbox_depth = CASE WHEN EXCLUDED.last_seen_at >= devices.last_seen_at THEN "
                "EXCLUDED.outbox_depth ELSE devices.outbox_depth END, "
                "outbox_oldest_at = CASE WHEN EXCLUDED.last_seen_at >= devices.last_seen_at THEN "
                ""
                "EXCLUDED.outbox_oldest_at "
                "  ELSE devices.outbox_oldest_at END, "
                "last_session_id = CASE WHEN EXCLUDED.last_seen_at >= devices.last_seen_at THEN "
                "EXCLUDED.last_session_id "
                "  ELSE devices.last_session_id END, "
                "last_seen_at = greatest(devices.last_seen_at, EXCLUDED.last_seen_at)"
            ),
            {
                "d": b["device_id"],
                "u": ev.user_id,
                "os": b.get("os"),
                "pv": b.get("plugin_version"),
                "tv": b.get("tsl_version"),
                "od": b.get("outbox_depth"),
                "oo": b.get("outbox_oldest_at"),
                "t": ev.t,
                "s": b.get("session_id"),
            },
        )
    if ev.run_id:
        ensure_run(conn, ev.run_id, ev.t, ev.user_id)
        touch_session(conn, ev.run_id, b.get("session_id"), ev.t)


def run_started(conn: Connection, ev: Ev) -> None:
    run_id = _need_run(ev)
    b = ev.body
    sysrow = conn.execute(
        text("SELECT id::text AS id, project_id::text AS project_id FROM systems WHERE code = :c"),
        {"c": b["system"]},
    ).first()
    if sysrow is None:
        raise Parked("unknown_system", 300)
    pod_id = pod_version = None
    if b.get("pod"):
        pod = conn.execute(
            text("SELECT id, current_version FROM pods WHERE id = :p"), {"p": b["pod"]}
        ).first()
        if pod is None:
            raise Parked("unknown_pod", 300)
        pod_id, pod_version = pod.id, pod.current_version
    run = ensure_run(conn, run_id, ev.t, ev.user_id)
    wins = status_wins(conn, run, ev)
    conn.execute(
        text(
            "UPDATE runs SET system_id = CAST(:s AS uuid), project_id = CAST(:p AS uuid), "
            "workflow_id = :w, "
            "workflow_version = :wv, pod_id = :pod, pod_version = :podv, ticket_ref = :tk, "
            "user_id = coalesce(CAST(:u AS uuid), user_id), plugin_version = :pv, pack_fresh = "
            ":pf, "
            ""
            "started_at = :t, "
            "is_partial = false, "
            "status = CASE WHEN :wins THEN 'RUNNING' ELSE status END, "
            "status_changed_at = CASE WHEN :wins THEN :t ELSE status_changed_at END, "
            "updated_at = greatest(updated_at, :t) WHERE id = :r"
        ),
        {
            "s": sysrow.id,
            "p": sysrow.project_id,
            "w": b["workflow"],
            "wv": b["workflow_version"],
            "pod": pod_id,
            "podv": pod_version,
            "tk": b["ticket_ref"],
            "u": ev.user_id,
            "pv": b["plugin_version"],
            "pf": b.get("pack_fresh"),
            "t": ev.occurred_at,
            "r": run_id,
            "wins": wins,
        },
    )
    touch_session(conn, run_id, b.get("session_id"), ev.t)
    user_daily(conn, ev.day, ev.user_id, sysrow.id, "runs_started")


def run_status_changed(conn: Connection, ev: Ev) -> None:
    run_id = _need_run(ev)
    b = ev.body
    run = ensure_run(conn, run_id, ev.t, ev.user_id)
    to = b["to"]
    if status_wins(conn, run, ev):
        reason = str(b.get("reason_code") or "")
        end_reason = end_code = None
        completed_at = None
        if to == "COMPLETED":
            completed_at = ev.occurred_at
            if reason in END_REASONS:
                end_reason = reason
            elif reason.startswith("E-"):
                end_reason, end_code = "aborted", reason
            else:
                end_reason = "completed"
        conn.execute(
            text(
                "UPDATE runs SET status = :to, status_changed_at = :t, end_reason = "
                "coalesce(:er, "
                "end_reason), "
                "end_code = coalesce(:ec, end_code), completed_at = coalesce(:ca, completed_at), "
                ""
                "updated_at = greatest(updated_at, :t) WHERE id = :r"
            ),
            {
                "to": to,
                "t": ev.occurred_at,
                "er": end_reason,
                "ec": end_code,
                "ca": completed_at,
                "r": run_id,
            },
        )
    if to == "PAUSED_APPROVAL" and b.get("gate"):
        gate_reason = b.get("reason_code")
        conn.execute(
            text(
                "INSERT INTO approvals (run_id, gate, step_id, reason_code, requested_at) VALUES "
                ""
                "(:r, :g, :s, :rc, :t) "
                "ON CONFLICT (run_id, gate) DO UPDATE SET step_id = coalesce(approvals.step_id, "
                "EXCLUDED.step_id), "
                "reason_code = coalesce(EXCLUDED.reason_code, approvals.reason_code), "
                "requested_at = CASE WHEN approvals.recorded_at IS NOT NULL AND "
                "EXCLUDED.requested_at > approvals.recorded_at "
                "  THEN EXCLUDED.requested_at ELSE coalesce(approvals.requested_at, "
                "EXCLUDED.requested_at) END, "
                "decision = CASE WHEN approvals.recorded_at IS NOT NULL AND "
                "EXCLUDED.requested_at > "
                ""
                "approvals.recorded_at "
                "  THEN NULL ELSE approvals.decision END, "
                "recorded_at = CASE WHEN approvals.recorded_at IS NOT NULL AND "
                "EXCLUDED.requested_at > approvals.recorded_at "
                "  THEN NULL ELSE approvals.recorded_at END"
            ),
            {
                "r": run_id,
                "g": b["gate"],
                "s": b.get("step"),
                "rc": gate_reason if str(gate_reason or "").startswith("E-") else None,
                "t": ev.occurred_at,
            },
        )
    touch_session(conn, run_id, b.get("session_id"), ev.t)


def step_started(conn: Connection, ev: Ev) -> None:
    run_id = _need_run(ev)
    b = ev.body
    if not skill_version_exists(conn, b["skill"], b["skill_version"]):
        raise Parked("unknown_skill_version", 300)
    ensure_run(conn, run_id, ev.t, ev.user_id)
    conn.execute(
        text(
            "INSERT INTO steps (run_id, step_id, attempt, seq, skill_id, skill_version, "
            "started_at) "
            ""
            ""
            "VALUES (:r, :s, :a, :q, :k, :v, :t) ON CONFLICT (run_id, step_id, attempt) DO "
            "UPDATE "
            "SET "
            "seq = coalesce(steps.seq, EXCLUDED.seq), skill_id = coalesce(steps.skill_id, "
            "EXCLUDED.skill_id), "
            "skill_version = coalesce(steps.skill_version, EXCLUDED.skill_version), started_at = "
            ""
            "EXCLUDED.started_at"
        ),
        {
            "r": run_id,
            "s": b["step"],
            "a": b["attempt"],
            "q": b["seq"],
            "k": b["skill"],
            "v": b["skill_version"],
            "t": ev.occurred_at,
        },
    )
    touch_session(conn, run_id, b.get("session_id"), ev.t)
    recompute_run(conn, run_id)


def step_decided(conn: Connection, ev: Ev) -> None:
    run_id = _need_run(ev)
    b = ev.body
    if not skill_version_exists(conn, b["skill"], b["skill_version"]):
        raise Parked("unknown_skill_version", 300)
    if key_exists(conn, b["key_id"]) is None:
        raise Parked("unknown_key", 300)
    run = ensure_run(conn, run_id, ev.t, ev.user_id)
    fc = b["findings_count"]
    conn.execute(
        text(
            "INSERT INTO steps (run_id, step_id, attempt, seq, skill_id, skill_version, "
            "attempt_cause, decided_at, outcome, "
            "band, signals, reasons, caps, gate_failures, findings_blocker, findings_major, "
            "findings_minor, duration_ms) "
            "VALUES (:r, :s, :a, :q, :k, :v, :c, :t, :o, :band, CAST(:sig AS jsonb), :rs, :caps, "
            ""
            ":gf, :fb, :fm, :fn, :d) "
            "ON CONFLICT (run_id, step_id, attempt) DO UPDATE SET seq = EXCLUDED.seq, skill_id = "
            ""
            "EXCLUDED.skill_id, "
            "skill_version = EXCLUDED.skill_version, attempt_cause = EXCLUDED.attempt_cause, "
            "decided_at = EXCLUDED.decided_at, "
            "outcome = EXCLUDED.outcome, band = EXCLUDED.band, signals = EXCLUDED.signals, "
            "reasons "
            "= EXCLUDED.reasons, "
            "caps = EXCLUDED.caps, gate_failures = EXCLUDED.gate_failures, findings_blocker = "
            "EXCLUDED.findings_blocker, "
            "findings_major = EXCLUDED.findings_major, findings_minor = EXCLUDED.findings_minor, "
            ""
            "duration_ms = EXCLUDED.duration_ms"
        ),
        {
            "r": run_id,
            "s": b["step"],
            "a": b["attempt"],
            "q": b["seq"],
            "k": b["skill"],
            "v": b["skill_version"],
            "c": b.get("cause"),
            "t": ev.occurred_at,
            "o": b["outcome"],
            "band": b.get("band"),
            "sig": json.dumps(b["signals"]),
            "rs": list(b["reasons"]),
            "caps": list(b["caps"]),
            "gf": list(b["gate_failures"]),
            "fb": fc["blocker"],
            "fm": fc["major"],
            "fn": fc["minor"],
            "d": b["duration_ms"],
        },
    )
    conn.execute(
        text(
            "INSERT INTO check_records (run_id, step_id, attempt, verification_sha256, key_id, "
            "decided_by, decided_at, "
            "findings_dropped) VALUES (:r, :s, :a, :h, :k, :by, :t, :fd) ON CONFLICT (run_id, "
            "step_id, attempt) DO UPDATE SET "
            "verification_sha256 = EXCLUDED.verification_sha256, key_id = EXCLUDED.key_id, "
            "decided_by = EXCLUDED.decided_by, "
            "decided_at = EXCLUDED.decided_at, findings_dropped = EXCLUDED.findings_dropped"
        ),
        {
            "r": run_id,
            "s": b["step"],
            "a": b["attempt"],
            "h": b["verification_sha256"],
            "k": b["key_id"],
            "by": b["decided_by"],
            "t": ev.occurred_at,
            "fd": list(b.get("findings_dropped") or []),
        },
    )
    conn.execute(
        text("UPDATE runs SET updated_at = greatest(updated_at, :t) WHERE id = :r"),
        {"t": ev.t, "r": run_id},
    )
    anchor(conn, ev, "verification", b["verification_sha256"], b["key_id"])
    touch_session(conn, run_id, b.get("session_id"), ev.t)
    recompute_run(conn, run_id)
    user_daily(conn, ev.day, run.user_id or ev.user_id, run.system_id, "steps_decided")


def question_created(conn: Connection, ev: Ev) -> None:
    run_id = _need_run(ev)
    b = ev.body
    ensure_run(conn, run_id, ev.t, ev.user_id)
    conn.execute(
        text(
            "INSERT INTO questions (run_id, question_id, step_id, blocking, ask_role, "
            "evidence_ref, "
            ""
            "created_at) "
            "VALUES (:r, :q, :s, :b, :ar, :e, :t) ON CONFLICT (run_id, question_id) DO UPDATE "
            "SET "
            "step_id = EXCLUDED.step_id, blocking = EXCLUDED.blocking, ask_role = "
            "EXCLUDED.ask_role, "
            "evidence_ref = EXCLUDED.evidence_ref, created_at = EXCLUDED.created_at"
        ),
        {
            "r": run_id,
            "q": b["question_id"],
            "s": b["step"],
            "b": b["blocking"],
            "ar": b["ask_role"],
            "e": b.get("evidence_ref"),
            "t": ev.occurred_at,
        },
    )


def question_answered(conn: Connection, ev: Ev) -> None:
    run_id = _need_run(ev)
    b = ev.body
    ensure_run(conn, run_id, ev.t, ev.user_id)
    conn.execute(
        text(
            "INSERT INTO questions (run_id, question_id, step_id, answered_at, accepted_default) "
            ""
            "VALUES (:r, :q, :s, :t, :ad) "
            "ON CONFLICT (run_id, question_id) DO UPDATE SET answered_at = EXCLUDED.answered_at, "
            ""
            "accepted_default = EXCLUDED.accepted_default, step_id = coalesce(questions.step_id, "
            ""
            "EXCLUDED.step_id)"
        ),
        {
            "r": run_id,
            "q": b["question_id"],
            "s": b["step"],
            "t": ev.occurred_at,
            "ad": b.get("accepted_default"),
        },
    )


def approval_recorded(conn: Connection, ev: Ev) -> None:
    run_id = _need_run(ev)
    b = ev.body
    ensure_run(conn, run_id, ev.t, ev.user_id)
    conn.execute(
        text(
            "INSERT INTO approvals (run_id, gate, step_id, decision, approver_user_id, "
            "approver_role, recorded_at) "
            "VALUES (:r, :g, :s, :d, CAST(:u AS uuid), :ar, :t) ON CONFLICT (run_id, gate) DO "
            "UPDATE SET "
            "step_id = coalesce(EXCLUDED.step_id, approvals.step_id), decision = "
            "EXCLUDED.decision, "
            ""
            ""
            "approver_user_id = EXCLUDED.approver_user_id, approver_role = "
            "EXCLUDED.approver_role, "
            "recorded_at = EXCLUDED.recorded_at WHERE approvals.recorded_at IS NULL OR "
            "approvals.recorded_at <= EXCLUDED.recorded_at"
        ),
        {
            "r": run_id,
            "g": b["gate"],
            "s": b.get("step"),
            "d": b["decision"],
            "u": ev.user_id,
            "ar": b["approver_role"],
            "t": ev.occurred_at,
        },
    )
    anchor(conn, ev, "approval", b.get("signature_block_sha256"), b.get("key_id"))


def hook_decision(conn: Connection, ev: Ev) -> None:
    b = ev.body
    system_id = None
    if ev.run_id:
        system_id = conn.execute(
            text("SELECT system_id::text FROM runs WHERE id = :r"), {"r": ev.run_id}
        ).scalar()
    conn.execute(
        text(
            "INSERT INTO hook_daily (day, system_id, hook, decision, code, n) VALUES (:d, "
            "CAST(:s "
            "AS uuid), :h, :dec, :c, 1) "
            "ON CONFLICT (day, system_id, hook, decision, code) DO UPDATE SET n = hook_daily.n + "
            "1"
        ),
        {
            "d": ev.day,
            "s": system_id or NIL,
            "h": b["hook"],
            "dec": b["decision"],
            "c": b.get("code") or "",
        },
    )


def pr_opened(conn: Connection, ev: Ev) -> None:
    run_id = _need_run(ev)
    b = ev.body
    run = ensure_run(conn, run_id, ev.t, ev.user_id)
    if run.system_id is None:
        raise Parked("run_partial", 120)
    repo = conn.execute(
        text("SELECT id::text FROM system_repos WHERE system_id = CAST(:s AS uuid) AND name = :n"),
        {"s": run.system_id, "n": b["repo"]},
    ).scalar()
    if repo is None:
        raise Parked("unknown_repo", 300)
    conn.execute(
        text(
            "INSERT INTO pull_requests (repo_id, number, run_id, state, draft, lowest_band, "
            "opened_at) "
            "VALUES (CAST(:p AS uuid), :n, :r, 'open', :d, :lb, :t) ON CONFLICT (repo_id, "
            "number) "
            "DO UPDATE SET "
            "run_id = coalesce(pull_requests.run_id, EXCLUDED.run_id), draft = "
            "coalesce(pull_requests.draft, EXCLUDED.draft), "
            "lowest_band = EXCLUDED.lowest_band, opened_at = coalesce(pull_requests.opened_at, "
            "EXCLUDED.opened_at)"
        ),
        {
            "p": repo,
            "n": b["number"],
            "r": run_id,
            "d": b["draft"],
            "lb": b.get("lowest_band"),
            "t": ev.occurred_at,
        },
    )


def pr_closed(conn: Connection, ev: Ev) -> None:
    """tsl pr-sync: a merge or close the webhook missed. A merged PR stays merged."""
    run_id = _need_run(ev)
    b = ev.body
    run = ensure_run(conn, run_id, ev.t, ev.user_id)
    if run.system_id is None:
        raise Parked("run_partial", 120)
    repo = conn.execute(
        text("SELECT id::text FROM system_repos WHERE system_id = CAST(:s AS uuid) AND name = :n"),
        {"s": run.system_id, "n": b["repo"]},
    ).scalar()
    if repo is None:
        raise Parked("unknown_repo", 300)
    state, col = ("merged", "merged_at") if b["merged"] else ("closed", "closed_at")
    conn.execute(
        text(
            f"INSERT INTO pull_requests (repo_id, number, run_id, state, {col}) "
            "VALUES (CAST(:p AS uuid), :n, :r, :st, CAST(:t AS timestamptz)) "
            "ON CONFLICT (repo_id, number) DO UPDATE SET "
            "run_id = coalesce(pull_requests.run_id, EXCLUDED.run_id), "
            "state = CASE WHEN pull_requests.state = 'merged' THEN 'merged' "
            "ELSE EXCLUDED.state END, "
            f"{col} = coalesce(pull_requests.{col}, EXCLUDED.{col})"
        ),
        {"p": repo, "n": b["number"], "r": run_id, "st": state, "t": b["closed_at"]},
    )


def ci_verified(conn: Connection, ev: Ev) -> None:
    b = ev.body
    repos = (
        conn.execute(text("SELECT id::text FROM system_repos WHERE name = :n"), {"n": b["repo"]})
        .scalars()
        .all()
    )
    pr = None
    if repos:
        pr = conn.execute(
            text(
                "SELECT repo_id::text AS repo_id, run_id FROM pull_requests WHERE repo_id = "
                "ANY(CAST(:ids AS uuid[])) "
                "AND number = :n ORDER BY opened_at DESC NULLS LAST LIMIT 1"
            ),
            {"ids": list(repos), "n": b["number"]},
        ).first()
    if pr is not None:
        repo_id = pr.repo_id
    elif len(repos) == 1:
        repo_id = repos[0]
    elif not repos:
        raise Parked("unknown_repo", 300)
    else:
        raise Parked("ambiguous_repo", 300)
    conn.execute(
        text(
            "INSERT INTO ci_checks (repo_id, head_sha, number, result, codes, source, "
            "checked_at) "
            "VALUES (CAST(:p AS uuid), :h, :n, :res, :c, 'event', :t) ON CONFLICT (repo_id, "
            "head_sha, source) DO UPDATE SET "
            "number = EXCLUDED.number, result = EXCLUDED.result, codes = EXCLUDED.codes, "
            "checked_at "
            ""
            "= EXCLUDED.checked_at "
            "WHERE ci_checks.checked_at <= EXCLUDED.checked_at"
        ),
        {
            "p": repo_id,
            "h": b["head_sha"],
            "n": b["number"],
            "res": b["result"],
            "c": list(b["codes"]),
            "t": ev.occurred_at,
        },
    )
    if pr is not None and pr.run_id:
        conn.execute(
            text("UPDATE check_records SET ci_verified = :v WHERE run_id = :r"),
            {"v": b["result"] == "pass", "r": pr.run_id},
        )


def context_event(conn: Connection, ev: Ev) -> None:
    b = ev.body
    sysrow = conn.execute(
        text("SELECT id::text AS id, pack_status_at FROM systems WHERE code = :c"),
        {"c": b["system"]},
    ).first()
    if sysrow is None:
        raise Parked("unknown_system", 300)
    if sysrow.pack_status_at is None or ev.occurred_at > sysrow.pack_status_at:
        signed = ev.type == "context.signed"
        conn.execute(
            text(
                "UPDATE systems SET pack_status = :st, pack_drift_files = :df, pack_status_at = "
                ":t, "
                ""
                ""
                "pack_signed_at = CASE WHEN :signed THEN :t ELSE pack_signed_at END, "
                "pack_signed_by = CASE WHEN :signed THEN CAST(:u AS uuid) ELSE pack_signed_by "
                "END "
                "WHERE id = CAST(:s AS uuid)"
            ),
            {
                "st": b["status"],
                "df": b["drift_files"],
                "t": ev.occurred_at,
                "signed": signed,
                "u": ev.user_id,
                "s": sysrow.id,
            },
        )
    if ev.type == "context.signed":
        anchor(conn, ev, "pack", b.get("signature_sha256"), b.get("key_id"))


def eval_recorded(conn: Connection, ev: Ev) -> None:
    b = ev.body
    if not skill_version_exists(conn, b["skill"], b["version"]):
        raise Parked("unknown_skill_version", 300)
    if key_exists(conn, b["key_id"]) is None:
        raise Parked("unknown_key", 300)
    conn.execute(
        text(
            "UPDATE skill_versions SET eval_cases = :c, eval_pass_rate = :p, eval_key_id = :k, "
            "eval_recorded_at = :t "
            "WHERE skill_id = :s AND version = :v AND (eval_recorded_at IS NULL OR "
            "eval_recorded_at "
            ""
            "<= :t)"
        ),
        {
            "c": b["cases"],
            "p": b["pass_rate"],
            "k": b["key_id"],
            "t": ev.occurred_at,
            "s": b["skill"],
            "v": b["version"],
        },
    )
    anchor(conn, ev, "eval", b.get("result_sha256"), b.get("key_id"))


def security_abort(conn: Connection, ev: Ev) -> None:
    if not ev.run_id:
        return
    ensure_run(conn, ev.run_id, ev.t, ev.user_id)
    conn.execute(
        text("UPDATE runs SET end_code = :c WHERE id = :r"), {"c": ev.body["code"], "r": ev.run_id}
    )


def companion_lifecycle(conn: Connection, ev: Ev) -> None:
    n = conn.execute(
        text("UPDATE systems SET lifecycle_state = :to WHERE code = :c"),
        {"to": ev.body["to"], "c": ev.body["system"]},
    ).rowcount
    if not n:
        raise Parked("unknown_system", 300)


def improvement_proposed(conn: Connection, ev: Ev) -> None:
    b = ev.body
    conn.execute(
        text(
            "INSERT INTO improvements (id, skill_id, from_version, to_version, flag_ids, "
            "owner_id, "
            "before_pass_rate, "
            "after_pass_rate, cases_added, state, created_at, updated_at) VALUES (:i, :k, :f, "
            ":to, "
            ":fl, CAST(:u AS uuid), "
            ":b, :a, :c, 'proposed', :t, :t) ON CONFLICT (id) DO UPDATE SET to_version = "
            "EXCLUDED.to_version, "
            "flag_ids = EXCLUDED.flag_ids, before_pass_rate = EXCLUDED.before_pass_rate, "
            "after_pass_rate = EXCLUDED.after_pass_rate, cases_added = EXCLUDED.cases_added, "
            "updated_at = EXCLUDED.updated_at"
        ),
        {
            "i": b["improvement_id"],
            "k": b["skill"],
            "f": b["from_version"],
            "to": b["to_version"],
            "fl": list(b["flag_ids"]),
            "u": ev.user_id,
            "b": b["before_pass_rate"],
            "a": b["after_pass_rate"],
            "c": b["cases_added"],
            "t": ev.occurred_at,
        },
    )
    conn.execute(
        text(
            "UPDATE skill_flags SET status = 'PROPOSED', updated_at = now() WHERE id = ANY(:ids) "
            ""
            "AND status IN ('OPEN','IN_PROGRESS','REOPENED')"
        ),
        {"ids": list(b["flag_ids"])},
    )


def no_side_effect(conn: Connection, ev: Ev) -> None:
    """Counted in ``ingest_daily`` only (step.invalidated, audit.recorded, "
    "companion.policy_violation)."""
    return None


HANDLERS: dict[tuple[str, int], Handler] = {
    ("session.started", 1): session_event,
    ("session.ended", 1): session_event,
    ("run.started", 1): run_started,
    ("run.status_changed", 1): run_status_changed,
    ("step.started", 1): step_started,
    ("step.decided", 1): step_decided,
    ("step.invalidated", 1): no_side_effect,
    ("question.created", 1): question_created,
    ("question.answered", 1): question_answered,
    ("approval.recorded", 1): approval_recorded,
    ("hook.decision", 1): hook_decision,
    ("pr.opened", 1): pr_opened,
    ("pr.closed", 1): pr_closed,
    ("ci.verified", 1): ci_verified,
    ("context.signed", 1): context_event,
    ("context.drift", 1): context_event,
    ("eval.recorded", 1): eval_recorded,
    ("security.abort", 1): security_abort,
    ("audit.recorded", 1): no_side_effect,
    ("companion.lifecycle", 1): companion_lifecycle,
    ("companion.policy_violation", 1): no_side_effect,
    ("improvement.proposed", 1): improvement_proposed,
}
