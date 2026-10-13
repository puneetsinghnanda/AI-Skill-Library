"""Read API conventions: envelope, period, cursor, nulls (SDD-09 §5.1)."""

from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from sqlalchemy import Connection, text

from app.auth.scope import Scope
from app.errors import ServiceError
from app.timeutil import iso, utcnow

PERIOD_DAYS = {"30d": 30, "90d": 90, "12m": 365, "all": None}


@dataclass(frozen=True)
class Period:
    key: str
    start: date | None
    end: date
    prev_start: date | None
    prev_end: date | None

    def meta(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "from": self.start.isoformat() if self.start else None,
            "to": self.end.isoformat(),
            "prev_from": self.prev_start.isoformat() if self.prev_start else None,
            "prev_to": self.prev_end.isoformat() if self.prev_end else None,
        }


def period(
    key: str | None, default: str = "90d", allowed: tuple[str, ...] = ("30d", "90d", "12m", "all")
) -> Period:
    k = key or default
    if k not in allowed:
        raise ServiceError("E-API-01", f"period must be one of {', '.join(allowed)}")
    today = utcnow().date()
    days = PERIOD_DAYS[k]
    if days is None:
        return Period(k, None, today, None, None)
    start = today - timedelta(days=days - 1)
    prev_end = start - timedelta(days=1)
    return Period(k, start, today, prev_end - timedelta(days=days - 1), prev_end)


def ratio(n: Any, d: Any) -> float | None:
    """A ratio with denominator 0 is null (SDD-08 §10.4)."""
    if not d:
        return None
    return round(float(n or 0) / float(d), 4)


def data_as_of(conn: Connection, views: list[str]) -> str | None:
    if not views:
        return iso(utcnow())
    v = conn.execute(
        text("SELECT min(refreshed_at) FROM view_refresh_log WHERE view_name = ANY(:v)"),
        {"v": views},
    ).scalar()
    return iso(v)


def scope_meta(sc: Scope | None, class_a: bool = False) -> dict[str, Any]:
    if class_a or sc is None:
        return {"level": "org"}
    if sc.all_systems:
        return {
            "level": "all",
            "projects": sorted({i.project_code for i in sc.catalogue.values()}),
            "systems": sorted(i.code for i in sc.catalogue.values()),
        }
    infos = [sc.catalogue[x] for x in sc.systems if x in sc.catalogue]
    return {
        "level": "systems",
        "projects": sorted({i.project_code for i in infos}),
        "systems": sorted(i.code for i in infos),
    }


def envelope(
    data: Any, *, meta: dict[str, Any] | None = None, page: dict[str, Any] | None = None
) -> dict[str, Any]:
    m = {"generated_at": iso(utcnow())}
    m.update(meta or {})
    out: dict[str, Any] = {"data": data, "meta": m}
    if page is not None:
        out["page"] = page
    return out


def _fhash(filters: dict[str, Any]) -> str:
    norm = json.dumps(filters, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(norm.encode()).hexdigest()[:16]


def encode_cursor(keys: list[Any], filters: dict[str, Any]) -> str:
    raw = json.dumps({"k": keys, "f": _fhash(filters)}, separators=(",", ":"), default=str)
    return base64.urlsafe_b64encode(raw.encode()).rstrip(b"=").decode()


def decode_cursor(cursor: str | None, filters: dict[str, Any]) -> list[Any] | None:
    if not cursor:
        return None
    try:
        raw = json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))
        keys = raw["k"]
        f = raw["f"]
    except (ValueError, KeyError, TypeError):
        raise ServiceError("E-API-01", "Invalid cursor") from None
    if f != _fhash(filters) or not isinstance(keys, list):
        raise ServiceError("E-API-01", "Cursor used with other filters")
    return keys


def limit_of(limit: int | None) -> int:
    n = 25 if limit is None else limit
    if not 1 <= n <= 100:
        raise ServiceError("E-API-01", "limit must be 1-100")
    return n


def page(
    items: list[Any], limit: int, key_of: Any, filters: dict[str, Any]
) -> tuple[list[Any], dict[str, Any]]:
    """Trim a fetched list of ``limit + 1`` rows and build the page block."""
    more = len(items) > limit
    items = items[:limit]
    nxt = encode_cursor(key_of(items[-1]), filters) if more and items else None
    return items, {"limit": limit, "next_cursor": nxt}


def months_back(n: int) -> list[str]:
    today = utcnow().date().replace(day=1)
    out = []
    y, m = today.year, today.month
    for _ in range(n):
        out.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return list(reversed(out))
