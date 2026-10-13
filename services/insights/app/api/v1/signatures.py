"""``POST /v1/signatures/verify``: key facts and server anchors for signed objects (SDD-07 §7.2).

Returns facts only; the accept rule runs in ``tsl`` (SDD-07 §7.3).
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

from app.api.deps import tsl_or_ci
from app.auth.principal import Principal
from app.config import Settings
from app.db import tx
from app.keyreg import facts, key_row, roles_at
from app.timeutil import iso, parse_iso

router = APIRouter(tags=["keys"])


class VerifyItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["verification", "approval", "pack", "eval"]
    key_id: str = Field(max_length=40)
    signed_at: str
    roles_needed: list[str] = Field(default_factory=list, max_length=7)
    anchor_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


class VerifyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    system: str = Field(pattern=r"^SYS-[0-9A-Z]{2,8}$")
    items: list[VerifyItem] = Field(max_length=500)


@router.post("/v1/signatures/verify", summary="Key facts and anchors for signed records")
def verify(
    body: VerifyRequest, request: Request, p: Principal = Depends(tsl_or_ci)
) -> dict[str, Any]:
    s: Settings = request.app.state.settings
    out: list[dict[str, Any]] = []
    with tx("app", s) as conn:
        for it in body.items:
            row = key_row(conn, it.key_id)
            if row is None:
                out.append({"key_id": it.key_id, "known": False})
                continue
            f = facts(row)
            f["known"] = True
            try:
                at = parse_iso(it.signed_at)
                f["roles_at"] = roles_at(conn, row.user_id, at, body.system)
            except ValueError:
                f["roles_at"] = []
            anchored = None
            if it.anchor_sha256:
                anchored = conn.execute(
                    text(
                        "SELECT anchored_at FROM signature_anchors WHERE sha256 = :h AND key_id = "
                        ":k"
                    ),
                    {"h": it.anchor_sha256, "k": it.key_id},
                ).scalar()
            f["anchored_at"] = iso(anchored)
            out.append(f)
    return {"items": out}
