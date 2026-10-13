"""``GET /v1/systems/{code}``: registration, consent and lifecycle state (SDD-12 §5.3)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Path, Request
from sqlalchemy import text

from app.api.deps import tsl_writer
from app.auth.principal import Principal
from app.config import Settings
from app.db import tx
from app.errors import ServiceError

router = APIRouter(tags=["identity"])


@router.get("/v1/systems/{code}", summary="System record for tsl init and consent checks")
def get_system(
    request: Request,
    code: str = Path(pattern=r"^SYS-[0-9A-Z]{2,8}$"),
    p: Principal = Depends(tsl_writer),
) -> dict[str, Any]:
    s: Settings = request.app.state.settings
    with tx("app", s) as conn:
        row = conn.execute(
            text(
                "SELECT s.id::text AS id, s.code, p.code AS project, c.code AS client, "
                "s.companion_repo, "
                "s.lifecycle_state, c.consent_ref, c.consent_recorded_at, c.consent_scope, "
                "c.consent_withdrawn_at "
                "FROM systems s JOIN projects p ON p.id = s.project_id JOIN clients c ON c.id = "
                "p.client_id "
                "WHERE s.code = :c"
            ),
            {"c": code},
        ).first()
        if row is None:
            raise ServiceError("E-API-04", "System not registered")
        allowed = p.has("admin") or any(
            g.role in ("engineer", "tech_lead")
            and g.scope_type == "system"
            and g.scope_id == row.id
            for g in p.grants
        )
        if not allowed:
            raise ServiceError("E-API-03", "Needs engineer or tech_lead on this system")
        repos = conn.execute(
            text(
                "SELECT name, github_full_name, kind FROM system_repos WHERE system_id = CAST(:s "
                "AS "
                ""
                "uuid) ORDER BY name"
            ),
            {"s": row.id},
        ).all()
    recorded = row.consent_recorded_at is not None and row.consent_withdrawn_at is None
    return {
        "code": row.code,
        "project": row.project,
        "client": row.client,
        "companion_repo": row.companion_repo,
        "lifecycle_state": row.lifecycle_state,
        "consent": {
            "recorded": recorded,
            "scope": list(row.consent_scope) if recorded else [],
            "ref": row.consent_ref,
        },
        "product_repos": [
            {"name": r.name, "github_full_name": r.github_full_name, "kind": r.kind} for r in repos
        ],
    }
