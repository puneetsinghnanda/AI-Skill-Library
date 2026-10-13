"""``GET /v1/me`` (SDD-08 §3.1; fields SDD-09 §5.6.1).

The response is the SDD-09 envelope ``{"data": {...}}``. ``tsl`` (SDD-04 §6.1) reads
``pseudonym``, ``oid`` and ``grants`` at the top level, so those three are mirrored there.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy import text

from app.api.deps import tsl_or_portal_read
from app.auth.principal import Principal
from app.config import ENGINEER_FAMILY, Settings
from app.crypto import decrypt
from app.db import tx
from app.read.labels import ROLE_LABELS

router = APIRouter(tags=["identity"])


@router.get("/v1/me", summary="Who am I: pseudonym, grants, scope, default view")
def me(request: Request, p: Principal = Depends(tsl_or_portal_read)) -> dict[str, Any]:
    s: Settings = request.app.state.settings
    assert p.user is not None and p.claims is not None  # noqa: S101
    with tx("app", s) as conn:
        sc = p.scope(conn, s)
        row = conn.execute(
            text(
                "SELECT display_name_enc, enc_key_id, erased_at FROM users WHERE id = CAST(:u AS "
                "uuid)"
            ),
            {"u": p.user.id},
        ).one()
        skills = {}
        if any(g.scope_type in ("project", "client") for g in p.grants):
            skills = {
                r.id: r.code
                for r in conn.execute(text("SELECT id::text, code FROM projects")).all()
            }
            skills |= {
                r.id: r.code for r in conn.execute(text("SELECT id::text, code FROM clients")).all()
            }
    display = None
    if row.display_name_enc is not None and row.erased_at is None:
        try:
            display = decrypt(s, bytes(row.display_name_enc), row.enc_key_id)
        except ValueError:
            display = None
    roles: list[dict[str, Any]] = []
    grants: list[dict[str, Any]] = []
    for g in p.grants:
        code: str | None
        if g.scope_type == "system":
            info = sc.catalogue.get(g.scope_id or "")
            code = info.code if info else None
        elif g.scope_type in ("project", "client"):
            code = skills.get(g.scope_id or "")
        else:
            code = g.scope_id
        roles.append({"role": g.role, "scope_type": g.scope_type, "scope": code})
        grants.append(
            {"role": g.role, "scope": "org" if g.scope_type == "org" else f"{g.scope_type}:{code}"}
        )
    projects: dict[str, dict[str, Any]] = {}
    for sid in sorted(sc.system_ids()):
        info = sc.catalogue[sid]
        pr = projects.setdefault(info.project_code, {"code": info.project_code, "systems": []})
        pr["systems"].append({"code": info.code, "domain": info.domain})
    labels = [
        ROLE_LABELS[r]
        for r in ("engineer", "tech_lead", "skill_owner", "stage_approver", "eng_lead", "admin")
        if r in sc.roles
    ]
    eng = any(r in ENGINEER_FAMILY for r in sc.roles)
    data = {
        "pseudonym": p.user.pseudonym,
        "display_name": display,
        "role_label": " · ".join(labels) if labels else "Viewer",
        "roles": roles,
        "agent_role": p.user.agent_role,
        "default_view": "engineer" if eng else "business",
        "can_switch_view": eng,
        "can_reveal_names": sc.can_reveal_names,
        "scope": {"projects": sorted(projects.values(), key=lambda x: x["code"])},
        "app_roles": sorted(p.claims.roles),
    }
    return {"data": data, "pseudonym": p.user.pseudonym, "oid": p.claims.oid, "grants": grants}
