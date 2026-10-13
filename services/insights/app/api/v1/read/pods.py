"""Pods: E08-E13 (SDD-09 §5.6.8, SDD-10 §6). Fields by role (SDD-10 §6.1)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from fastapi import APIRouter, Depends, Path, Query, Request
from sqlalchemy import Connection, text

from app.api.deps import portal_read
from app.api.v1.read.runs import list_runs
from app.auth.principal import Principal
from app.auth.scope import Scope
from app.config import Settings
from app.db import tx
from app.errors import ServiceError
from app.read.access import require_any_grant, require_engineer_family, systems_filter
from app.read.common import decode_cursor, envelope, limit_of, page, period, ratio
from app.read.labels import AGENT_CODE, STATUS_RANK

router = APIRouter(tags=["read"])
POD_ID = r"^[a-z][a-z0-9-]{2,60}$"
MIN_COMPLETED_RUNS = 5  # SDD-10 §6.2


def _visible(sc: Scope, status: str) -> bool:
    return status != "draft" or sc.engineer_family


def _pod_rows(conn: Connection) -> Sequence[Any]:
    return conn.execute(
        text(
            "SELECT p.id, p.title, p.kind, p.status, p.owner_pseudonym, p.current_version, "
            "v.definition "
            "FROM pods p JOIN pod_versions v ON v.pod_id = p.id AND v.version = p.current_version"
        )
    ).all()


def _agents(conn: Connection, pod_id: str, version: str) -> Sequence[Any]:
    return conn.execute(
        text(
            "SELECT a.agent_key, a.role, a.display_name, a.engineers, "
            "coalesce(array_agg(s.skill_id ORDER BY s.skill_id) FILTER (WHERE s.skill_id IS NOT "
            "NULL), '{}') AS skills "
            "FROM pod_agents a LEFT JOIN pod_agent_skills s USING (pod_id, version, agent_key) "
            "WHERE a.pod_id = :p AND a.version = :v GROUP BY 1, 2, 3, 4 ORDER BY a.agent_key"
        ),
        {"p": pod_id, "v": version},
    ).all()


def _workflows(conn: Connection, pod_id: str, version: str) -> list[str]:
    return list(
        conn.execute(
            text(
                "SELECT workflow_id FROM pod_workflows WHERE pod_id = :p AND version = :v "
                "ORDER BY workflow_id"
            ),
            {"p": pod_id, "v": version},
        ).scalars()
    )


def pod_metrics(conn: Connection, pod_id: str, period_key: str) -> dict[str, Any]:
    per = period(period_key, default="90d", allowed=("90d", "12m", "all"))
    cond: str = "TRUE"
    params: dict[str, Any] = {"p": pod_id}
    if per.start is not None:
        cond, params = "day BETWEEN :a AND :b", {"p": pod_id, "a": per.start, "b": per.end}
    completed = conn.execute(
        text(
            "SELECT count(*) FROM runs WHERE pod_id = :p AND end_reason IN "
            "('pr_opened','completed')"
            + ("" if per.start is None else " AND completed_at::date BETWEEN :a AND :b")
        ),
        params,
    ).scalar_one()
    if completed < MIN_COMPLETED_RUNS:
        return {"status": "no_data"}
    q = conn.execute(
        text(
            f"SELECT sum(first_try_pass) AS a, sum(first_attempts) AS b FROM mv_skill_daily "
            f"WHERE pod_id = :p AND {cond}"
        ),
        params,
    ).one()
    systems = conn.execute(
        text(
            "SELECT count(DISTINCT system_id) FROM runs WHERE pod_id = :p"
            + ("" if per.start is None else " AND started_at::date BETWEEN :a AND :b")
        ),
        params,
    ).scalar_one()
    merged = conn.execute(
        text(f"SELECT coalesce(sum(merged), 0) FROM mv_pr_daily WHERE pod_id = :p AND {cond}"),
        params,
    ).scalar_one()
    return {
        "status": "ok",
        "period": per.key,
        "first_try_pass": ratio(q.a, q.b),
        "systems_served": int(systems),
        "prs_merged": int(merged),
        "completed_runs": int(completed),
    }


def _card(conn: Connection, sc: Scope, r: Any, engagements: int) -> dict[str, Any]:
    d = r.definition or {}
    agents = _agents(conn, r.id, r.current_version)
    card: dict[str, Any] = {
        "id": r.id,
        "version": r.current_version,
        "status": r.status,
        "kind": r.kind,
        "title": r.title,
        "summary": d.get("summary"),
        "agents": [a.display_name for a in agents],
        "code": [AGENT_CODE.get(a.role, a.agent_key[:2].upper()) for a in agents],
        "people": [x.get("title") for x in d.get("people", []) if isinstance(x, dict)],
        "engagements": engagements,
    }
    if sc.viewer_only:
        fit = (d.get("best_fit") or {}).get("good_fit_when") or []
        card["best_for"] = d.get("best_for") or (fit[0] if fit else None)
        card["metrics"] = pod_metrics(conn, r.id, "all")
    else:
        card["workflows"] = _workflows(conn, r.id, r.current_version)
        card["skill_count"] = len({sk for a in agents for sk in a.skills})
    return card


@router.get("/v1/catalogue/pods", summary="E08 pod cards (class A; fields by role)")
def catalogue_pods(
    request: Request,
    status: str | None = Query(default=None),
    kind: str | None = Query(default=None, pattern="^(brownfield|greenfield|quality|ux)$"),
    sort: str = Query(default="status", pattern="^(status|featured)$"),
    limit: int | None = Query(default=None),
    cursor: str | None = Query(default=None),
    p: Principal = Depends(portal_read),
) -> dict[str, Any]:
    s: Settings = request.app.state.settings
    n = limit_of(limit)
    filters = {"status": status, "kind": kind, "sort": sort}
    after = decode_cursor(cursor, filters)
    wanted = {x for x in (status or "").split(",") if x} or {"draft", "pilot", "production"}
    with tx("read", s) as conn:
        sc = p.scope(conn, s)
        require_any_grant(sc)
        eng = {
            r.pod_id: int(r.n)
            for r in conn.execute(
                text("SELECT pod_id, count(*) AS n FROM mv_pod_engagement GROUP BY 1")
            ).all()
        }
        rows = [
            r
            for r in _pod_rows(conn)
            if r.status in wanted and _visible(sc, r.status) and (not kind or r.kind == kind)
        ]

        def key(r: Any) -> list[Any]:
            if sort == "featured":
                return [STATUS_RANK[r.status], -eng.get(r.id, 0), r.id]
            return [STATUS_RANK[r.status], r.title, r.id]

        rows.sort(key=key)
        if after is not None:
            rows = [r for r in rows if key(r) > after]
        rows = rows[: n + 1]
        keys = {r.id: key(r) for r in rows}
        items = [_card(conn, sc, r, eng.get(r.id, 0)) for r in rows]
    items, pg = page(items, n, lambda it: keys[it["id"]], filters)
    return envelope({"items": items}, meta={"scope": {"level": "org"}}, page=pg)


def _pod(conn: Connection, sc: Scope, pod_id: str, version: str | None = None) -> Any:
    row = conn.execute(
        text(
            "SELECT p.id, p.title, p.kind, p.status AS pod_status, p.owner_pseudonym, v.version, "
            "v.status, v.definition "
            "FROM pods p JOIN pod_versions v ON v.pod_id = p.id AND v.version = coalesce(:v, "
            "p.current_version) "
            "WHERE p.id = :p"
        ),
        {"p": pod_id, "v": version},
    ).first()
    if row is None or not _visible(sc, row.status):
        raise ServiceError("E-API-04", "Pod not found")
    return row


@router.get("/v1/pods/{pod_id}", summary="E09 pod detail (class A; fields by role)")
def pod_detail(
    request: Request,
    pod_id: str = Path(pattern=POD_ID),
    version: str | None = Query(default=None, max_length=20),
    p: Principal = Depends(portal_read),
) -> dict[str, Any]:
    s: Settings = request.app.state.settings
    with tx("read", s) as conn:
        sc = p.scope(conn, s)
        require_any_grant(sc)
        r = _pod(conn, sc, pod_id, version)
        d = r.definition or {}
        agents = _agents(conn, r.id, r.version)
        workflows = _workflows(conn, r.id, r.version)
        flow_rows: list[Any] = []
        if workflows:
            flow_rows = list(
                conn.execute(
                    text(
                        "SELECT ws.seq, ws.kind, ws.step_id, ws.skill_id, ws.gate_role, k.title, "
                        "k.agent_role "
                        "FROM workflow_steps ws JOIN workflows w ON w.id = ws.workflow_id AND "
                        "w.current_version = ws.version "
                        "LEFT JOIN skills k ON k.id = ws.skill_id WHERE ws.workflow_id = :w "
                        "ORDER BY ws.seq"
                    ),
                    {"w": workflows[0]},
                ).all()
            )
    jobs = {a.get("key"): a.get("job") for a in d.get("agents", []) if isinstance(a, dict)}
    by_skill = {sk: a.display_name for a in agents for sk in a.skills}
    show_ids = not sc.viewer_only
    flow = []
    for st in flow_rows:
        if st.kind == "skill":
            label = st.title or st.skill_id
            who = (
                by_skill.get(st.skill_id)
                or f"{(st.agent_role or 'skill').replace('-', ' ').title()} skill"
            )
        elif st.kind == "gate":
            label, who = (
                f"Approval {st.step_id}",
                (st.gate_role or "tech_lead").replace("_", " ").capitalize(),
            )
        else:
            label, who = "Pull request", "Engineer"
        item = {"seq": st.seq, "kind": st.kind, "label": label, "who": who}
        if show_ids:
            item["step_id"] = st.step_id
        flow.append(item)
    fit = d.get("best_fit") or {}
    data: dict[str, Any] = {
        "id": r.id,
        "version": r.version,
        "status": r.status,
        "kind": r.kind,
        "title": r.title,
        "summary": d.get("summary"),
        "agents": [
            {
                "key": a.agent_key,
                "code": AGENT_CODE.get(a.role, a.agent_key[:2].upper()),
                "role": a.role,
                "display_name": a.display_name,
                "engineers": a.engineers,
                "job": jobs.get(a.agent_key),
                **({"skills": list(a.skills)} if show_ids else {}),
            }
            for a in agents
        ],
        "people_accountable": [
            {"role": x.get("title"), "decides": x.get("duties", [])}
            for x in d.get("people", [])
            if isinstance(x, dict)
        ],
        "flow": flow,
        "client_gets": d.get("client_gets", []),
        "good_fit": fit.get("good_fit_when", []),
        "not_a_fit": fit.get("not_a_fit_when", []),
        "deprecated_by": d.get("deprecated_by"),
        "internal_only": r.status != "production",
    }
    if show_ids:
        data["workflows"] = workflows
    return envelope(data, meta={"scope": {"level": "org"}})


@router.get("/v1/pods/{pod_id}/metrics", summary="E10 pod track record (class A)")
def metrics(
    request: Request,
    pod_id: str = Path(pattern=POD_ID),
    period_: str | None = Query(default=None, alias="period"),
    p: Principal = Depends(portal_read),
) -> dict[str, Any]:
    s: Settings = request.app.state.settings
    with tx("read", s) as conn:
        sc = p.scope(conn, s)
        require_any_grant(sc)
        _pod(conn, sc, pod_id)
        m = pod_metrics(conn, pod_id, period_ or "90d")
    return envelope(m, meta={"scope": {"level": "org"}})


@router.get("/v1/pods/{pod_id}/runs", summary="E11 active runs of a pod, scoped (class B)")
def pod_runs(
    request: Request,
    pod_id: str = Path(pattern=POD_ID),
    status: str | None = Query(default=None),
    include: str | None = Query(default=None),
    limit: int | None = Query(default=None),
    cursor: str | None = Query(default=None),
    p: Principal = Depends(portal_read),
) -> dict[str, Any]:
    s: Settings = request.app.state.settings
    with tx("read", s) as conn:
        sc = p.scope(conn, s)
        require_engineer_family(sc)
        _pod(conn, sc, pod_id)
    return list_runs(
        request,
        p,
        project=None,
        system=None,
        status=status,
        workflow=None,
        pod=pod_id,
        owner=None,
        period_key=None,
        include=include,
        limit=limit,
        cursor=cursor,
        route="/v1/pods/{pod_id}/runs",
    )


@router.get("/v1/pods/{pod_id}/fit", summary="E12 fit check for a system (class B)")
def fit(
    request: Request,
    pod_id: str = Path(pattern=POD_ID),
    system: str = Query(pattern=r"^SYS-[0-9A-Z]{2,8}$"),
    p: Principal = Depends(portal_read),
) -> dict[str, Any]:
    s: Settings = request.app.state.settings
    with tx("read", s) as conn:
        sc = p.scope(conn, s)
        require_engineer_family(sc)
        sid = systems_filter(sc, None, system)[0]
        r = _pod(conn, sc, pod_id)
        sysrow = conn.execute(
            text(
                "SELECT pack_status, pack_signed_at, (SELECT count(*) FROM system_repos WHERE "
                "system_id = s.id "
                "AND kind = 'product') AS repos FROM systems s WHERE s.id = CAST(:s AS uuid)"
            ),
            {"s": sid},
        ).one()
    req = ((r.definition or {}).get("best_fit") or {}).get("requires") or {}
    checks = []
    for keyname, want in req.items():
        status_ = "confirm_locally"
        detail = "Not checkable from the server; confirm with tsl doctor"
        if keyname == "product_repo_host":
            status_ = "met" if sysrow.repos > 0 else "not_met"
            detail = f"{sysrow.repos} product repo(s) registered on GitHub"
        elif keyname == "context_pack":
            if want == "none":
                status_, detail = "met", "No context pack needed"
            elif want == "signed":
                status_ = "met" if sysrow.pack_signed_at else "not_met"
                detail = f"Pack status {sysrow.pack_status}"
            else:
                status_ = "met" if sysrow.pack_status == "fresh" else "not_met"
                detail = f"Pack status {sysrow.pack_status}"
        elif keyname in ("docker", "figma_mcp") and want is False:
            status_, detail = "met", "Not required"
        checks.append({"key": keyname, "required": want, "status": status_, "detail": detail})
    return envelope(
        {"pod_id": pod_id, "system": system, "checks": checks}, meta={"scope": {"level": "systems"}}
    )


@router.get(
    "/v1/pods/{pod_id}/one-pager", summary="E13 pod one-pager text with current metrics (class A)"
)
def one_pager(
    request: Request, pod_id: str = Path(pattern=POD_ID), p: Principal = Depends(portal_read)
) -> dict[str, Any]:
    s: Settings = request.app.state.settings
    with tx("read", s) as conn:
        sc = p.scope(conn, s)
        require_any_grant(sc)
        r = _pod(conn, sc, pod_id)
        m = pod_metrics(conn, pod_id, "all")
    return envelope(
        {
            "pod_id": pod_id,
            "status": r.status,
            "markdown": (r.definition or {}).get("one_pager_md", ""),
            "metrics": m,
            "internal_only": r.status != "production",
        },
        meta={"scope": {"level": "org"}},
    )
