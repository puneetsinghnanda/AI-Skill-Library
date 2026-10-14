"""Admin lists (SDD-13 §5.3 access review, §7.2; SDD-09 §4.16).

``GET /v1/admin/...``: ``Portal.Read`` scope and the ``admin`` grant (``403 E-API-03`` otherwise).
Read API conventions (SDD-09 §5.1): the ``data.items`` envelope, ``limit`` 1-100 (default 25) and
an opaque ``cursor`` bound to the filters. Codes and pseudonyms only: client display names are
never returned, and engineers' real names only with ``include=names`` to a caller whose grants hold
a role in ``rd1_name_reveal_roles`` (RD-1), read through the audited reveal path.
Responses are ``Cache-Control: no-store`` so a list is fresh after an admin action.
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, Path, Query, Request, Response
from sqlalchemy import text

from app.api.deps import portal_read
from app.auth.principal import Principal
from app.config import Settings
from app.db import tx
from app.errors import ServiceError
from app.read.common import decode_cursor, envelope, limit_of, page
from app.read.names import record_reveal, reveal
from app.timeutil import iso, utcnow

router = APIRouter(tags=["admin"])
CLIENT = r"^CL-[0-9A-Z]{2,8}$"
PROJECT = r"^PRJ-[0-9A-Z]{2,8}$"
PSEUDONYM = r"^eng-[0-9a-f]{4,8}$"
ROLE = Literal[
    "viewer", "engineer", "tech_lead", "skill_owner", "stage_approver", "eng_lead", "admin"
]


def admin_reader(request: Request, response: Response) -> Principal:
    p = portal_read(request)
    if not p.has("admin"):
        raise ServiceError("E-API-03", "Admin only")
    response.headers["Cache-Control"] = "no-store"
    return p


def _meta() -> dict[str, Any]:
    return {"scope": {"level": "org"}}


def consent_status(recorded_at: Any, withdrawn_at: Any) -> str:
    if withdrawn_at is not None:
        return "withdrawn"
    return "recorded" if recorded_at is not None else "none"


CONSENT_SQL = {
    "recorded": "c.consent_recorded_at IS NOT NULL AND c.consent_withdrawn_at IS NULL",
    "withdrawn": "c.consent_withdrawn_at IS NOT NULL",
    "none": "c.consent_recorded_at IS NULL AND c.consent_withdrawn_at IS NULL",
}


@router.get("/v1/admin/clients", summary="List clients with consent status (SDD-13 §5.3)")
def list_clients(
    request: Request,
    consent: Literal["recorded", "withdrawn", "none"] | None = Query(default=None),
    limit: int | None = Query(default=None),
    cursor: str | None = Query(default=None),
    p: Principal = Depends(admin_reader),
) -> dict[str, Any]:
    s: Settings = request.app.state.settings
    n = limit_of(limit)
    filters = {"consent": consent}
    after = decode_cursor(cursor, filters)
    where = ["TRUE"]
    params: dict[str, Any] = {"n": n + 1}
    if consent:
        where.append(CONSENT_SQL[consent])
    if after:
        where.append("c.code > :after")
        params["after"] = str(after[0])
    with tx("read", s) as conn:
        rows = conn.execute(
            text(
                "SELECT c.code, c.consent_ref, c.consent_scope, c.consent_recorded_at, "
                "c.consent_withdrawn_at, c.created_at, "
                "(SELECT count(*) FROM projects pr WHERE pr.client_id = c.id) AS projects "
                f"FROM clients c WHERE {' AND '.join(where)} ORDER BY c.code LIMIT :n"
            ),
            params,
        ).all()
    items = [
        {
            "code": r.code,
            "consent": {
                "status": consent_status(r.consent_recorded_at, r.consent_withdrawn_at),
                "ref": r.consent_ref,
                "scope": sorted(r.consent_scope or []),
                "recorded_at": iso(r.consent_recorded_at),
                "withdrawn_at": iso(r.consent_withdrawn_at),
            },
            "projects": int(r.projects),
            "created_at": iso(r.created_at),
        }
        for r in rows
    ]
    items, pg = page(items, n, lambda it: [it["code"]], filters)
    return envelope({"items": items}, meta=_meta(), page=pg)


@router.get("/v1/admin/projects", summary="List projects (SDD-13 §5.3)")
def list_projects(
    request: Request,
    client: str | None = Query(default=None, pattern=CLIENT),
    limit: int | None = Query(default=None),
    cursor: str | None = Query(default=None),
    p: Principal = Depends(admin_reader),
) -> dict[str, Any]:
    s: Settings = request.app.state.settings
    n = limit_of(limit)
    filters = {"client": client}
    after = decode_cursor(cursor, filters)
    where = ["TRUE"]
    params: dict[str, Any] = {"n": n + 1}
    if client:
        where.append("c.code = :client")
        params["client"] = client
    if after:
        where.append("pr.code > :after")
        params["after"] = str(after[0])
    with tx("read", s) as conn:
        rows = conn.execute(
            text(
                "SELECT pr.code, c.code AS client, "
                "(SELECT count(*) FROM systems sy WHERE sy.project_id = pr.id) AS systems "
                "FROM projects pr JOIN clients c ON c.id = pr.client_id "
                f"WHERE {' AND '.join(where)} ORDER BY pr.code LIMIT :n"
            ),
            params,
        ).all()
    items = [{"code": r.code, "client": r.client, "systems": int(r.systems)} for r in rows]
    items, pg = page(items, n, lambda it: [it["code"]], filters)
    return envelope({"items": items}, meta=_meta(), page=pg)


@router.get("/v1/admin/systems", summary="List systems and their product repos (SDD-13 §5.3)")
def list_systems(
    request: Request,
    client: str | None = Query(default=None, pattern=CLIENT),
    project: str | None = Query(default=None, pattern=PROJECT),
    limit: int | None = Query(default=None),
    cursor: str | None = Query(default=None),
    p: Principal = Depends(admin_reader),
) -> dict[str, Any]:
    s: Settings = request.app.state.settings
    n = limit_of(limit)
    filters = {"client": client, "project": project}
    after = decode_cursor(cursor, filters)
    where = ["TRUE"]
    params: dict[str, Any] = {"n": n + 1}
    if client:
        where.append("c.code = :client")
        params["client"] = client
    if project:
        where.append("pr.code = :project")
        params["project"] = project
    if after:
        where.append("sy.code > :after")
        params["after"] = str(after[0])
    with tx("read", s) as conn:
        rows = conn.execute(
            text(
                "SELECT sy.id::text AS id, sy.code, pr.code AS project, c.code AS client, "
                "sy.domain, sy.companion_repo, sy.lifecycle_state, sy.created_at "
                "FROM systems sy JOIN projects pr ON pr.id = sy.project_id "
                "JOIN clients c ON c.id = pr.client_id "
                f"WHERE {' AND '.join(where)} ORDER BY sy.code LIMIT :n"
            ),
            params,
        ).all()
        repos: dict[str, list[dict[str, Any]]] = {}
        if rows:
            for r in conn.execute(
                text(
                    "SELECT system_id::text AS sid, name, github_full_name, kind FROM system_repos "
                    "WHERE system_id = ANY(CAST(:ids AS uuid[])) ORDER BY name"
                ),
                {"ids": [r.id for r in rows]},
            ).all():
                repos.setdefault(r.sid, []).append(
                    {"name": r.name, "github_full_name": r.github_full_name, "kind": r.kind}
                )
    items = [
        {
            "code": r.code,
            "project": r.project,
            "client": r.client,
            "domain": r.domain,
            "companion_repo": r.companion_repo,
            "lifecycle_state": r.lifecycle_state,
            "product_repos": repos.get(r.id, []),
            "created_at": iso(r.created_at),
        }
        for r in rows
    ]
    items, pg = page(items, n, lambda it: [it["code"]], filters)
    return envelope({"items": items}, meta=_meta(), page=pg)


GRANT_STATUS_SQL = {"active": "g.revoked_at IS NULL", "revoked": "g.revoked_at IS NOT NULL"}


@router.get("/v1/admin/role-grants", summary="List role grants, active and revoked (SDD-13 §5.3)")
def list_grants(
    request: Request,
    status: Literal["active", "revoked", "all"] = Query(default="all"),
    user: str | None = Query(default=None, pattern=PSEUDONYM),
    role: ROLE | None = Query(default=None),
    limit: int | None = Query(default=None),
    cursor: str | None = Query(default=None),
    p: Principal = Depends(admin_reader),
) -> dict[str, Any]:
    s: Settings = request.app.state.settings
    n = limit_of(limit)
    filters = {"status": status, "user": user, "role": role}
    after = decode_cursor(cursor, filters)
    where = ["TRUE"]
    params: dict[str, Any] = {"n": n + 1}
    if status in GRANT_STATUS_SQL:
        where.append(GRANT_STATUS_SQL[status])
    if user:
        where.append("u.pseudonym = :user")
        params["user"] = user
    if role:
        where.append("g.role = :role")
        params["role"] = role
    if after:
        where.append("(g.granted_at, g.id::text) < (CAST(:ca AS timestamptz), :cb)")
        params |= {"ca": after[0], "cb": after[1]}
    with tx("read", s) as conn:
        rows = conn.execute(
            text(
                "SELECT g.id::text AS id, u.pseudonym AS user, g.role, g.scope_type, "
                "CASE g.scope_type WHEN 'client' THEN c.code WHEN 'project' THEN pr.code "
                "WHEN 'system' THEN sy.code ELSE g.scope_id END AS scope, "
                "g.granted_at, b.pseudonym AS granted_by, g.revoked_at "
                "FROM role_grants g JOIN users u ON u.id = g.user_id "
                "LEFT JOIN users b ON b.id = g.granted_by "
                "LEFT JOIN clients c ON g.scope_type = 'client' AND c.id::text = g.scope_id "
                "LEFT JOIN projects pr ON g.scope_type = 'project' AND pr.id::text = g.scope_id "
                "LEFT JOIN systems sy ON g.scope_type = 'system' AND sy.id::text = g.scope_id "
                f"WHERE {' AND '.join(where)} ORDER BY g.granted_at DESC, g.id::text DESC "
                "LIMIT :n"
            ),
            params,
        ).all()
    keys = {r.id: [r.granted_at.isoformat(), r.id] for r in rows}
    items = [
        {
            "id": r.id,
            "user": r.user,
            "role": r.role,
            "scope_type": r.scope_type,
            "scope": r.scope,
            "status": "revoked" if r.revoked_at is not None else "active",
            "granted_at": iso(r.granted_at),
            "granted_by": r.granted_by,
            "revoked_at": iso(r.revoked_at),
        }
        for r in rows
    ]
    items, pg = page(items, n, lambda it: keys[it["id"]], filters)
    return envelope({"items": items}, meta=_meta(), page=pg)


@router.get(
    "/v1/admin/users",
    summary="List users: pseudonym, roles, active; names per RD-1 (SDD-13 §5.3)",
)
def list_users(
    request: Request,
    active: bool | None = Query(default=None),
    role: ROLE | None = Query(default=None),
    include: Literal["names"] | None = Query(default=None),
    limit: int | None = Query(default=None),
    cursor: str | None = Query(default=None),
    p: Principal = Depends(admin_reader),
) -> dict[str, Any]:
    s: Settings = request.app.state.settings
    assert p.user is not None  # noqa: S101
    n = limit_of(limit)
    filters = {"active": active, "role": role}
    after = decode_cursor(cursor, filters)
    where = ["TRUE"]
    params: dict[str, Any] = {"n": n + 1}
    if active is not None:
        where.append("u.active = :active")
        params["active"] = active
    if role:
        where.append(
            "EXISTS (SELECT 1 FROM role_grants r WHERE r.user_id = u.id AND r.role = :role "
            "AND r.revoked_at IS NULL)"
        )
        params["role"] = role
    if after:
        where.append("u.pseudonym > :after")
        params["after"] = str(after[0])
    with tx("read", s) as conn:
        rows = conn.execute(
            text(
                "SELECT u.id::text AS id, u.pseudonym, u.app_roles, u.active, u.created_at, "
                "u.erased_at, "
                "ARRAY(SELECT DISTINCT r.role FROM role_grants r WHERE r.user_id = u.id "
                "AND r.revoked_at IS NULL ORDER BY r.role) AS roles "
                f"FROM users u WHERE {' AND '.join(where)} ORDER BY u.pseudonym LIMIT :n"
            ),
            params,
        ).all()
    ids = {r.pseudonym: r.id for r in rows}
    items: list[dict[str, Any]] = [
        {
            "pseudonym": r.pseudonym,
            "app_roles": sorted(r.app_roles or []),
            "roles": list(r.roles or []),
            "active": bool(r.active),
            "erased": r.erased_at is not None,
            "created_at": iso(r.created_at),
            "display_name": None,
        }
        for r in rows
    ]
    items, pg = page(items, n, lambda it: [it["pseudonym"]], filters)
    # RD-1: names only for a caller holding a role in rd1_name_reveal_roles, and only on request.
    if include == "names" and any(g.role in s.rd1_name_reveal_roles for g in p.grants):
        names = reveal(s, {ids[it["pseudonym"]] for it in items})
        count = 0
        for it in items:
            name = names.get(ids[it["pseudonym"]])
            if name is not None:
                it["display_name"] = name
                count += 1
        record_reveal(s, p.user.id, "/v1/admin/users", count, [])
    return envelope({"items": items}, meta=_meta(), page=pg)


def key_status(revoked_at: Any, expires_at: Any, now: Any) -> str:
    if revoked_at is not None:
        return "revoked"
    return "expired" if expires_at <= now else "active"


@router.get("/v1/admin/users/{pseudonym}/keys", summary="List one user's signing keys")
def list_user_keys(
    request: Request,
    pseudonym: str = Path(pattern=PSEUDONYM),
    status: Literal["active", "revoked", "expired", "all"] = Query(default="all"),
    limit: int | None = Query(default=None),
    cursor: str | None = Query(default=None),
    p: Principal = Depends(admin_reader),
) -> dict[str, Any]:
    s: Settings = request.app.state.settings
    n = limit_of(limit)
    filters = {"pseudonym": pseudonym, "status": status}
    after = decode_cursor(cursor, filters)
    now = utcnow()
    with tx("read", s) as conn:
        uid = conn.execute(
            text("SELECT id::text FROM users WHERE pseudonym = :p"), {"p": pseudonym}
        ).scalar()
        if uid is None:
            raise ServiceError("E-API-04", "User not found")
        where = ["k.user_id = CAST(:u AS uuid)"]
        params: dict[str, Any] = {"u": uid, "n": n + 1, "now": now}
        if status == "active":
            where.append("k.revoked_at IS NULL AND k.expires_at > :now")
        elif status == "revoked":
            where.append("k.revoked_at IS NOT NULL")
        elif status == "expired":
            where.append("k.revoked_at IS NULL AND k.expires_at <= :now")
        if after:
            where.append("(k.created_at, k.key_id) < (CAST(:ca AS timestamptz), :cb)")
            params |= {"ca": after[0], "cb": after[1]}
        rows = conn.execute(
            text(
                "SELECT k.key_id, k.device_label, k.created_at, k.expires_at, k.revoked_at, "
                "k.revoked_reason FROM keys k "
                f"WHERE {' AND '.join(where)} ORDER BY k.created_at DESC, k.key_id DESC LIMIT :n"
            ),
            params,
        ).all()
    keys = {r.key_id: [r.created_at.isoformat(), r.key_id] for r in rows}
    items = [
        {
            "key_id": r.key_id,
            "device_label": r.device_label,
            "status": key_status(r.revoked_at, r.expires_at, now),
            "created_at": iso(r.created_at),
            "expires_at": iso(r.expires_at),
            "revoked_at": iso(r.revoked_at),
            "revoked_reason": r.revoked_reason,
        }
        for r in rows
    ]
    items, pg = page(items, n, lambda it: keys[it["key_id"]], filters)
    return envelope({"items": items}, meta={**_meta(), "user": pseudonym}, page=pg)
