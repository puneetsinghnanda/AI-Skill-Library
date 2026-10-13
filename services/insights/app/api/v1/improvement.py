"""Improvement loop read and flag routes (SDD-11 §5.4, §9)."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, Path, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

from app.api.deps import portal_read, portal_read_or_tsl, portal_write
from app.auth.principal import Principal
from app.auth.users import audit
from app.config import Settings
from app.db import tx
from app.errors import ServiceError
from app.ingest.denylist import check_string
from app.read.common import envelope
from app.timeutil import iso, iso_date

router = APIRouter(tags=["improvement"])
SKILL_ID = r"^[a-z][a-z0-9-]{2,39}$"
FLAG_ID = r"^flg_[0-9A-HJKMNP-TV-Z]{26}$"


def _allowed_skills(p: Principal) -> set[str] | None:
    """None = every skill (eng_lead, admin); else the owned skills; empty -> 403."""
    if p.has("admin") or p.has("eng_lead"):
        return None
    owned = {g.scope_id for g in p.grants if g.role == "skill_owner" and g.scope_id}
    if not owned:
        raise ServiceError("E-API-03", "Needs skill_owner, eng_lead or admin")
    return owned


def _flag(r: Any) -> dict[str, Any]:
    return {
        "flag_id": r.id,
        "skill_id": r.skill_id,
        "skill_version": r.skill_version,
        "signal": r.signal,
        "value": float(r.value),
        "threshold": float(r.threshold),
        "sample": r.sample,
        "status": r.status,
        "dismissed_reason": r.dismissed_reason,
        "opened_at": iso(r.opened_at),
        "updated_at": iso(r.updated_at),
    }


@router.get("/v1/improvement/flags", summary="Improvement flags (SDD-11 §5.4)")
def flags(
    request: Request,
    skill: str | None = Query(default=None, pattern=SKILL_ID),
    status: str | None = Query(default=None, max_length=80),
    signal: str | None = Query(default=None, pattern=r"^IS-[0-9]+$"),
    p: Principal = Depends(portal_read),
) -> dict[str, Any]:
    s: Settings = request.app.state.settings
    allowed = _allowed_skills(p)
    where: list[str] = ["TRUE"]
    prm: dict[str, Any] = {}
    if skill:
        where.append("skill_id = :k")
        prm["k"] = skill
    if status:
        where.append("status = ANY(:st)")
        prm["st"] = [x for x in status.split(",") if x]
    if signal:
        where.append("signal = :sg")
        prm["sg"] = signal
    if allowed is not None:
        where.append("skill_id = ANY(:own)")
        prm["own"] = sorted(allowed)
    with tx("read", s) as conn:
        rows = conn.execute(
            text(
                f"SELECT * FROM skill_flags WHERE {' AND '.join(where)} ORDER BY opened_at DESC, id"
            ),
            prm,
        ).all()
    return envelope({"items": [_flag(r) for r in rows]}, meta={"scope": {"level": "skills"}})


@router.get(
    "/v1/improvement/skills/{skill_id}",
    summary="Latest improvement report of a skill (SDD-11 §4.4)",
)
def report(
    request: Request,
    skill_id: str = Path(pattern=SKILL_ID),
    version: str | None = Query(default=None, max_length=20),
    window: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    p: Principal = Depends(portal_read_or_tsl),
) -> dict[str, Any]:
    s: Settings = request.app.state.settings
    allowed = _allowed_skills(p)
    if allowed is not None and skill_id not in allowed:
        raise ServiceError("E-API-03", "Not an owner of this skill")
    with tx("read", s) as conn:
        ver = (
            version
            or conn.execute(
                text("SELECT current_version FROM skills WHERE id = :k"), {"k": skill_id}
            ).scalar()
        )
        if ver is None:
            raise ServiceError("E-API-04", "Skill not found")
        cond = "window_end = CAST(:w AS date)" if window else "TRUE"
        row = conn.execute(
            text(
                "SELECT window_end, body FROM improvement_reports WHERE skill_id = :k AND "
                f"skill_version = :v AND {cond} "
                f"ORDER BY window_end DESC LIMIT 1"
            ),
            {"k": skill_id, "v": ver, "w": window},
        ).first()
        if row is None:
            raise ServiceError("E-API-04", "No report for this skill version yet")
        live = conn.execute(
            text("SELECT * FROM skill_flags WHERE skill_id = :k ORDER BY opened_at DESC"),
            {"k": skill_id},
        ).all()
    body = dict(row.body)
    body["flags"] = [_flag(r) for r in live]
    body["window_end"] = iso_date(row.window_end)
    out = envelope(body, meta={"scope": {"level": "org"}})
    # tsl improve plan (SDD-04 §6.17) reads these two lists at the top level.
    out["flags"] = body["flags"]
    out["clusters"] = body.get("clusters", [])
    return out


class FlagPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["IN_PROGRESS", "DISMISSED"]
    reason: str | None = Field(default=None, max_length=200)


@router.patch("/v1/improvement/flags/{flag_id}", summary="Change a flag's status (skill owner)")
def patch_flag(
    body: FlagPatch,
    request: Request,
    flag_id: str = Path(pattern=FLAG_ID),
    p: Principal = Depends(portal_write),
) -> dict[str, Any]:
    s: Settings = request.app.state.settings
    assert p.user is not None  # noqa: S101
    if body.status == "DISMISSED" and not body.reason:
        raise ServiceError("E-API-01", "A reason is required to dismiss a flag")
    if body.reason and check_string("reason", body.reason):
        raise ServiceError("E-API-01", "reason failed the deny-list")
    with tx("app", s) as conn:
        f = conn.execute(
            text("SELECT * FROM skill_flags WHERE id = :f FOR UPDATE"), {"f": flag_id}
        ).first()
        if f is None:
            raise ServiceError("E-API-04", "Flag not found")
        if not any(g.role == "skill_owner" and g.scope_id == f.skill_id for g in p.grants):
            raise ServiceError("E-API-03", "Only the skill owner may change this flag")
        ok_from = {"IN_PROGRESS": {"OPEN", "REOPENED"}, "DISMISSED": {"OPEN"}}[body.status]
        if f.status not in ok_from:
            raise ServiceError("E-API-01", f"Cannot move a {f.status} flag to {body.status}")
        r = conn.execute(
            text(
                "UPDATE skill_flags SET status = :st, dismissed_reason = :r, updated_at = now() "
                "WHERE id = :f RETURNING *"
            ),
            {
                "st": body.status,
                "r": body.reason if body.status == "DISMISSED" else None,
                "f": flag_id,
            },
        ).one()
        audit(
            conn,
            p.user.id,
            "flag_update",
            "skill_flag",
            flag_id,
            before={"status": f.status},
            after={"status": body.status},
            reason=body.reason,
        )
    return envelope(_flag(r))
