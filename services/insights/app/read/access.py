"""Access matrix helpers (SDD-09 §5.4)."""

from __future__ import annotations

from app.auth.scope import Scope
from app.errors import ServiceError


def require_engineer_family(sc: Scope) -> None:
    if not sc.engineer_family:
        raise ServiceError("E-API-03", "This view needs an engineer-family role")


def require_any_grant(sc: Scope) -> None:
    if not sc.any_grant:
        raise ServiceError("E-API-03", "You do not have access yet. Ask an admin.")


def systems_filter(sc: Scope, project: str | None, system: str | None) -> list[str]:
    """System ids in scope after the ``project`` and ``system`` filters; outside scope -> "
    "E-API-04."""
    ids = sc.system_ids()
    if project:
        ids = [x for x in ids if sc.catalogue[x].project_code == project]
        if not ids:
            raise ServiceError("E-API-04", "Project not found")
    if system:
        ids = [x for x in ids if sc.catalogue[x].code == system]
        if not ids:
            raise ServiceError("E-API-04", "System not found")
    return ids
