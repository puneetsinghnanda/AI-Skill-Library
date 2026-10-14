"""Readiness checks for ``GET /v1/health/ready`` (OPS-02 §4.2, SDD-08 §11.1)."""

from __future__ import annotations

from functools import lru_cache

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text

from app.auth.entra import EntraValidator
from app.config import SERVICE_DIR, Settings
from app.db import engine


@lru_cache(maxsize=1)
def head_revision() -> str:
    cfg = Config(str(SERVICE_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(SERVICE_DIR / "alembic"))
    head = ScriptDirectory.from_config(cfg).get_current_head()
    if head is None:
        raise RuntimeError("no alembic head")
    return head


def readiness(s: Settings, validator: EntraValidator | None) -> tuple[bool, dict[str, str]]:
    checks: dict[str, str] = {}
    try:
        with engine("app", s).connect() as conn:
            conn.execute(text("SELECT 1"))
            checks["db"] = "ok"
            rev = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
            checks["migration"] = "ok" if rev == head_revision() else "behind"
    except Exception:
        checks.setdefault("db", "fail")
        checks.setdefault("migration", "unknown")
    try:
        s.pepper()
        s.data_key()
        checks["secrets"] = "ok"
    except Exception:
        checks["secrets"] = "fail"
    if s.identity_provider == "entra":  # GitHub sign-in (ADR 0006) has no JWKS
        checks["jwks"] = "ok" if validator is not None and validator.refresh() else "fail"
    if s.portal_dir is not None:
        checks["static"] = "ok" if (s.portal_dir / "index.html").exists() else "fail"
    return all(v == "ok" for v in checks.values()), checks
