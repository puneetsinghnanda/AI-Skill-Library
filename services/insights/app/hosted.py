"""``python -m app.entry allinone``: the hosted test environment in one process (deploy/render).

A free hosting plan runs one container with one public port and no shell, so this mode does at
start what the compose stack splits over ``migrate``, ``admin`` and ``worker``:

1. waits for the database (a hosted database may be waking from scale-to-zero);
2. runs the Alembic migrations as the owner (``DATABASE_URL_MIGRATIONS`` or ``DATABASE_URL``);
3. gives the three runtime roles their logins (passwords derived from ``DB_ROLE_PASSWORD_KEY``),
   so the api still connects as ``insights_app``, ``insights_read`` and ``insights_reveal`` and
   never as the owner;
4. ensures the event partitions, syncs the skill catalogue from the image, and registers the GitHub
   webhooks named in ``GITHUB_WEBHOOK_HOOKS``; all idempotent;
5. runs the worker jobs in a background thread behind the leader advisory lock, and uvicorn on
   ``$PORT`` (default 10000) in the foreground.

Test phase only (ADR 0006 addendum): ``check_hosting`` refuses the value secrets when ENV=prod.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from pathlib import Path
from typing import Literal

from psycopg import sql
from sqlalchemy import create_engine, pool, text

from app.config import SERVICE_DIR, Settings, get_settings

log = logging.getLogger("insights.hosted")
DEFAULT_PORT = 10000
RUNTIME_ROLES: tuple[Literal["app", "read", "reveal"], ...] = ("app", "read", "reveal")


def port_from_env(environ: dict[str, str] | os._Environ[str] = os.environ) -> int:
    raw = environ.get("PORT", "").strip()
    if not raw:
        return DEFAULT_PORT
    port = int(raw)
    if not 0 < port < 65536:
        raise ValueError(f"PORT {port} is out of range")
    return port


def wait_for_database(s: Settings, timeout_s: float = 120, step_s: float = 3) -> None:
    eng = create_engine(s.migrations_url(), poolclass=pool.NullPool)
    deadline = time.monotonic() + timeout_s
    try:
        while True:
            try:
                with eng.connect() as conn:
                    conn.execute(text("SELECT 1"))
                return
            except Exception as exc:
                if time.monotonic() >= deadline:
                    raise RuntimeError("database not reachable; check DATABASE_URL") from exc
                # The driver's first message line names the cause (host, auth, TLS) and never
                # the password.
                first = (str(exc).strip().splitlines() or [""])[0]
                why = f"{type(exc).__name__}: {first}"
                log.warning("database not reachable yet; retrying", extra={"code": why[:180]})
                time.sleep(step_s)
    finally:
        eng.dispose()


def migrate(s: Settings) -> None:
    from alembic.config import Config

    from alembic import command

    cfg = Config(str(SERVICE_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(SERVICE_DIR / "alembic"))
    cfg.attributes["url"] = s.migrations_url()
    command.upgrade(cfg, "head")


def ensure_role_logins(s: Settings) -> None:
    """Give the runtime roles (created NOLOGIN by migration 0001) their derived passwords.

    Runs as the owner, which created those roles and so holds ADMIN on them (PostgreSQL 16
    CREATEROLE rules; on Neon the project owner is such a role). Re-running sets the same values.
    The password goes as a quoted literal because ALTER ROLE takes no bind parameters.
    """
    users = {
        "app": s.database_app_user,
        "read": s.database_read_user,
        "reveal": s.database_reveal_user,
    }
    eng = create_engine(s.migrations_url(), poolclass=pool.NullPool, isolation_level="AUTOCOMMIT")
    try:
        with eng.connect() as conn:
            raw = conn.connection.driver_connection
            if raw is None:
                raise RuntimeError("no database connection")
            db = conn.execute(text("SELECT current_database()")).scalar_one()
            with raw.cursor() as cur:
                for role in RUNTIME_ROLES:
                    cur.execute(
                        sql.SQL("ALTER ROLE {} WITH LOGIN PASSWORD {}").format(
                            sql.Identifier(users[role]), sql.Literal(s.role_password(role))
                        )
                    )
                    cur.execute(
                        sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                            sql.Identifier(db), sql.Identifier(users[role])
                        )
                    )
    finally:
        eng.dispose()
    log.info("runtime role logins set")


def release_tag(root: Path) -> tuple[str, str] | None:
    tag_file = root / ".release-tag"
    if not tag_file.exists():
        return None
    tag, _, sha = tag_file.read_text(encoding="utf-8").strip().partition(" ")
    return tag, (sha.strip() or "unknown")


def sync_catalogue(s: Settings) -> None:
    root = s.catalogue_source_dir
    if root is None:
        return
    found = release_tag(root)
    if found is None:
        log.warning("CATALOGUE_SOURCE_DIR has no .release-tag; catalogue not synced")
        return
    from app.catalogue.sync import sync

    tag, sha = found
    if sha == "unknown":  # the build had no commit; Render also sets it at run time
        sha = os.environ.get("RENDER_GIT_COMMIT", "").strip() or "unknown"
    r = sync(s, root, tag, sha)
    log.info(
        "catalogue synced",
        extra={"code": f"{r.tag}: {r.skills} skills, {r.workflows} workflows, {r.pods} pods"},
    )


def parse_hooks(entries: tuple[str, ...]) -> list[tuple[int, str]]:
    out = []
    for e in entries:
        hook_id, sep, target = e.partition(":")
        if not sep or not hook_id.strip().isdigit() or not target.strip():
            raise RuntimeError(f"GITHUB_WEBHOOK_HOOKS entry {e!r} is not HOOK_ID:org[/repo]")
        out.append((int(hook_id), target.strip()))
    return out


def register_hooks(s: Settings) -> int:
    """Upsert the webhooks named in GITHUB_WEBHOOK_HOOKS with GITHUB_WEBHOOK_SECRET (encrypted)."""
    hooks = parse_hooks(s.github_webhook_hooks)
    if not hooks:
        return 0
    if s.github_webhook_secret is None:
        raise RuntimeError("GITHUB_WEBHOOK_HOOKS needs GITHUB_WEBHOOK_SECRET")
    secret = s.github_webhook_secret.get_secret_value()
    if len(secret) < 20:
        raise RuntimeError("GITHUB_WEBHOOK_SECRET must be at least 20 characters")
    from app.crypto import encrypt
    from app.db import tx

    with tx("owner", s) as conn:
        for hook_id, target in hooks:
            enc, key_id = encrypt(s, secret)
            conn.execute(
                text(
                    "INSERT INTO github_hooks (hook_id, target, secret_enc, enc_key_id) "
                    "VALUES (:h, :t, :s, :k) ON CONFLICT (hook_id) DO UPDATE SET "
                    "target = EXCLUDED.target, secret_enc = EXCLUDED.secret_enc, "
                    "enc_key_id = EXCLUDED.enc_key_id, revoked_at = NULL"
                ),
                {"h": hook_id, "t": target, "s": enc, "k": key_id},
            )
    log.info("github webhooks registered", extra={"code": ",".join(str(h) for h, _ in hooks)})
    return len(hooks)


def bootstrap(s: Settings) -> None:
    """Everything that must be true before the api starts. Idempotent; safe on every start."""
    s.check_identity()
    s.check_hosting()
    wait_for_database(s)
    migrate(s)
    if s.database_url_value is not None:
        ensure_role_logins(s)
    from app.jobs import partitions

    partitions.run(s, role="owner")
    sync_catalogue(s)
    register_hooks(s)
    from app.db import dispose_all

    dispose_all()  # close the owner's pooled sessions; the api and jobs use the runtime roles


def start_worker(s: Settings, stop: threading.Event) -> threading.Thread:
    """The worker jobs in a daemon thread; restarted after a database error."""
    from app.worker import run_loop

    def supervise() -> None:
        while not stop.is_set():
            try:
                run_loop(s, stop)
            except Exception:
                log.exception("worker loop stopped; restarting in 30 s")
                stop.wait(30)

    th = threading.Thread(target=supervise, name="insights-worker", daemon=True)
    th.start()
    return th


def main() -> int:
    from app.obs import logging as obslog

    obslog.setup("api")
    s = get_settings()
    port = port_from_env()
    bootstrap(s)
    stop = threading.Event()
    start_worker(s, stop)
    import uvicorn

    from app.main import create_app

    try:
        uvicorn.run(
            create_app(s),
            host="0.0.0.0",  # noqa: S104 - the platform routes its public HTTPS port here
            port=port,
            workers=1,
            proxy_headers=True,
            forwarded_allow_ips="*",
            log_config=None,
        )
    finally:
        stop.set()
    return 0
