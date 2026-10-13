"""Name rule (SDD-09 §5.3; RD-1). Names are read through the ``insights_reveal`` role only and
every request that returns at least one name writes one ``audit_log`` row."""

from __future__ import annotations

from typing import Any

from sqlalchemy import text

from app.auth.users import audit
from app.config import Settings
from app.crypto import decrypt
from app.db import tx
from app.obs import metrics


def reveal(s: Settings, user_ids: set[str]) -> dict[str, str]:
    if not user_ids:
        return {}
    with tx("reveal", s) as conn:
        rows = conn.execute(
            text(
                "SELECT id::text AS id, display_name_enc, enc_key_id, erased_at FROM users "
                "WHERE id = ANY(CAST(:ids AS uuid[]))"
            ),
            {"ids": sorted(user_ids)},
        ).all()
    out: dict[str, str] = {}
    for r in rows:
        if r.erased_at is not None or r.display_name_enc is None:
            continue
        try:
            out[r.id] = decrypt(s, bytes(r.display_name_enc), r.enc_key_id)
        except ValueError:
            continue
    return out


def record_reveal(s: Settings, actor_id: str, route: str, count: int, systems: list[str]) -> None:
    if count <= 0:
        return
    with tx("app", s) as conn:
        audit(
            conn,
            actor_id,
            "reveal_names",
            "route",
            route,
            detail={"count": count, "systems": sorted(set(systems))},
        )
    metrics.NAME_REVEALS.labels(route=route).inc()


def apply_names(
    s: Settings,
    actor_id: str,
    route: str,
    items: list[dict[str, Any]],
    eligible: list[tuple[dict[str, Any], str | None, str]],
) -> None:
    """``eligible``: (engineer dict to fill, user id, system code) for rows in ``name_systems``."""
    ids = {uid for _d, uid, _c in eligible if uid}
    names = reveal(s, ids)
    n = 0
    systems: list[str] = []
    for d, uid, code in eligible:
        if uid and uid in names:
            d["display_name"] = names[uid]
            n += 1
            systems.append(code)
    record_reveal(s, actor_id, route, n, systems)
