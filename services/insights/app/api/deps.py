"""Route-level auth dependencies (SDD-08 §3.3 auth column, SDD-07 §9 route scopes)."""

from __future__ import annotations

from fastapi import Request

from app.auth.principal import Principal, authenticate
from app.errors import ServiceError

ENGINEER_APP_ROLES = frozenset({"Engineer", "TechLead", "Admin"})


def tsl_writer(request: Request) -> Principal:
    """``Events.Write`` from the ``truminds-tsl`` client."""
    return authenticate(
        request, route="ingest", scopes={"Events.Write"}, allow={"entra"}, clients={"tsl"}
    )


def events_writer(request: Request) -> Principal:
    """``Events.Write`` or a CI ingest token (``POST /v1/events``)."""
    return authenticate(
        request, route="ingest", scopes={"Events.Write"}, allow={"entra", "ci"}, clients={"tsl"}
    )


def tsl_or_ci(request: Request) -> Principal:
    return authenticate(
        request, route="ingest", scopes={"Events.Write"}, allow={"entra", "ci"}, clients={"tsl"}
    )


def tsl_or_portal_read(request: Request) -> Principal:
    """``GET /v1/me``, ``GET /v1/me/keys``: either client (SDD-07 §9)."""
    return authenticate(
        request, route="ingest", scopes={"Events.Write", "Portal.Read"}, allow={"entra"}
    )


def tsl_or_portal_write(request: Request) -> Principal:
    """``POST /v1/keys/{key_id}/revoke``: ``Events.Write`` from tsl or ``Portal.Write``."""
    p = authenticate(
        request, route="write", scopes={"Events.Write", "Portal.Write"}, allow={"entra"}
    )
    assert p.claims is not None  # noqa: S101 - entra principal
    if p.claims.client == "portal" and "Portal.Write" not in p.claims.scopes:
        raise ServiceError("E-ING-07", "Portal.Write scope required")
    return p


def portal_read(request: Request) -> Principal:
    return authenticate(
        request, route="read", scopes={"Portal.Read"}, allow={"entra"}, clients={"portal"}
    )


def portal_read_or_tsl(request: Request) -> Principal:
    """``GET /v1/improvement/skills/{skill_id}``: ``Portal.Read`` or ``Events.Write`` (registry "
    "§4)."""
    return authenticate(
        request, route="read", scopes={"Portal.Read", "Events.Write"}, allow={"entra"}
    )


def portal_write(request: Request) -> Principal:
    return authenticate(
        request, route="write", scopes={"Portal.Write"}, allow={"entra"}, clients={"portal"}
    )


def require_engineer_app_role(p: Principal) -> None:
    if p.claims is None or not (p.claims.roles & ENGINEER_APP_ROLES):
        raise ServiceError("E-AUTH-08", "App role Engineer, TechLead or Admin required")
