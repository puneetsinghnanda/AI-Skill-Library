"""Catalogue and capability map: E03-E07, E14 (SDD-09 §5.6.3-§5.6.7, §6). Class A except E06."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from fastapi import APIRouter, Depends, Path, Query, Request
from sqlalchemy import Connection, text

from app.api.deps import portal_read
from app.auth.principal import Principal
from app.auth.scope import Scope
from app.config import Settings
from app.db import tx
from app.errors import ServiceError
from app.read.access import require_any_grant, systems_filter
from app.read.common import (
    Period,
    data_as_of,
    decode_cursor,
    envelope,
    limit_of,
    page,
    period,
    ratio,
    scope_meta,
)
from app.read.labels import AGENT_CODE, AGENT_LABEL, AGENT_ROLES, PHASES
from app.timeutil import iso

router = APIRouter(tags=["read"])
SKILL_ID = r"^[a-z][a-z0-9-]{2,39}$"


def _period_sql(p: Period, col: str = "day") -> tuple[str, dict[str, Any]]:
    if p.start is None:
        return "TRUE", {}
    return f"{col} BETWEEN :p_from AND :p_to", {"p_from": p.start, "p_to": p.end}


def skill_rows(conn: Connection) -> Sequence[Any]:
    return conn.execute(
        text(
            "SELECT k.id, k.agent_role, k.title, k.summary, k.phase, k.domains, "
            "k.owner_pseudonym, "
            "k.current_version, v.status, v.outputs, v.inputs, v.context_sections, "
            "v.size_budget_tokens, "
            "v.allowed_tools, v.portal, v.release_tag, v.eval_cases, v.eval_pass_rate, "
            "v.eval_recorded_at "
            "FROM skills k JOIN skill_versions v ON v.skill_id = k.id AND v.version = "
            "k.current_version"
        )
    ).all()


def first_try_by_skill(
    conn: Connection, p: Period, systems: list[str] | None = None
) -> dict[tuple[str, str], tuple[int, int]]:
    where, params = _period_sql(p)
    if systems is not None:
        where += " AND system_id = ANY(CAST(:sys AS uuid[]))"
        params["sys"] = systems
    rows = conn.execute(
        text(
            "SELECT skill_id, skill_version, sum(first_try_pass) AS ftp, sum(first_attempts) AS "
            "fa "
            f"FROM mv_skill_daily WHERE {where} GROUP BY 1, 2"
        ),
        params,
    ).all()
    return {(r.skill_id, r.skill_version): (int(r.ftp or 0), int(r.fa or 0)) for r in rows}


def _outputs(v: Any) -> list[str]:
    return [str(o.get("schema")) for o in (v or []) if isinstance(o, dict) and o.get("schema")]


@router.get("/v1/catalogue/summary", summary="E03 catalogue summary (class A)")
def summary(request: Request, p: Principal = Depends(portal_read)) -> dict[str, Any]:
    s: Settings = request.app.state.settings
    with tx("read", s) as conn:
        require_any_grant(p.scope(conn, s))
        skills = skill_rows(conn)
        pods_ready = conn.execute(
            text("SELECT count(*) FROM pods WHERE status IN ('production','pilot')")
        ).scalar_one()
        rel = conn.execute(
            text(
                "SELECT tag, plugin_version, released_at FROM catalogue_releases "
                "ORDER BY released_at DESC, tag LIMIT 1"
            )
        ).first()
    prod = [k for k in skills if k.status == "production"]
    roles = []
    for rid, code, label in AGENT_ROLES:
        roles.append(
            {
                "id": rid,
                "code": code,
                "label": label,
                "skills_production": sum(1 for k in prod if k.agent_role == rid),
                "skills_pilot": sum(
                    1 for k in skills if k.agent_role == rid and k.status == "pilot"
                ),
            }
        )
    return envelope(
        {
            "skills_in_production": len(prod),
            "roles_covered": len({k.agent_role for k in prod}),
            "phases_covered": len({k.phase for k in prod}),
            "pods_ready": int(pods_ready),
            "roles": roles,
            "phases": [{"id": i, "label": label} for i, label in PHASES],
            "domains": sorted({d for k in prod for d in (k.domains or [])}),
            "latest_release": None
            if rel is None
            else {
                "tag": rel.tag,
                "plugin_version": rel.plugin_version,
                "released_at": iso(rel.released_at),
            },
        },
        meta={"scope": {"level": "org"}},
    )


def _allowed_status(sc: Scope, status: str | None) -> set[str]:
    default = {"pilot", "production"} | ({"draft"} if sc.engineer_family else set())
    if not status:
        return default
    wanted = {x.strip() for x in status.split(",") if x.strip()}
    if not wanted <= {"draft", "pilot", "production", "deprecated"}:
        raise ServiceError("E-API-01", "status must be draft, pilot, production or deprecated")
    if not sc.engineer_family:
        wanted.discard("draft")
    return wanted


@router.get("/v1/catalogue/skills", summary="E04 skills list (class A)")
def skills(
    request: Request,
    q: str | None = Query(default=None, max_length=60),
    role: str | None = Query(default=None),
    phase: str | None = Query(default=None),
    domain: str | None = Query(default=None, max_length=40),
    status: str | None = Query(default=None),
    period_: str | None = Query(default=None, alias="period"),
    sort: str = Query(default="role", pattern="^(role|first_try)$"),
    limit: int | None = Query(default=None),
    cursor: str | None = Query(default=None),
    p: Principal = Depends(portal_read),
) -> dict[str, Any]:
    s: Settings = request.app.state.settings
    per = period(period_)
    n = limit_of(limit)
    filters = {
        "q": q,
        "role": role,
        "phase": phase,
        "domain": domain,
        "status": status,
        "period": per.key,
        "sort": sort,
    }
    after = decode_cursor(cursor, filters)
    with tx("read", s) as conn:
        sc = p.scope(conn, s)
        require_any_grant(sc)
        allowed = _allowed_status(sc, status)
        rows = skill_rows(conn)
        ftp = first_try_by_skill(conn, per)
        as_of = data_as_of(conn, ["mv_skill_daily"])
    items = []
    needle = (q or "").lower()
    for k in rows:
        if (
            k.status not in allowed
            or (role and k.agent_role != role)
            or (phase and k.phase != phase)
        ):
            continue
        if domain and domain not in (k.domains or []):
            continue
        outs = _outputs(k.outputs)
        hay = " ".join(
            [k.id, k.title, k.summary, AGENT_LABEL.get(k.agent_role, ""), k.phase, *outs]
        ).lower()
        if needle and needle not in hay:
            continue
        a, b = ftp.get((k.id, k.current_version), (0, 0))
        items.append(
            {
                "id": k.id,
                "title": k.title,
                "summary": k.summary,
                "agent_role": k.agent_role,
                "agent_role_label": AGENT_LABEL.get(k.agent_role, k.agent_role),
                "phase": k.phase,
                "domains": list(k.domains or []),
                "status": k.status,
                "current_version": k.current_version,
                "outputs": outs,
                "first_try_pass": ratio(a, b),
                "first_try_n": b,
            }
        )

    def key(it: dict[str, Any]) -> list[Any]:
        if sort == "first_try":
            f = it["first_try_pass"]
            return [1 if f is None else 0, -(f or 0.0), it["id"]]
        return [it["agent_role"], it["title"], it["id"]]

    items.sort(key=key)
    if after is not None:
        items = [it for it in items if key(it) > after]
    items, pg = page(items[: n + 1], n, key, filters)
    return envelope(
        {"items": items},
        meta={"data_as_of": as_of, "period": per.meta(), "scope": {"level": "org"}},
        page=pg,
    )


def _workflow_positions(conn: Connection, skill_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        text(
            "SELECT ws.workflow_id, ws.version, ws.seq, ws.step_id, ws.kind, ws.skill_id "
            "FROM workflow_steps ws JOIN workflows w ON w.id = ws.workflow_id AND "
            "w.current_version "
            ""
            "= ws.version "
            "WHERE ws.workflow_id IN (SELECT x.workflow_id FROM workflow_steps x JOIN workflows "
            "y "
            "  ON y.id = x.workflow_id AND y.current_version = x.version WHERE x.skill_id = :k) "
            "ORDER BY ws.workflow_id, ws.seq"
        ),
        {"k": skill_id},
    ).all()
    by: dict[str, list[Any]] = {}
    for r in rows:
        by.setdefault(r.workflow_id, []).append(r)
    out = []
    for wid, steps in sorted(by.items()):
        gate = None
        for i, st in enumerate(steps, start=1):
            if st.kind == "gate":
                gate = st.step_id
            if st.skill_id == skill_id:
                out.append(
                    {
                        "workflow_id": wid,
                        "version": st.version,
                        "position": i,
                        "step_count": len(steps),
                        "after_gate": gate,
                    }
                )
                break
    return out


@router.get("/v1/catalogue/skills/{skill_id}", summary="E05 skill detail (class A)")
def skill_detail(
    request: Request, skill_id: str = Path(pattern=SKILL_ID), p: Principal = Depends(portal_read)
) -> dict[str, Any]:
    s: Settings = request.app.state.settings
    per = period("90d")
    with tx("read", s) as conn:
        sc = p.scope(conn, s)
        require_any_grant(sc)
        k = next((r for r in skill_rows(conn) if r.id == skill_id), None)
        if k is None or (k.status == "draft" and not sc.engineer_family):
            raise ServiceError("E-API-04", "Skill not found")
        where, params = _period_sql(per)
        q = conn.execute(
            text(
                "SELECT sum(step_instances) AS runs, sum(first_try_pass) AS ftp, "
                "sum(first_attempts) AS fa, "
                f"sum(b_high) AS h, sum(b_medium) AS m, sum(b_low) AS l FROM mv_skill_daily "
                f"WHERE skill_id = :k AND skill_version = :v AND {where}"
            ),
            {"k": skill_id, "v": k.current_version, **params},
        ).one()
        versions = conn.execute(
            text(
                "SELECT version, status, eval_pass_rate, changelog, published_at FROM "
                "skill_versions "
                "WHERE skill_id = :k ORDER BY string_to_array(version, '.')::int[] DESC"
            ),
            {"k": skill_id},
        ).all()
        pods = conn.execute(
            text(
                "SELECT DISTINCT p.id, p.title, p.status FROM pod_agent_skills a JOIN pods p ON "
                "p.id = a.pod_id "
                "AND p.current_version = a.version WHERE a.skill_id = :k AND p.status <> "
                "'deprecated' ORDER BY p.id"
            ),
            {"k": skill_id},
        ).all()
        workflows = _workflow_positions(conn, skill_id)
        as_of = data_as_of(conn, ["mv_skill_daily"])
    bands = (q.h or 0) + (q.m or 0) + (q.l or 0)
    data = {
        "id": k.id,
        "title": k.title,
        "summary": k.summary,
        "agent_role": k.agent_role,
        "agent_role_label": AGENT_LABEL.get(k.agent_role, k.agent_role),
        "phase": k.phase,
        "domains": list(k.domains or []),
        "status": k.status,
        "owner_pseudonym": k.owner_pseudonym,
        "release_tag": k.release_tag,
        "portal": k.portal or {},
        "current": {
            "version": k.current_version,
            "inputs": k.inputs or [],
            "outputs": k.outputs or [],
            "context_sections": k.context_sections or [],
            "size_budget_tokens": k.size_budget_tokens,
            "allowed_tools": list(k.allowed_tools or []),
        },
        "quality": {
            "period": per.key,
            "runs": int(q.runs or 0),
            "first_try_pass": ratio(q.ftp, q.fa),
            "band_mix": {
                "high": ratio(q.h, bands),
                "medium": ratio(q.m, bands),
                "low": ratio(q.l, bands),
            },
        },
        "eval": {
            "version": k.current_version,
            "pass_rate": float(k.eval_pass_rate) if k.eval_pass_rate is not None else None,
            "cases": k.eval_cases,
            "recorded_at": iso(k.eval_recorded_at),
        },
        "versions": [
            {
                "version": v.version,
                "status": v.status,
                "eval_pass_rate": float(v.eval_pass_rate) if v.eval_pass_rate is not None else None,
                "changelog": v.changelog,
                "published_at": iso(v.published_at),
            }
            for v in versions
            if v.status != "draft" or sc.engineer_family
        ],
        "pods": [
            {"id": x.id, "title": x.title}
            for x in pods
            if x.status != "draft" or sc.engineer_family
        ],
        "workflows": workflows,
    }
    return envelope(
        data, meta={"data_as_of": as_of, "period": per.meta(), "scope": {"level": "org"}}
    )


@router.get(
    "/v1/catalogue/skills/{skill_id}/quality", summary="E06 skill quality, scoped (class B)"
)
def skill_quality(
    request: Request,
    skill_id: str = Path(pattern=SKILL_ID),
    period_: str | None = Query(default=None, alias="period"),
    version: str | None = Query(default=None, max_length=20),
    project: str | None = Query(default=None),
    system: str | None = Query(default=None),
    p: Principal = Depends(portal_read),
) -> dict[str, Any]:
    s: Settings = request.app.state.settings
    per = period(period_)
    with tx("read", s) as conn:
        sc = p.scope(conn, s)
        owned = skill_id in sc.owned_skills
        if not (sc.engineer_family or owned):
            raise ServiceError("E-API-03")
        ver = (
            version
            or conn.execute(
                text("SELECT current_version FROM skills WHERE id = :k"), {"k": skill_id}
            ).scalar()
        )
        if ver is None:
            raise ServiceError("E-API-04", "Skill not found")
        where, params = _period_sql(per)
        params |= {"k": skill_id, "v": ver}
        org = (owned or sc.all_systems) and not (project or system)
        if not org:
            params["sys"] = systems_filter(sc, project, system)
            where += " AND system_id = ANY(CAST(:sys AS uuid[]))"
        fa = conn.execute(
            text(
                f"SELECT coalesce(sum(first_attempts), 0) FROM mv_skill_daily "
                f"WHERE skill_id = :k AND skill_version = :v AND {where}"
            ),
            params,
        ).scalar_one()
        causes = conn.execute(
            text(
                "SELECT m.code, coalesce(c.label, m.code) AS label, sum(m.n) AS n FROM "
                "mv_cause_daily m "
                "LEFT JOIN cause_labels c ON c.code = m.code WHERE m.skill_id = :k AND "
                f"m.skill_version = :v AND {where} "
                f"GROUP BY 1, 2 ORDER BY 3 DESC, 1 LIMIT 5"
            ),
            params,
        ).all()
        as_of = data_as_of(conn, ["mv_skill_daily", "mv_cause_daily"])
    return envelope(
        {
            "skill_id": skill_id,
            "version": ver,
            "scope_level": "org" if org else "systems",
            "first_attempts": int(fa),
            "causes": [{"code": c.code, "label": c.label, "n": int(c.n)} for c in causes],
        },
        meta={"data_as_of": as_of, "period": per.meta(), "scope": scope_meta(None if org else sc)},
    )


@router.get("/v1/catalogue/releases", summary="E07 releases (class A)")
def releases(
    request: Request,
    limit: int | None = Query(default=None),
    cursor: str | None = Query(default=None),
    p: Principal = Depends(portal_read),
) -> dict[str, Any]:
    s: Settings = request.app.state.settings
    n = limit_of(limit)
    after = decode_cursor(cursor, {})
    with tx("read", s) as conn:
        require_any_grant(p.scope(conn, s))
        cond, params = "TRUE", {"n": n + 1}
        if after:
            cond = "(released_at, tag) < (CAST(:a AS timestamptz), :b)"
            params |= {"a": after[0], "b": after[1]}
        rows = conn.execute(
            text(
                "SELECT tag, plugin_version, tsl_version, released_at, notes FROM "
                f"catalogue_releases WHERE {cond} "
                f"ORDER BY released_at DESC, tag DESC LIMIT :n"
            ),
            params,
        ).all()
    items = [
        {
            "tag": r.tag,
            "plugin_version": r.plugin_version,
            "tsl_version": r.tsl_version,
            "released_at": iso(r.released_at),
            "notes": r.notes or [],
        }
        for r in rows
    ]
    items, pg = page(items, n, lambda it: [it["released_at"], it["tag"]], {})
    return envelope({"items": items}, meta={"scope": {"level": "org"}}, page=pg)


@router.get("/v1/capability-map", summary="E14 capability map, internal or shared (class A)")
def capability_map(
    request: Request,
    audience: str = Query(default="internal", pattern="^(internal|shared)$"),
    domain: str | None = Query(default=None, max_length=40),
    p: Principal = Depends(portal_read),
) -> dict[str, Any]:
    s: Settings = request.app.state.settings
    with tx("read", s) as conn:
        require_any_grant(p.scope(conn, s))
        rows = conn.execute(
            text(
                "SELECT m.agent_role, m.phase, m.skill_id, m.title, m.status, k.domains FROM "
                "v_capability_map m "
                "JOIN skills k ON k.id = m.skill_id ORDER BY m.agent_role, m.phase, m.title"
            )
        ).all()
        evidence = {
            r.skill_id: int(r.n)
            for r in conn.execute(
                text("SELECT skill_id, sum(step_instances) AS n FROM mv_skill_daily GROUP BY 1")
            ).all()
        }
        tot = conn.execute(
            text(
                "SELECT coalesce(sum(runs_started), 0) AS runs, count(DISTINCT system_id) AS "
                "systems FROM mv_run_daily"
            )
        ).one()
        ftp = conn.execute(
            text("SELECT sum(first_try_pass) AS a, sum(first_attempts) AS b FROM mv_skill_daily")
        ).one()
        as_of = data_as_of(conn, ["mv_skill_daily", "mv_run_daily"])
    cells: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for r in rows:
        if audience == "shared" and r.status != "production":
            continue
        if domain and domain not in (r.domains or []):
            continue
        cells.setdefault(r.agent_role, {}).setdefault(r.phase, []).append(
            {"skill_id": r.skill_id, "title": r.title, "status": r.status}
        )
    out_rows = []
    cells_with = evidence_cells = 0
    for rid, _code, label in AGENT_ROLES:
        rc = cells.get(rid, {})
        if audience == "shared" and not any(
            x["status"] == "production" for v in rc.values() for x in v
        ):
            continue
        row_cells: dict[str, list[dict[str, Any]]] = {}
        for ph, _l in PHASES:
            lst = rc.get(ph, [])
            prod_n = sum(evidence.get(x["skill_id"], 0) for x in lst if x["status"] == "production")
            backed = prod_n >= 5
            row_cells[ph] = [
                {**x, "evidence_backed": backed and x["status"] == "production"} for x in lst
            ]
            if lst:
                cells_with += 1
                evidence_cells += 1 if backed else 0
        out_rows.append({"role": rid, "code": AGENT_CODE[rid], "label": label, "cells": row_cells})
    data = {
        "audience": audience,
        "phases": [{"id": i, "label": label} for i, label in PHASES],
        "rows": out_rows,
        "totals": {
            "production_skills": sum(
                1
                for r in rows
                if r.status == "production" and (not domain or domain in (r.domains or []))
            ),
            "cells_with_skills": cells_with,
            "evidence_backed_cells": evidence_cells,
            "runs": int(tot.runs),
            "first_try_pass": ratio(ftp.a, ftp.b),
            "systems_served": int(tot.systems),
        },
    }
    return envelope(data, meta={"data_as_of": as_of, "scope": {"level": "org"}})
