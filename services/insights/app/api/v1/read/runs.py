"""Runs: E21 ``GET /v1/runs``, E22 ``GET /v1/runs/{run_id}`` (SDD-09 §5.6.12-§5.6.13). Class B.

Every run-level query carries ``system_id = ANY(:systems)``. A run outside scope is E-API-04.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Path, Query, Request
from sqlalchemy import Connection, text

from app.api.deps import portal_read
from app.auth.principal import Principal
from app.auth.scope import Scope
from app.config import Settings
from app.db import tx
from app.errors import ServiceError
from app.read.access import require_engineer_family, systems_filter
from app.read.common import decode_cursor, envelope, limit_of, page, period, scope_meta
from app.read.labels import status_label
from app.read.names import apply_names
from app.timeutil import iso, utcnow

router = APIRouter(tags=["read"])
RUN_ID = r"^run_[0-9A-HJKMNP-TV-Z]{26}$"
STATUS_FILTERS = {
    "open": "r.status <> 'COMPLETED'",
    "RUNNING": "r.status = 'RUNNING'",
    "PAUSED_INPUT": "r.status = 'PAUSED_INPUT'",
    "PAUSED_APPROVAL": "r.status = 'PAUSED_APPROVAL'",
    "completed": "r.status = 'COMPLETED' AND coalesce(r.end_reason, '') <> 'aborted'",
    "aborted": "r.status = 'COMPLETED' AND r.end_reason = 'aborted'",
}
RUN_COLS = (
    "r.id, r.system_id::text AS system_id, r.project_id::text AS project_id, r.ticket_ref, "
    "r.workflow_id, "
    "r.workflow_version, r.pod_id, r.current_step_id, r.current_seq, r.status, r.end_reason, "
    "r.end_code, "
    "r.lowest_band, r.user_id::text AS user_id, u.pseudonym, r.updated_at, r.started_at, "
    "r.is_partial, "
    "coalesce(r.updated_at, r.started_at, 'epoch'::timestamptz) AS sort_ts"
)


def _positions(conn: Connection, rows: Sequence[Any]) -> dict[tuple[str, str], list[str]]:
    keys = {
        (r.workflow_id, r.workflow_version) for r in rows if r.workflow_id and r.workflow_version
    }
    out: dict[tuple[str, str], list[str]] = {}
    for wid, ver in keys:
        out[(wid, ver)] = list(
            conn.execute(
                text(
                    "SELECT step_id FROM workflow_steps WHERE workflow_id = :w AND version = :v "
                    "ORDER BY seq"
                ),
                {"w": wid, "v": ver},
            ).scalars()
        )
    return out


def _last_prs(conn: Connection, run_ids: list[str]) -> dict[str, Any]:
    if not run_ids:
        return {}
    rows = conn.execute(
        text(
            "SELECT DISTINCT ON (run_id) run_id, number, state FROM pull_requests WHERE run_id = "
            ""
            "ANY(:ids) "
            "ORDER BY run_id, opened_at DESC NULLS LAST"
        ),
        {"ids": run_ids},
    ).all()
    return {r.run_id: r for r in rows}


def next_action(r: Any, pr: Any) -> dict[str, Any]:
    if r.status == "RUNNING":
        return {"kind": "none", "text": "None, Claude is working", "command": None}
    if r.status == "PAUSED_INPUT":
        return {
            "kind": "answer_questions",
            "text": "Answer open-questions.md, then resume in Claude Code",
            "command": f"/truminds:resume {r.id}",
        }
    if r.status == "PAUSED_APPROVAL":
        return {
            "kind": "approve",
            "text": "Tech lead approves the open gate",
            "command": f"tsl approve {r.id} <gate>",
        }
    if r.status == "COMPLETED" and r.end_reason == "aborted":
        return {"kind": "none", "text": f"Run aborted: {r.end_code or 'unknown'}", "command": None}
    if r.status == "COMPLETED" and pr is not None:
        word = (
            "merged"
            if pr.state == "merged"
            else ("closed" if pr.state == "closed" else "in review")
        )
        return {"kind": "pr", "text": f"PR #{pr.number} {word}", "command": None}
    return {"kind": "none", "text": "Completed", "command": None}


def run_items(conn: Connection, sc: Scope, me_id: str, rows: Sequence[Any]) -> list[dict[str, Any]]:
    pos = _positions(conn, rows)
    prs = _last_prs(conn, [r.id for r in rows])
    items = []
    for r in rows:
        info = sc.catalogue.get(r.system_id or "")
        steps = pos.get((r.workflow_id, r.workflow_version), [])
        cur = None
        if r.current_step_id:
            cur = {
                "step_id": r.current_step_id,
                "position": steps.index(r.current_step_id) + 1
                if r.current_step_id in steps
                else None,
                "step_count": len(steps) or None,
            }
        items.append(
            {
                "run_id": r.id,
                "project": info.project_code if info else None,
                "system": info.code if info else None,
                "ticket_ref": r.ticket_ref,
                "workflow": r.workflow_id,
                "workflow_version": r.workflow_version,
                "pod": r.pod_id,
                "current_step": cur,
                "status": r.status,
                "end_reason": r.end_reason,
                "end_code": r.end_code,
                "status_label": status_label(r.status, r.end_reason),
                "lowest_band": r.lowest_band,
                "engineer": {"pseudonym": r.pseudonym, "display_name": None},
                "is_mine": r.user_id == me_id,
                "updated_at": iso(r.updated_at),
                "is_partial": r.is_partial,
                "next_action": next_action(r, prs.get(r.id)),
            }
        )
    return items


def list_runs(
    request: Request,
    p: Principal,
    *,
    project: str | None,
    system: str | None,
    status: str | None,
    workflow: str | None,
    pod: str | None,
    owner: str | None,
    period_key: str | None,
    include: str | None,
    limit: int | None,
    cursor: str | None,
    route: str,
) -> dict[str, Any]:
    s: Settings = request.app.state.settings
    n = limit_of(limit)
    if status and status not in STATUS_FILTERS:
        raise ServiceError("E-API-01", "Unknown status filter")
    if owner not in (None, "me"):
        raise ServiceError("E-API-01", "owner must be me")
    if include not in (None, "names"):
        raise ServiceError("E-API-01", "include must be names")
    per = period(period_key, default="all") if period_key else None
    filters = {
        "project": project,
        "system": system,
        "status": status,
        "workflow": workflow,
        "pod": pod,
        "owner": owner,
        "period": period_key,
    }
    after = decode_cursor(cursor, filters)
    with tx("read", s) as conn:
        sc = p.scope(conn, s)
        require_engineer_family(sc)
        assert p.user is not None  # noqa: S101
        systems = systems_filter(sc, project, system)
        where = ["r.system_id = ANY(CAST(:sys AS uuid[]))"]
        params: dict[str, Any] = {"sys": systems, "n": n + 1}
        if status:
            where.append(STATUS_FILTERS[status])
        if workflow:
            where.append("r.workflow_id = :wf")
            params["wf"] = workflow
        if pod:
            where.append("r.pod_id = :pod")
            params["pod"] = pod
        if owner == "me":
            where.append("r.user_id = CAST(:me AS uuid)")
            params["me"] = p.user.id
        if per is not None and per.start is not None:
            where.append("coalesce(r.updated_at, r.started_at)::date BETWEEN :pf AND :pt")
            params |= {"pf": per.start, "pt": per.end}
        if after:
            where.append(
                "(coalesce(r.updated_at, r.started_at, 'epoch'::timestamptz), r.id) < "
                "(CAST(:ca AS timestamptz), :cb)"
            )
            params |= {"ca": after[0], "cb": after[1]}
        rows = conn.execute(
            text(
                f"SELECT {RUN_COLS} FROM runs r LEFT JOIN users u ON u.id = r.user_id WHERE "
                f"{' AND '.join(where)} "
                f"ORDER BY sort_ts DESC, r.id DESC LIMIT :n"
            ),
            params,
        ).all()
        keys = {r.id: [r.sort_ts.isoformat(), r.id] for r in rows}
        items = run_items(conn, sc, p.user.id, rows)
    items, pg = page(items, n, lambda it: keys[it["run_id"]], filters)
    if include == "names":
        eligible = [
            (it["engineer"], r.user_id, sc.catalogue[r.system_id].code)
            for it, r in zip(items, rows, strict=False)
            if sc.can_see_names(r.system_id)
        ]
        apply_names(s, p.user.id, route, items, eligible)
    return envelope({"items": items}, meta={"scope": scope_meta(sc)}, page=pg)


@router.get("/v1/runs", summary="E21 runs in scope (class B)")
def runs(
    request: Request,
    project: str | None = Query(default=None),
    system: str | None = Query(default=None),
    status: str | None = Query(default=None),
    workflow: str | None = Query(default=None, max_length=60),
    pod: str | None = Query(default=None, max_length=60),
    owner: str | None = Query(default=None),
    period_: str | None = Query(default=None, alias="period"),
    include: str | None = Query(default=None),
    limit: int | None = Query(default=None),
    cursor: str | None = Query(default=None),
    p: Principal = Depends(portal_read),
) -> dict[str, Any]:
    return list_runs(
        request,
        p,
        project=project,
        system=system,
        status=status,
        workflow=workflow,
        pod=pod,
        owner=owner,
        period_key=period_,
        include=include,
        limit=limit,
        cursor=cursor,
        route="/v1/runs",
    )


def _age(start: datetime | None, end: datetime | None) -> int | None:
    if start is None:
        return None
    return int(((end or utcnow()) - start).total_seconds())


@router.get("/v1/runs/{run_id}", summary="E22 run detail (class B)")
def run_detail(
    request: Request,
    run_id: str = Path(pattern=RUN_ID),
    include: str | None = Query(default=None),
    p: Principal = Depends(portal_read),
) -> dict[str, Any]:
    s: Settings = request.app.state.settings
    with tx("read", s) as conn:
        sc = p.scope(conn, s)
        require_engineer_family(sc)
        assert p.user is not None  # noqa: S101
        r = conn.execute(
            text(
                f"SELECT {RUN_COLS} FROM runs r LEFT JOIN users u ON u.id = r.user_id "
                f"WHERE r.id = :id"
            ),
            {"id": run_id},
        ).first()
        if r is None or not sc.can_see_system(r.system_id):
            raise ServiceError("E-API-04", "Run not found")
        info = sc.catalogue[r.system_id]
        item = run_items(conn, sc, p.user.id, [r])[0]
        plan = conn.execute(
            text(
                "SELECT seq, step_id, kind, skill_id FROM workflow_steps WHERE workflow_id = :w "
                "AND "
                ""
                "version = :v "
                "ORDER BY seq"
            ),
            {"w": r.workflow_id or "", "v": r.workflow_version or ""},
        ).all()
        attempts = conn.execute(
            text(
                "SELECT s.*, c.decided_by, c.key_id, c.verification_sha256, c.findings_dropped, "
                "c.ci_verified "
                "FROM steps s LEFT JOIN check_records c USING (run_id, step_id, attempt) WHERE "
                "s.run_id = :id "
                "ORDER BY s.seq NULLS LAST, s.step_id, s.attempt"
            ),
            {"id": run_id},
        ).all()
        labels: dict[str, str] = dict(
            conn.execute(text("SELECT code, label FROM cause_labels")).all()
        )
        questions = conn.execute(
            text("SELECT * FROM questions WHERE run_id = :id ORDER BY question_id"), {"id": run_id}
        ).all()
        approvals = conn.execute(
            text(
                "SELECT a.*, u.pseudonym AS approver FROM approvals a LEFT JOIN users u ON u.id "
                "= "
                "a.approver_user_id "
                "WHERE a.run_id = :id ORDER BY a.gate"
            ),
            {"id": run_id},
        ).all()
        prs = conn.execute(
            text(
                "SELECT pr.number, pr.state, pr.draft, pr.head_sha, sr.name AS repo, "
                "sr.github_full_name, "
                "(SELECT c.result FROM ci_checks c WHERE c.repo_id = pr.repo_id AND c.head_sha = "
                ""
                "pr.head_sha "
                " ORDER BY (c.source = 'event') DESC, c.checked_at DESC LIMIT 1) AS ci_result "
                "FROM pull_requests pr JOIN system_repos sr ON sr.id = pr.repo_id WHERE "
                "pr.run_id = "
                ""
                ":id ORDER BY pr.number"
            ),
            {"id": run_id},
        ).all()
        usage = conn.execute(
            text("SELECT * FROM run_usage WHERE run_id = :id"), {"id": run_id}
        ).first()
        pack = conn.execute(
            text(
                "SELECT s.pack_status, s.pack_signed_at, u.pseudonym FROM systems s LEFT JOIN "
                "users "
                ""
                "u "
                "ON u.id = s.pack_signed_by WHERE s.id = CAST(:s AS uuid)"
            ),
            {"s": r.system_id},
        ).one()
    by_step: dict[str, list[Any]] = {}
    for a in attempts:
        by_step.setdefault(a.step_id, []).append(a)
    appr = {a.gate: a for a in approvals}

    def attempt_json(a: Any) -> dict[str, Any]:
        rec = None
        if a.decided_at is not None:
            rec = {
                "decided_by": a.decided_by,
                "key_id": a.key_id,
                "verification_sha256": a.verification_sha256,
                "signals": a.signals,
                "gate_failures": list(a.gate_failures or []),
                "caps": list(a.caps or []),
                "reasons": [{"code": c, "label": labels.get(c, c)} for c in (a.reasons or [])],
                "findings": {
                    "blocker": a.findings_blocker,
                    "major": a.findings_major,
                    "minor": a.findings_minor,
                },
                "findings_dropped": list(a.findings_dropped or []),
                "ci_verified": a.ci_verified,
            }
        return {
            "attempt": a.attempt,
            "started_at": iso(a.started_at),
            "decided_at": iso(a.decided_at),
            "duration_ms": a.duration_ms,
            "record": rec,
        }

    steps_out: list[dict[str, Any]] = []
    planned = set()
    for st in plan:
        planned.add(st.step_id)
        atts = by_step.get(st.step_id, [])
        last = atts[-1] if atts else None
        outcome = last.outcome if last else None
        if st.kind == "gate" and st.step_id in appr:
            outcome = appr[st.step_id].decision
        steps_out.append(
            {
                "seq": st.seq,
                "step_id": st.step_id,
                "kind": st.kind,
                "skill_id": st.skill_id,
                "skill_version": last.skill_version if last else None,
                "outcome": outcome,
                "band": last.band if last else None,
                "attempt_count": len(atts),
                "attempts": [attempt_json(a) for a in atts],
            }
        )
    for sid, atts in by_step.items():
        if sid not in planned:
            last = atts[-1]
            steps_out.append(
                {
                    "seq": last.seq,
                    "step_id": sid,
                    "kind": "skill",
                    "skill_id": last.skill_id,
                    "skill_version": last.skill_version,
                    "outcome": last.outcome,
                    "band": last.band,
                    "attempt_count": len(atts),
                    "attempts": [attempt_json(a) for a in atts],
                }
            )
    companion = f"{s.companion_url_base}/{info.companion_repo}"
    q_url = f"{companion}/blob/main/runs/{run_id}/open-questions.md"
    approvals_out = [
        {
            "gate": a.gate,
            "reason_code": a.reason_code,
            "requested_at": iso(a.requested_at),
            "decision": a.decision,
            "approver": {"pseudonym": a.approver, "display_name": None} if a.approver else None,
            "recorded_at": iso(a.recorded_at),
        }
        for a in approvals
    ]
    data = {
        "run": item,
        "pack": {
            "status": pack.pack_status,
            "signed_at": iso(pack.pack_signed_at),
            "signed_by": pack.pseudonym,
        },
        "links": {"companion_runs_url": f"{companion}/tree/main/runs/{run_id}"},
        "steps": steps_out,
        "questions": [
            {
                "question_id": q.question_id,
                "step_id": q.step_id,
                "blocking": q.blocking,
                "ask_role": q.ask_role,
                "evidence_ref": q.evidence_ref,
                "created_at": iso(q.created_at),
                "answered_at": iso(q.answered_at),
                "age_s": _age(q.created_at, q.answered_at),
                "file_url": q_url,
            }
            for q in questions
        ],
        "approvals": approvals_out,
        "pull_requests": [
            {
                "repo": x.repo,
                "number": x.number,
                "state": x.state,
                "draft": x.draft,
                "url": f"https://github.com/{x.github_full_name}/pull/{x.number}",
                "ci_result": x.ci_result,
            }
            for x in prs
        ],
        "usage": None
        if usage is None
        else {
            "tokens_in": int(usage.tokens_in),
            "tokens_out": int(usage.tokens_out),
            "cost_usd": float(usage.cost_usd),
        },
    }
    if include == "names" and sc.can_see_names(r.system_id):
        eligible = [(item["engineer"], r.user_id, info.code)]
        apply_names(s, p.user.id, "/v1/runs/{run_id}", [item], eligible)
    return envelope(data, meta={"scope": scope_meta(sc)})
