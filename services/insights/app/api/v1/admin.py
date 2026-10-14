"""Admin operations (SDD-13 §7.2). ``Portal.Write`` scope and the ``admin`` grant (app role Admin).

All routes are in the published OpenAPI file; every write produces an ``audit_log`` row.
"""

from __future__ import annotations

import os
from typing import Any, Literal

from fastapi import APIRouter, Depends, Path, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Connection, text
from sqlalchemy.exc import IntegrityError

from app.api.deps import portal_write
from app.auth.principal import Principal
from app.auth.users import CEILING, allowed_by_ceiling, audit
from app.config import Settings
from app.crypto import encrypt
from app.db import tx
from app.errors import ServiceError
from app.ingest.denylist import name_hashes
from app.timeutil import iso

router = APIRouter(tags=["admin"])
CLIENT = r"^CL-[0-9A-Z]{2,8}$"
PROJECT = r"^PRJ-[0-9A-Z]{2,8}$"
SYSTEM = r"^SYS-[0-9A-Z]{2,8}$"
REPO = r"^[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}$"
CONSENT_SCOPES = Literal["code_processing", "companion_storage", "product_prs", "ci_webhook"]


def _admin(request: Request) -> Principal:
    p = portal_write(request)
    if not p.has("admin"):
        raise ServiceError("E-API-03", "Admin only")
    return p


class ClientIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str = Field(pattern=CLIENT)
    display_name: str = Field(min_length=1, max_length=200)
    aliases: list[str] = Field(default_factory=list, max_length=20)


def _update_denylist(conn: Connection, names: list[str]) -> int:
    row = conn.execute(
        text("SELECT version, salt, hashes FROM client_denylist ORDER BY version DESC LIMIT 1")
    ).first()
    salt = bytes(row.salt) if row else os.urandom(16)
    hashes = set(row.hashes) if row else set()
    for n in names:
        hashes |= name_hashes(salt, n)
    version = (row.version if row else 0) + 1
    conn.execute(
        text(
            "INSERT INTO client_denylist (version, salt, hashes, created_at) VALUES (:v, :s, :h, "
            ""
            "now())"
        ),
        {"v": version, "s": salt, "h": sorted(hashes)},
    )
    return int(version)


@router.post("/v1/admin/clients", status_code=201, summary="Create a client (SDD-13 §7.2)")
def create_client(
    body: ClientIn, request: Request, p: Principal = Depends(_admin)
) -> dict[str, Any]:
    s: Settings = request.app.state.settings
    assert p.user is not None  # noqa: S101
    enc, key_id = encrypt(s, body.display_name)
    with tx("app", s) as conn:
        try:
            cid = conn.execute(
                text(
                    "INSERT INTO clients (code, display_name_enc) VALUES (:c, :n) RETURNING "
                    "id::text"
                ),
                {"c": body.code, "n": enc},
            ).scalar_one()
        except IntegrityError:
            raise ServiceError("E-API-01", "Client code already exists") from None
        version = _update_denylist(conn, [body.display_name, *body.aliases])
        audit(
            conn,
            p.user.id,
            "client_create",
            "client",
            body.code,
            after={"code": body.code, "key_id": key_id},
        )
        audit(
            conn,
            p.user.id,
            "denylist_change",
            "client_denylist",
            str(version),
            detail={"client": body.code},
        )
    return {"id": cid, "code": body.code, "denylist_version": version}


class ConsentIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["record", "withdraw"] = "record"
    consent_ref: str | None = Field(default=None, pattern=r"^[A-Z0-9-]{3,40}$")
    scope: list[CONSENT_SCOPES] = Field(default_factory=list)


@router.post("/v1/admin/clients/{code}/consent", summary="Record or withdraw client consent")
def consent(
    body: ConsentIn,
    request: Request,
    code: str = Path(pattern=CLIENT),
    p: Principal = Depends(_admin),
) -> dict[str, Any]:
    s: Settings = request.app.state.settings
    assert p.user is not None  # noqa: S101
    with tx("app", s) as conn:
        before = conn.execute(
            text(
                "SELECT consent_ref, consent_scope, consent_withdrawn_at FROM clients WHERE code "
                "= "
                ":c"
            ),
            {"c": code},
        ).first()
        if before is None:
            raise ServiceError("E-API-04", "Client not found")
        if body.action == "record":
            if not body.consent_ref or not body.scope:
                raise ServiceError("E-API-01", "consent_ref and scope are required")
            r = conn.execute(
                text(
                    "UPDATE clients SET consent_ref = :r, consent_scope = :sc, "
                    "consent_recorded_at "
                    "= now(), "
                    "consent_withdrawn_at = NULL WHERE code = :c RETURNING consent_recorded_at, "
                    "consent_withdrawn_at"
                ),
                {"r": body.consent_ref, "sc": sorted(set(body.scope)), "c": code},
            ).one()
            action = "consent_record"
        else:
            r = conn.execute(
                text(
                    "UPDATE clients SET consent_withdrawn_at = now() WHERE code = :c "
                    "RETURNING consent_recorded_at, consent_withdrawn_at"
                ),
                {"c": code},
            ).one()
            action = "consent_withdraw"
        audit(
            conn,
            p.user.id,
            action,
            "client",
            code,
            before={"ref": before.consent_ref, "scope": list(before.consent_scope)},
            after={"ref": body.consent_ref, "scope": sorted(set(body.scope))},
        )
    return {
        "code": code,
        "recorded_at": iso(r.consent_recorded_at),
        "withdrawn_at": iso(r.consent_withdrawn_at),
    }


class ProjectIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    client: str = Field(pattern=CLIENT)
    code: str = Field(pattern=PROJECT)


@router.post("/v1/admin/projects", status_code=201, summary="Create a project")
def create_project(
    body: ProjectIn, request: Request, p: Principal = Depends(_admin)
) -> dict[str, Any]:
    s: Settings = request.app.state.settings
    assert p.user is not None  # noqa: S101
    with tx("app", s) as conn:
        cid = conn.execute(
            text("SELECT id FROM clients WHERE code = :c"), {"c": body.client}
        ).scalar()
        if cid is None:
            raise ServiceError("E-API-04", "Client not found")
        try:
            pid = conn.execute(
                text("INSERT INTO projects (client_id, code) VALUES (:c, :p) RETURNING id::text"),
                {"c": cid, "p": body.code},
            ).scalar_one()
        except IntegrityError:
            raise ServiceError("E-API-01", "Project code already exists") from None
        audit(
            conn, p.user.id, "project_create", "project", body.code, after={"client": body.client}
        )
    return {"id": pid, "code": body.code, "client": body.client}


class RepoIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,60}$")
    github_full_name: str = Field(pattern=REPO)
    kind: Literal["product", "read_only"] = "product"


class SystemIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project: str = Field(pattern=PROJECT)
    code: str = Field(pattern=SYSTEM)
    domain: str = Field(pattern=r"^[a-z][a-z0-9-]{1,30}$")
    companion_repo: str = Field(pattern=REPO)
    product_repos: list[RepoIn] = Field(default_factory=list, max_length=20)


@router.post("/v1/admin/systems", status_code=201, summary="Create a system and its product repos")
def create_system(
    body: SystemIn, request: Request, p: Principal = Depends(_admin)
) -> dict[str, Any]:
    s: Settings = request.app.state.settings
    assert p.user is not None  # noqa: S101
    with tx("app", s) as conn:
        pid = conn.execute(
            text("SELECT id FROM projects WHERE code = :c"), {"c": body.project}
        ).scalar()
        if pid is None:
            raise ServiceError("E-API-04", "Project not found")
        try:
            sid = conn.execute(
                text(
                    "INSERT INTO systems (project_id, code, domain, companion_repo) VALUES (:p, "
                    ":c, "
                    ""
                    ":d, :r) RETURNING id::text"
                ),
                {"p": pid, "c": body.code, "d": body.domain, "r": body.companion_repo},
            ).scalar_one()
            for repo in body.product_repos:
                conn.execute(
                    text(
                        "INSERT INTO system_repos (system_id, name, github_full_name, kind) "
                        "VALUES (CAST(:s AS uuid), :n, :g, :k)"
                    ),
                    {"s": sid, "n": repo.name, "g": repo.github_full_name, "k": repo.kind},
                )
        except IntegrityError:
            raise ServiceError("E-API-01", "System code or repo already exists") from None
        audit(
            conn,
            p.user.id,
            "system_create",
            "system",
            body.code,
            after={"project": body.project, "repos": [r.name for r in body.product_repos]},
        )
    return {"id": sid, "code": body.code, "project": body.project}


class GrantIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user: str = Field(pattern=r"^eng-[0-9a-f]{4,8}$")
    role: Literal[
        "viewer", "engineer", "tech_lead", "skill_owner", "stage_approver", "eng_lead", "admin"
    ]
    scope_type: Literal["org", "client", "project", "system", "skill", "stage"]
    scope: str | None = Field(default=None, max_length=60)


ROLE_SCOPES = {
    "viewer": {"org"},
    "engineer": {"system"},
    "tech_lead": {"system"},
    "skill_owner": {"skill"},
    "stage_approver": {"stage"},
    "eng_lead": {"org", "client", "project"},
    "admin": {"org"},
}


def _scope_id(conn: Connection, scope_type: str, scope: str | None) -> str | None:
    if scope_type == "org":
        return None
    if not scope:
        raise ServiceError("E-API-01", "scope is required")
    table = {"client": "clients", "project": "projects", "system": "systems"}.get(scope_type)
    if table:
        sid = conn.execute(
            text(f"SELECT id::text FROM {table} WHERE code = :c"), {"c": scope}
        ).scalar()
    elif scope_type == "skill":
        sid = conn.execute(text("SELECT id FROM skills WHERE id = :c"), {"c": scope}).scalar()
    else:
        sid = scope if scope in ("requirements", "design", "build", "test", "operate") else None
    if sid is None:
        raise ServiceError("E-API-04", "Scope not found")
    return str(sid)


@router.post(
    "/v1/admin/role-grants", status_code=201, summary="Grant a role (not to self, E-ADM-01)"
)
def grant(body: GrantIn, request: Request, p: Principal = Depends(_admin)) -> dict[str, Any]:
    s: Settings = request.app.state.settings
    assert p.user is not None  # noqa: S101
    if body.scope_type not in ROLE_SCOPES[body.role]:
        raise ServiceError("E-API-01", f"{body.role} cannot be granted at {body.scope_type} scope")
    with tx("app", s) as conn:
        u = conn.execute(
            text("SELECT id::text, app_roles, active FROM users WHERE pseudonym = :p"),
            {"p": body.user},
        ).first()
        if u is None or not u.active:
            raise ServiceError("E-API-04", "User not found")
        if u.id == p.user.id:
            raise ServiceError("E-ADM-01")
        # With GitHub (ADR 0006) app roles are derived from grants, so there is no ceiling to check.
        if s.identity_provider == "entra" and not allowed_by_ceiling(
            body.role, frozenset(u.app_roles or [])
        ):
            raise ServiceError(
                "E-API-01",
                f"The user's app roles do not allow {body.role} "
                f"(needs {sorted(CEILING[body.role])})",
            )
        sid = _scope_id(conn, body.scope_type, body.scope)
        try:
            gid = conn.execute(
                text(
                    "INSERT INTO role_grants (user_id, role, scope_type, scope_id, granted_at, "
                    "granted_by) "
                    "VALUES (CAST(:u AS uuid), :r, :t, :s, now(), CAST(:by AS uuid)) RETURNING "
                    "id::text"
                ),
                {"u": u.id, "r": body.role, "t": body.scope_type, "s": sid, "by": p.user.id},
            ).scalar_one()
        except IntegrityError:
            raise ServiceError("E-API-01", "The grant already exists") from None
        audit(
            conn,
            p.user.id,
            "role_grant",
            "role_grant",
            gid,
            after={
                "user": body.user,
                "role": body.role,
                "scope_type": body.scope_type,
                "scope": body.scope,
            },
        )
    return {
        "id": gid,
        "user": body.user,
        "role": body.role,
        "scope_type": body.scope_type,
        "scope": body.scope,
    }


class ReasonIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=1, max_length=200)


@router.post("/v1/admin/role-grants/{grant_id}/revoke", summary="Revoke a role grant")
def revoke_grant(
    body: ReasonIn,
    request: Request,
    grant_id: str = Path(pattern=r"^[0-9a-f-]{36}$"),
    p: Principal = Depends(_admin),
) -> dict[str, Any]:
    s: Settings = request.app.state.settings
    assert p.user is not None  # noqa: S101
    with tx("app", s) as conn:
        r = conn.execute(
            text(
                "UPDATE role_grants SET revoked_at = now() WHERE id = CAST(:g AS uuid) AND "
                "revoked_at IS NULL "
                "RETURNING role, scope_type, scope_id, revoked_at"
            ),
            {"g": grant_id},
        ).first()
        if r is None:
            raise ServiceError("E-API-04", "Active grant not found")
        audit(
            conn,
            p.user.id,
            "role_revoke",
            "role_grant",
            grant_id,
            before={"role": r.role, "scope_type": r.scope_type, "scope_id": r.scope_id},
            reason=body.reason,
        )
    return {"id": grant_id, "revoked_at": iso(r.revoked_at)}


@router.post(
    "/v1/admin/users/{pseudonym}/deactivate",
    summary="Deactivate a user: keys offboarded, grants revoked",
)
def deactivate(
    body: ReasonIn,
    request: Request,
    pseudonym: str = Path(pattern=r"^eng-[0-9a-f]{4,8}$"),
    p: Principal = Depends(_admin),
) -> dict[str, Any]:
    s: Settings = request.app.state.settings
    assert p.user is not None  # noqa: S101
    with tx("app", s) as conn:
        u = conn.execute(
            text("UPDATE users SET active = false WHERE pseudonym = :p RETURNING id::text"),
            {"p": pseudonym},
        ).first()
        if u is None:
            raise ServiceError("E-API-04", "User not found")
        keys = (
            conn.execute(
                text(
                    "UPDATE keys SET revoked_at = now(), revoked_reason = 'offboarded', "
                    "revoked_by "
                    "= CAST(:a AS uuid) "
                    "WHERE user_id = CAST(:u AS uuid) AND revoked_at IS NULL RETURNING key_id"
                ),
                {"u": u.id, "a": p.user.id},
            )
            .scalars()
            .all()
        )
        grants = (
            conn.execute(
                text(
                    "UPDATE role_grants SET revoked_at = now() WHERE user_id = CAST(:u AS uuid) "
                    "AND "
                    ""
                    "revoked_at IS NULL "
                    "RETURNING id::text"
                ),
                {"u": u.id},
            )
            .scalars()
            .all()
        )
        for k in keys:
            audit(
                conn,
                p.user.id,
                "key_revoke",
                "key",
                k,
                after={"revoked_reason": "offboarded"},
                reason=body.reason,
            )
        audit(
            conn,
            p.user.id,
            "user_deactivate",
            "user",
            pseudonym,
            after={"keys_revoked": list(keys), "grants_revoked": len(grants)},
            reason=body.reason,
        )
    return {
        "pseudonym": pseudonym,
        "active": False,
        "keys_revoked": list(keys),
        "grants_revoked": len(grants),
    }
