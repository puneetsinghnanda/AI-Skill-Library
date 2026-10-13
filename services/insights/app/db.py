"""Database engines, one per role (SDD-08 §9.4). SQLAlchemy 2 Core with psycopg 3.

- ``app``: ingest, keys, admin, projector and jobs (DML).
- ``read``: read API routes (SELECT on core tables and views only; statement timeout 5 s).
- ``reveal``: the audited name reveal (SELECT on four ``users`` columns).
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Literal

from sqlalchemy import Connection, Engine, create_engine, event

from app.config import Settings, get_settings

Role = Literal["owner", "app", "read", "reveal"]

_lock = threading.Lock()
_engines: dict[tuple[int, Role], Engine] = {}


def engine(role: Role, settings: Settings | None = None) -> Engine:
    s = settings or get_settings()
    key = (id(s), role)
    with _lock:
        eng = _engines.get(key)
        if eng is None:
            eng = create_engine(
                s.database_url(role),
                pool_size=s.database_pool_size,
                max_overflow=2,
                pool_pre_ping=True,
            )
            if role == "read":
                timeout = int(s.read_statement_timeout_ms)

                @event.listens_for(eng, "connect")
                def _timeout(dbapi_conn, _rec):  # type: ignore[no-untyped-def]  # DBAPI hook
                    with dbapi_conn.cursor() as cur:
                        cur.execute(f"SET statement_timeout = {timeout}")
                    dbapi_conn.commit()

            _engines[key] = eng
        return eng


def dispose_all() -> None:
    with _lock:
        for eng in _engines.values():
            eng.dispose()
        _engines.clear()


@contextmanager
def tx(role: Role = "app", settings: Settings | None = None) -> Iterator[Connection]:
    """One transaction on the role's engine; commits on success, rolls back on error."""
    with engine(role, settings).begin() as conn:
        yield conn
