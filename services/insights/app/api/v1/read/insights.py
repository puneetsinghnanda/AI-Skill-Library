"""Insights: E15 business (class A), E16 home, E17-E20 engineering (class B) (SDD-09 "
"§5.6.10-§5.6.14)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import Connection, text

from app.api.deps import portal_read
from app.auth.principal import Principal
from app.config import Settings
from app.db import tx
from app.errors import ServiceError
from app.read.access import require_any_grant, require_engineer_family, systems_filter
from app.read.common import Period, data_as_of, envelope, months_back, period, ratio, scope_meta
from app.timeutil import iso, utcnow

router = APIRouter(tags=["read"])
OUTCOMES = [
    ("PASS", "o_pass"),
    ("PASS-WITH-FINDINGS", "o_findings"),
    ("RETRY", "o_retry"),
    ("NEEDS-INPUT", "o_input"),
    ("ESCALATE", "o_escalate"),
    ("ABORT", "o_abort"),
]


def _win(per: Period, col: str = "day", prefix: str = "") -> tuple[str, dict[str, Any]]:
    if per.start is None:
        return "TRUE", {}
    return f"{col} BETWEEN :{prefix}a AND :{prefix}b", {
        f"{prefix}a": per.start,
        f"{prefix}b": per.end,
    }


def _prev(per: Period) -> Period | None:
    if per.prev_start is None or per.prev_end is None:
        return None
    return Period(per.key, per.prev_start, per.prev_end, None, None)


# ----------------------------------------------------------------------------- E15
@router.get("/v1/insights/business", summary="E15 business impact (class A)")
def business(
    request: Request,
    period_: str | None = Query(default=None, alias="period"),
    p: Principal = Depends(portal_read),
) -> dict[str, Any]:
    s: Settings = request.app.state.settings
    per = period(period_, default="90d", allowed=("90d", "12m", "all"))
    with tx("read", s) as conn:
        require_any_grant(p.scope(conn, s))
        w, prm = _win(per)
        merged = conn.execute(
            text(f"SELECT coalesce(sum(merged), 0) FROM mv_pr_daily WHERE {w}"), prm
        ).scalar_one()
        if per.start is None:
            merged += conn.execute(
                text("SELECT coalesce(sum(value), 0) FROM agg_monthly WHERE metric = 'prs_merged'")
            ).scalar_one()
        change = None
        pp = _prev(per)
        if pp is not None:
            w2, prm2 = _win(pp)
            change = int(merged) - int(
                conn.execute(
                    text(f"SELECT coalesce(sum(merged), 0) FROM mv_pr_daily WHERE {w2}"), prm2
                ).scalar_one()
            )
        ftp = conn.execute(
            text(
                f"SELECT sum(first_try_pass) a, sum(first_attempts) b FROM mv_skill_daily WHERE {w}"
            ),
            prm,
        ).one()
        sysq = conn.execute(
            text(
                "SELECT count(DISTINCT m.system_id) AS n, count(DISTINCT s.domain) AS d FROM "
                "mv_run_daily m "
                "JOIN systems s ON s.id = m.system_id WHERE m.runs_started > 0 AND "
                f"{w.replace('day', 'm.day')}"
            ),
            prm,
        ).one()
        eng_sql = f"SELECT count(DISTINCT user_id) FROM user_daily WHERE runs_started > 0 AND {w}"
        if per.start is None:
            eng_sql = (
                "SELECT count(DISTINCT user_id) FROM (SELECT user_id FROM user_daily WHERE "
                "runs_started > 0 "
                "UNION SELECT user_id FROM agg_user_month) x"
            )
        engineers = conn.execute(text(eng_sql), prm).scalar_one()
        wa, pa = _win(per, "last_activity_at::date")
        active_pods = conn.execute(
            text(f"SELECT count(*) FROM mv_pod_engagement WHERE {wa}"), pa
        ).scalar_one()
        most = conn.execute(
            text(
                "SELECT e.pod_id, p.title, count(*) AS n FROM mv_pod_engagement e JOIN pods p ON "
                ""
                "p.id = e.pod_id "
                "WHERE p.status IN ('production','pilot') AND "
                f"{wa.replace('last_activity_at', 'e.last_activity_at')} "
                f"GROUP BY 1, 2 ORDER BY 3 DESC, 1 LIMIT 5"
            ),
            pa,
        ).all()
        by_month = {
            r.m: int(r.n)
            for r in conn.execute(
                text(
                    "SELECT to_char(day, 'YYYY-MM') AS m, sum(merged) AS n FROM mv_pr_daily "
                    "GROUP "
                    "BY 1"
                )
            ).all()
        }
        for r in conn.execute(
            text(
                "SELECT to_char(month, 'YYYY-MM') AS m, sum(value) AS n FROM agg_monthly "
                "WHERE metric = 'prs_merged' GROUP BY 1"
            )
        ).all():
            by_month[r.m] = by_month.get(r.m, 0) + int(r.n)
        as_of = data_as_of(
            conn, ["mv_pr_daily", "mv_skill_daily", "mv_run_daily", "mv_pod_engagement"]
        )
    if per.key == "all":
        months = sorted(m for m, v in by_month.items() if v)[-36:]
    else:
        months = months_back(6 if per.key == "90d" else 12)
    data = {
        "prs_delivered": {"value": int(merged), "change": change},
        "first_try_pass": {"value": ratio(ftp.a, ftp.b)},
        "systems_served": {"value": int(sysq.n), "domains": int(sysq.d)},
        "engineers_using": {"value": int(engineers)},
        "active_pods": {"value": int(active_pods)},
        "prs_by_month": [{"month": m, "merged": by_month.get(m, 0)} for m in months],
        "most_used_pods": [
            {"pod_id": r.pod_id, "title": r.title, "engagements": int(r.n)} for r in most
        ],
    }
    return envelope(
        data, meta={"data_as_of": as_of, "period": per.meta(), "scope": {"level": "org"}}
    )


# ----------------------------------------------------------------------------- E16
@router.get("/v1/me/home", summary="E16 Home: Engineer (own data)")
def home(
    request: Request,
    tz: str = Query(default="UTC", max_length=64),
    p: Principal = Depends(portal_read),
) -> dict[str, Any]:
    s: Settings = request.app.state.settings
    try:
        zone = ZoneInfo(tz)
    except (ZoneInfoNotFoundError, ValueError):
        raise ServiceError("E-API-01", "tz is not an IANA time zone") from None
    local = utcnow().astimezone(zone)
    month_start = datetime(local.year, local.month, 1, tzinfo=zone)
    with tx("read", s) as conn:
        sc = p.scope(conn, s)
        require_engineer_family(sc)
        assert p.user is not None  # noqa: S101
        me = p.user.id
        active = conn.execute(
            text(
                "SELECT count(*) FROM runs WHERE user_id = CAST(:u AS uuid) "
                "AND status IS NOT NULL AND status <> 'COMPLETED'"
            ),
            {"u": me},
        ).scalar_one()
        qs = conn.execute(
            text(
                "SELECT w.run_id, w.item, w.since, w.needs_role, w.system_id::text AS system_id, "
                ""
                "r.ticket_ref, q.blocking "
                "FROM v_run_waiting w JOIN runs r ON r.id = w.run_id JOIN questions q ON "
                "q.run_id = "
                "w.run_id "
                "AND q.question_id = w.item WHERE w.kind = 'question' AND w.user_id = CAST(:u AS "
                ""
                "uuid) "
                "ORDER BY w.since NULLS LAST"
            ),
            {"u": me},
        ).all()
        aps = conn.execute(
            text(
                "SELECT w.run_id, w.item, w.since, w.system_id::text AS system_id, r.ticket_ref, "
                ""
                "a.reason_code "
                "FROM v_run_waiting w JOIN runs r ON r.id = w.run_id JOIN approvals a ON "
                "a.run_id = "
                "w.run_id "
                "AND a.gate = w.item WHERE w.kind = 'approval' AND w.system_id = ANY(CAST(:ts AS "
                ""
                "uuid[])) "
                "AND w.user_id IS DISTINCT FROM CAST(:u AS uuid) ORDER BY w.since NULLS LAST"
            ),
            {"u": me, "ts": sorted(sc.tech_lead_systems)},
        ).all()
        last30 = conn.execute(
            text(
                "SELECT count(*) FILTER (WHERE outcome IN ('PASS','PASS-WITH-FINDINGS')) AS ok, "
                "count(*) AS n FROM ("
                " SELECT s.outcome FROM steps s JOIN runs r ON r.id = s.run_id WHERE r.user_id = "
                ""
                "CAST(:u AS uuid) "
                " AND s.attempt = 1 AND s.decided_at IS NOT NULL ORDER BY s.decided_at DESC "
                "LIMIT "
                "30) x"
            ),
            {"u": me},
        ).one()
        prs = conn.execute(
            text(
                "SELECT count(*) FROM pull_requests pr JOIN runs r ON r.id = pr.run_id WHERE "
                "r.user_id = CAST(:u AS uuid) "
                "AND pr.merged_at >= :m"
            ),
            {"u": me, "m": month_start},
        ).scalar_one()
        systems = conn.execute(
            text(
                "SELECT code, pack_status, pack_signed_at, pack_drift_files FROM systems WHERE "
                "id = "
                "ANY(CAST(:s AS uuid[])) "
                "ORDER BY code"
            ),
            {"s": sorted(sc.engineer_systems)},
        ).all()
    waiting: list[dict[str, Any]] = []
    for q in qs:
        info = sc.catalogue.get(q.system_id)
        url = (
            f"{s.companion_url_base}/{info.companion_repo}/blob/main/runs/{q.run_id}/open-questions.md"
            if info
            else None
        )
        waiting.append(
            {
                "kind": "question",
                "run_id": q.run_id,
                "ticket_ref": q.ticket_ref,
                "item": q.item,
                "blocking": q.blocking,
                "ask_role": q.needs_role,
                "since": iso(q.since),
                "file_url": url,
            }
        )
    for a in aps:
        waiting.append(
            {
                "kind": "approval",
                "run_id": a.run_id,
                "ticket_ref": a.ticket_ref,
                "item": a.item,
                "reason_code": a.reason_code,
                "since": iso(a.since),
            }
        )
    now = utcnow()
    data = {
        "tiles": {
            "active_runs": int(active),
            "waiting_on_me": {"total": len(waiting), "questions": len(qs), "approvals": len(aps)},
            "my_first_try_pass": {"value": ratio(last30.ok, last30.n), "n": int(last30.n)},
            "my_prs_this_month": int(prs),
        },
        "waiting": waiting,
        "systems": [
            {
                "system": x.code,
                "pack_status": x.pack_status,
                "pack_signed_at": iso(x.pack_signed_at),
                "days_since_signed": (now - x.pack_signed_at).days if x.pack_signed_at else None,
                "drift_files": x.pack_drift_files,
            }
            for x in systems
        ],
        "agent_role": p.user.agent_role,
    }
    return envelope(data, meta={"scope": scope_meta(sc)})


# ----------------------------------------------------------------------------- E17-E20
def _eng(
    request: Request,
    p: Principal,
    project: str | None,
    system: str | None,
    period_: str | None,
    conn: Connection,
) -> tuple[Any, list[str], Period]:
    s: Settings = request.app.state.settings
    sc = p.scope(conn, s)
    require_engineer_family(sc)
    per = period(period_, default="30d", allowed=("30d", "90d"))
    return sc, systems_filter(sc, project, system), per


@router.get("/v1/insights/engineering/runs", summary="E17 engineering: runs (class B)")
def eng_runs(
    request: Request,
    project: str | None = Query(default=None),
    system: str | None = Query(default=None),
    period_: str | None = Query(default=None, alias="period"),
    p: Principal = Depends(portal_read),
) -> dict[str, Any]:
    s: Settings = request.app.state.settings
    with tx("read", s) as conn:
        sc, sys_ids, per = _eng(request, p, project, system, period_, conn)
        prm: dict[str, Any] = {"s": sys_ids, "a": per.start, "b": per.end}
        cur: dict[str, int] = dict(
            conn.execute(
                text(
                    "SELECT status, count(*) FROM runs WHERE system_id = ANY(CAST(:s AS uuid[])) "
                    ""
                    "AND status <> 'COMPLETED' "
                    "GROUP BY 1"
                ),
                prm,
            ).all()
        )
        done = conn.execute(
            text(
                "SELECT count(*) FILTER (WHERE coalesce(end_reason, '') <> 'aborted') AS "
                "completed, "
                ""
                "count(*) FILTER (WHERE end_reason = 'aborted') AS aborted FROM runs "
                "WHERE system_id = ANY(CAST(:s AS uuid[])) AND status = 'COMPLETED' AND "
                "completed_at::date BETWEEN :a AND :b"
            ),
            prm,
        ).one()
        oldest = conn.execute(
            text(
                "SELECT min(since) FROM v_run_waiting WHERE kind = 'question' AND system_id = "
                "ANY(CAST(:s AS uuid[]))"
            ),
            prm,
        ).scalar()
        aborted = conn.execute(
            text(
                "SELECT coalesce(end_code, 'unknown') AS code, count(*) AS n FROM runs WHERE "
                "system_id = ANY(CAST(:s AS uuid[])) "
                "AND end_reason = 'aborted' AND completed_at::date BETWEEN :a AND :b GROUP BY 1 "
                "ORDER BY 2 DESC, 1"
            ),
            prm,
        ).all()
        out = conn.execute(
            text(
                "SELECT coalesce(sum(decisions), 0) AS total, "
                + ", ".join(f"coalesce(sum({c}), 0) AS {c}" for _o, c in OUTCOMES)
                + " FROM mv_skill_daily WHERE system_id = ANY(CAST(:s AS uuid[])) AND day "
                "BETWEEN "
                ":a AND :b"
            ),
            prm,
        ).one()
        as_of = data_as_of(conn, ["mv_skill_daily"])
    total = int(out.total)
    data = {
        "status_counts": {
            "running": int(cur.get("RUNNING", 0)),
            "paused_input": int(cur.get("PAUSED_INPUT", 0)),
            "paused_approval": int(cur.get("PAUSED_APPROVAL", 0)),
            "completed": int(done.completed),
            "aborted": int(done.aborted),
        },
        "oldest_input_wait_s": int((utcnow() - oldest).total_seconds()) if oldest else None,
        "aborted_by_code": [{"code": r.code, "n": int(r.n)} for r in aborted],
        "step_outcomes": {
            "total": total,
            **{o: ratio(getattr(out, c), total) for o, c in OUTCOMES},
        },
    }
    return envelope(data, meta={"data_as_of": as_of, "period": per.meta(), "scope": scope_meta(sc)})


@router.get(
    "/v1/insights/engineering/skills", summary="E18 engineering: skill performance (class B)"
)
def eng_skills(
    request: Request,
    project: str | None = Query(default=None),
    system: str | None = Query(default=None),
    period_: str | None = Query(default=None, alias="period"),
    p: Principal = Depends(portal_read),
) -> dict[str, Any]:
    s: Settings = request.app.state.settings
    with tx("read", s) as conn:
        sc = p.scope(conn, s)
        if not (sc.engineer_family or sc.owned_skills):
            raise ServiceError("E-API-03")
        per = period(period_, default="30d", allowed=("30d", "90d"))
        sys_ids = systems_filter(sc, project, system) if sc.engineer_family else []
        prm: dict[str, Any] = {
            "s": sys_ids,
            "a": per.start,
            "b": per.end,
            "own": sorted(sc.owned_skills),
        }
        base = (
            "(system_id = ANY(CAST(:s AS uuid[])) OR skill_id = ANY(:own)) AND day BETWEEN :a "
            "AND "
            ":b"
        )
        rows = conn.execute(
            text(
                "SELECT skill_id, skill_version, sum(step_instances) AS inst, "
                "sum(first_try_pass) "
                "AS ftp, "
                "sum(first_attempts) AS fa, sum(b_high) AS h, sum(b_medium) AS m, sum(b_low) AS "
                "l, sum(o_retry) AS r "
                f"FROM mv_skill_daily WHERE {base} GROUP BY 1, 2 ORDER BY 1, "
                "string_to_array(skill_version, '.')::int[] DESC"
            ),
            prm,
        ).all()
        ov = {
            (r.skill_id, r.skill_version): int(r.n)
            for r in conn.execute(
                text(
                    "SELECT skill_id, skill_version, sum(overrides) AS n FROM mv_override_daily "
                    f"WHERE {base} GROUP BY 1, 2"
                ),
                prm,
            ).all()
        }
        causes = {}
        for r in conn.execute(
            text(
                "SELECT DISTINCT ON (skill_id, skill_version) skill_id, skill_version, m.code, "
                "c.label FROM ("
                " SELECT skill_id, skill_version, code, sum(n) AS n FROM mv_cause_daily WHERE "
                f"{base} GROUP BY 1, 2, 3) m "
                "LEFT JOIN cause_labels c ON c.code = m.code ORDER BY skill_id, skill_version, "
                "m.n DESC, m.code"
            ),
            prm,
        ).all():
            causes[(r.skill_id, r.skill_version)] = {"code": r.code, "label": r.label or r.code}
        flags = {
            (r.skill_id, r.skill_version): int(r.n)
            for r in conn.execute(
                text(
                    "SELECT skill_id, skill_version, count(*) AS n FROM skill_flags "
                    "WHERE status IN ('OPEN','IN_PROGRESS','REOPENED') GROUP BY 1, 2"
                )
            ).all()
        }
        as_of = data_as_of(conn, ["mv_skill_daily", "mv_override_daily", "mv_cause_daily"])
    items = []
    for r in rows:
        key = (r.skill_id, r.skill_version)
        own = r.skill_id in sc.owned_skills
        bands = (r.h or 0) + (r.m or 0) + (r.l or 0)
        f = ratio(r.ftp, r.fa)
        items.append(
            {
                "skill_id": r.skill_id,
                "version": r.skill_version,
                "scope_level": "org" if own else "systems",
                "runs": int(r.inst or 0),
                "first_try_pass": f,
                "below_target": None if f is None else f < s.first_try_target,
                "band_mix": {
                    "high": ratio(r.h, bands),
                    "medium": ratio(r.m, bands),
                    "low": ratio(r.l, bands),
                },
                "retries_per_step": ratio(r.r, r.inst),
                "override_rate": ratio(ov.get(key, 0), r.inst),
                "top_cause": causes.get(key),
                "open_flags": flags.get(key, 0),
                "high_band_precision": None,
            }
        )
    return envelope(
        {"items": items},
        meta={"data_as_of": as_of, "period": per.meta(), "scope": scope_meta(sc)},
        page={"limit": len(items), "next_cursor": None},
    )


@router.get("/v1/insights/engineering/usage", summary="E19 engineering: usage (class B)")
def eng_usage(
    request: Request,
    project: str | None = Query(default=None),
    system: str | None = Query(default=None),
    period_: str | None = Query(default=None, alias="period"),
    p: Principal = Depends(portal_read),
) -> dict[str, Any]:
    s: Settings = request.app.state.settings
    with tx("read", s) as conn:
        sc, sys_ids, per = _eng(request, p, project, system, period_, conn)
        prm: dict[str, Any] = {"s": sys_ids, "a": per.start, "b": per.end}
        inscope = "system_id = ANY(CAST(:s AS uuid[])) AND day BETWEEN :a AND :b"
        active = conn.execute(
            text(
                "SELECT count(DISTINCT user_id) FROM user_daily WHERE runs_started > 0 AND "
                f"{inscope}"
            ),
            prm,
        ).scalar_one()
        started = conn.execute(
            text(f"SELECT coalesce(sum(runs_started), 0) FROM mv_run_daily WHERE {inscope}"), prm
        ).scalar_one()
        pr = conn.execute(
            text(
                f"SELECT coalesce(sum(merged), 0) AS m, coalesce(sum(closed_unmerged), 0) AS c, "
                "coalesce(sum(opened), 0) AS o, coalesce(sum(opened_with_changes_requested), 0) "
                "AS cr "
                f"FROM mv_pr_daily WHERE {inscope}"
            ),
            prm,
        ).one()
        unlinked = conn.execute(
            text(
                "SELECT coalesce(sum(opened), 0) FROM pr_unlinked_daily WHERE day BETWEEN :a AND "
                ":b "
                "AND github_full_name IN "
                "(SELECT DISTINCT github_full_name FROM system_repos WHERE system_id = "
                "ANY(CAST(:s "
                "AS uuid[])))"
            ),
            prm,
        ).scalar_one()
        by_wf = conn.execute(
            text(
                f"SELECT workflow_id, sum(runs_started) AS n FROM mv_run_daily WHERE {inscope} "
                f"GROUP BY 1 ORDER BY 2 DESC, 1"
            ),
            prm,
        ).all()
        weekly = conn.execute(
            text(
                "SELECT to_char(day, 'IYYY-\"W\"IW') AS wk, count(DISTINCT user_id) FILTER "
                "(WHERE "
                "runs_started > 0) AS eng, "
                f"sum(runs_started) AS runs FROM user_daily WHERE {inscope} GROUP BY 1 ORDER BY "
                "1"
            ),
            prm,
        ).all()
        cost = conn.execute(
            text(
                "SELECT r.workflow_id, avg(u.tokens_in + u.tokens_out) AS avg_t, avg(u.cost_usd) "
                "AS "
                "avg_c FROM run_usage u "
                "JOIN runs r ON r.id = u.run_id WHERE r.system_id = ANY(CAST(:s AS uuid[])) "
                "AND r.started_at::date BETWEEN :a AND :b GROUP BY 1 ORDER BY 1"
            ),
            prm,
        ).all()
        as_of = data_as_of(conn, ["mv_run_daily", "mv_pr_daily"])
    data = {
        "active_engineers": int(active),
        "runs_started": int(started),
        "pr_merge_rate": ratio(pr.m, int(pr.m) + int(pr.c)),
        "prs_without_run": int(unlinked),
        "changes_requested_share": ratio(pr.cr, pr.o),
        "runs_by_workflow": [{"workflow_id": r.workflow_id, "runs": int(r.n)} for r in by_wf],
        "weekly": [
            {"week": r.wk, "active_engineers": int(r.eng), "runs_started": int(r.runs or 0)}
            for r in weekly
        ],
        "cost_by_workflow": [
            {
                "workflow_id": r.workflow_id,
                "avg_tokens": int(r.avg_t or 0),
                "avg_cost_usd": round(float(r.avg_c or 0), 4),
            }
            for r in cost
        ],
    }
    return envelope(data, meta={"data_as_of": as_of, "period": per.meta(), "scope": scope_meta(sc)})


@router.get("/v1/insights/engineering/health", summary="E20 engineering: health (class B)")
def eng_health(
    request: Request,
    project: str | None = Query(default=None),
    system: str | None = Query(default=None),
    period_: str | None = Query(default=None, alias="period"),
    p: Principal = Depends(portal_read),
) -> dict[str, Any]:
    s: Settings = request.app.state.settings
    with tx("read", s) as conn:
        sc, sys_ids, per = _eng(request, p, project, system, period_, conn)
        prm: dict[str, Any] = {"s": sys_ids, "a": per.start, "b": per.end}
        packs = conn.execute(
            text(
                "SELECT code, pack_status, pack_signed_at, pack_drift_files FROM systems "
                "WHERE id = ANY(CAST(:s AS uuid[])) ORDER BY code"
            ),
            prm,
        ).all()
        ci = conn.execute(
            text(
                "SELECT coalesce(sum(verified), 0) v, coalesce(sum(e_ci_01), 0) a, "
                "coalesce(sum(e_ci_02), 0) b, "
                "coalesce(sum(e_ci_03), 0) c FROM mv_ci_daily WHERE system_id = ANY(CAST(:s AS "
                "uuid[])) "
                "AND day BETWEEN :a AND :b"
            ),
            prm,
        ).one()
        telemetry = None
        if sc.telemetry:
            today = conn.execute(
                text("SELECT coalesce(sum(n), 0) FROM ingest_daily WHERE day = CAST(now() AS date)")
            ).scalar_one()
            queued = conn.execute(
                text(
                    "SELECT count(*) FROM devices WHERE last_seen_at > now() - interval '14 "
                    "days' "
                    "AND outbox_depth > 0"
                )
            ).scalar_one()
            latest = conn.execute(
                text(
                    "SELECT plugin_version FROM catalogue_releases ORDER BY released_at DESC "
                    "LIMIT "
                    "1"
                )
            ).scalar()
            spread = conn.execute(
                text(
                    "WITH act AS (SELECT DISTINCT user_id FROM user_daily WHERE runs_started > 0 "
                    ""
                    "AND day BETWEEN :a AND :b), "
                    "dev AS (SELECT DISTINCT ON (user_id) user_id, plugin_version FROM devices "
                    "ORDER BY user_id, last_seen_at DESC) "
                    "SELECT count(*) AS active, count(*) FILTER (WHERE dev.plugin_version = :lv) "
                    "AS "
                    "on_latest "
                    "FROM act LEFT JOIN dev USING (user_id)"
                ),
                {**prm, "lv": latest},
            ).one()
            blocks = conn.execute(
                text(
                    "SELECT coalesce(sum(n), 0) FROM hook_daily WHERE decision = 'deny' AND day "
                    "BETWEEN :a AND :b "
                    "AND (system_id = ANY(CAST(:s AS uuid[])) OR system_id = "
                    "'00000000-0000-0000-0000-000000000000')"
                ),
                prm,
            ).scalar_one()
            telemetry = {
                "events_today": int(today),
                "devices_with_queue": int(queued),
                "plugin_spread": {
                    "latest": latest,
                    "on_latest": int(spread.on_latest),
                    "active": int(spread.active),
                },
                "policy_blocks": int(blocks),
            }
        as_of = data_as_of(conn, ["mv_ci_daily"])
    now = utcnow()
    data = {
        "packs": [
            {
                "system": x.code,
                "status": x.pack_status,
                "days_since_signed": (now - x.pack_signed_at).days if x.pack_signed_at else None,
                "drift_files": x.pack_drift_files,
            }
            for x in packs
        ],
        "fresh_systems": sum(1 for x in packs if x.pack_status == "fresh"),
        "ci": {
            "verified": int(ci.v),
            "e_ci_01": int(ci.a),
            "e_ci_02": int(ci.b),
            "e_ci_03": int(ci.c),
        },
        "telemetry": telemetry,
    }
    return envelope(data, meta={"data_as_of": as_of, "period": per.meta(), "scope": scope_meta(sc)})
