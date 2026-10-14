"""Hosted test environment (deploy/render, ``python -m app.entry allinone``).

Covers: Neon URL handling, value secrets refused in production, ``$PORT``, the SPA fallback never
shadowing API paths, the portal security headers, the worker leader lock, and the whole start-up
bootstrap as a non-superuser owner with CREATEROLE (what a Neon project owner is) on a fresh
cluster that checks passwords.
"""

from __future__ import annotations

import base64
import os
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

from app import hosted
from app.config import Settings, hosted_database_url
from app.main import create_app, is_portal_path, portal_csp
from tests.conftest import PG, PG_BIN, ROOT, SERVICE, pg_cluster

NEON = (
    "postgresql://neondb_owner:npg_secretvalue@ep-quiet-sun-a1b2c3d4.ap-southeast-1.aws.neon.tech"
    "/neondb?sslmode=require&channel_binding=require"
)
ROLE_KEY = "k" * 44


def _b64(n: int) -> str:
    return base64.b64encode(os.urandom(n)).decode()


# ----- Neon URL parsing -----


def test_neon_url_becomes_a_psycopg_url_and_keeps_tls_options() -> None:
    url = hosted_database_url(NEON, None)
    assert url.startswith("postgresql+psycopg://neondb_owner:npg_secretvalue@ep-quiet-sun-")
    assert "sslmode=require" in url
    assert "channel_binding=require" in url
    as_app = hosted_database_url(NEON, ("insights_app", "pw123"))
    assert as_app.startswith("postgresql+psycopg://insights_app:pw123@ep-quiet-sun-")
    assert "/neondb?" in as_app


def test_postgres_short_scheme_is_accepted() -> None:
    url = hosted_database_url(NEON.replace("postgresql://", "postgres://"), None)
    assert url.startswith("postgresql+psycopg://")


@pytest.mark.parametrize(
    ("raw", "why"),
    [
        (NEON.replace("ep-quiet-sun-a1b2c3d4.", "ep-quiet-sun-a1b2c3d4-pooler."), "pooled"),
        (NEON.split("?")[0], "TLS"),
        (NEON.replace("sslmode=require", "sslmode=disable"), "TLS"),
        ("mysql://u:p@db.example.invalid/x", "postgresql"),
        ("postgresql://u:p@db.example.invalid", "database name"),
        ("not a url", "valid"),
    ],
)
def test_bad_database_urls_are_refused(raw: str, why: str) -> None:
    with pytest.raises(RuntimeError, match=why):
        hosted_database_url(raw, None)


def test_local_url_without_tls_is_allowed() -> None:
    assert hosted_database_url("postgresql://u:p@localhost:5432/x", None)


def test_settings_from_render_style_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    key = _b64(32)
    for k, v in {
        "DATABASE_URL": NEON,
        "DB_ROLE_PASSWORD_KEY": ROLE_KEY,
        "DATA_KEY": key,
        "PSEUDONYM_PEPPER": _b64(32),
        "ENVIRONMENT": "test",
        "SERVE_PORTAL_DIR": "/app/portal",
        "GITHUB_WEBHOOK_HOOKS": "123:example-org/companion, 456:example-org",
    }.items():
        monkeypatch.setenv(k, v)
    s = Settings()
    s.check_hosting()
    assert s.data_key() == base64.b64decode(key)
    assert len(s.pepper()) >= 32
    assert s.portal_dir == Path("/app/portal")
    assert s.database_url("owner").startswith("postgresql+psycopg://neondb_owner:")
    app_url = s.database_url("app")
    assert app_url.startswith(f"postgresql+psycopg://insights_app:{s.role_password('app')}@")
    assert s.role_password("app") != s.role_password("read")
    assert len(s.role_password("reveal")) == 64  # 256 bits of hex, over Neon's 60-bit minimum
    assert s.migrations_url() == s.database_url("owner")
    assert hosted.parse_hooks(s.github_webhook_hooks) == [
        (123, "example-org/companion"),
        (456, "example-org"),
    ]


def test_migrations_url_override(monkeypatch: pytest.MonkeyPatch) -> None:
    other = NEON.replace("ep-quiet-sun-a1b2c3d4", "ep-other-host-9z")
    s = Settings(
        database_url_value=SecretStr(NEON),
        database_url_migrations=SecretStr(other),
        db_role_password_key=SecretStr(ROLE_KEY),
    )
    assert "ep-other-host-9z" in s.migrations_url()
    assert "ep-quiet-sun" in s.database_url("owner")


def test_value_secrets_are_refused_in_production() -> None:
    s = Settings(
        env="prod", database_url_value=SecretStr(NEON), db_role_password_key=SecretStr(ROLE_KEY)
    )
    with pytest.raises(RuntimeError, match="test phase only"):
        s.check_hosting()
    with pytest.raises(RuntimeError, match="test phase only"):
        Settings(env="prod", data_key_value=SecretStr(_b64(32))).check_hosting()


def test_database_url_needs_the_role_password_key() -> None:
    with pytest.raises(RuntimeError, match="DB_ROLE_PASSWORD_KEY"):
        Settings(database_url_value=SecretStr(NEON)).check_hosting()
    with pytest.raises(RuntimeError, match="at least 32"):
        Settings(
            database_url_value=SecretStr(NEON), db_role_password_key=SecretStr("short")
        ).check_hosting()


@pytest.mark.parametrize("bad", ["12x", "1:", ":org/repo", "org/repo"])
def test_bad_hook_entries_are_refused(bad: str) -> None:
    with pytest.raises(RuntimeError, match="HOOK_ID"):
        hosted.parse_hooks((bad,))


# ----- $PORT -----


def hosted_main_module() -> Any:
    import app.main

    return app.main


def test_port_defaults_to_10000_and_honours_port() -> None:
    assert hosted.port_from_env({}) == 10000
    assert hosted.port_from_env({"PORT": ""}) == 10000
    assert hosted.port_from_env({"PORT": "12345"}) == 12345
    with pytest.raises(ValueError):
        hosted.port_from_env({"PORT": "70000"})
    with pytest.raises(ValueError):
        hosted.port_from_env({"PORT": "http"})


def test_allinone_runs_uvicorn_on_port(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}
    monkeypatch.setenv("PORT", "12345")
    monkeypatch.setattr(hosted, "bootstrap", lambda s: seen.setdefault("bootstrap", True))
    monkeypatch.setattr(hosted, "start_worker", lambda s, stop: seen.setdefault("worker", stop))
    import uvicorn

    monkeypatch.setattr(hosted_main_module(), "create_app", lambda s: "the-app")
    monkeypatch.setattr(uvicorn, "run", lambda app, **kw: seen.update(app=app, **kw))
    assert hosted.main() == 0
    assert seen["port"] == 12345
    assert seen["host"] == "0.0.0.0"  # noqa: S104 - what the platform routes to
    assert seen["workers"] == 1
    assert seen["app"] == "the-app"  # one app instance, built once
    assert seen["bootstrap"] is True
    assert seen["worker"].is_set()  # stopped when uvicorn returns


# ----- portal: SPA fallback and security headers -----


@pytest.fixture(scope="module")
def portal_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    d = tmp_path_factory.mktemp("portal")
    (d / "index.html").write_text("<!doctype html><title>portal</title>")
    (d / "assets").mkdir()
    (d / "assets" / "app-1234.js").write_text("console.log(1)")
    (d / "assets" / "app-1234.js.map").write_text("{}")
    (d / "brand").mkdir()
    (d / "brand" / "logo.svg").write_text("<svg/>")
    return d


@pytest.fixture(scope="module")
def portal_client(migrated: Settings, portal_dir: Path) -> TestClient:
    s = migrated.model_copy(
        update={"serve_portal_dir": portal_dir, "public_base_url": "https://skills.example.invalid"}
    )
    return TestClient(create_app(s))


def _is_index(r: Any) -> bool:
    return r.status_code == 200 and "<title>portal</title>" in r.text


@pytest.mark.parametrize(
    "path", ["/", "/runs", "/insights/business", "/admin/users/x", "/index.html"]
)
def test_portal_routes_get_the_spa(portal_client: TestClient, path: str) -> None:
    assert _is_index(portal_client.get(path))


def test_msal_callback_is_still_a_portal_route(portal_client: TestClient) -> None:
    assert _is_index(portal_client.get("/auth/callback"))


@pytest.mark.parametrize(
    "path",
    [
        "/v1",
        "/v1/nope",
        "/v1/runs/x/y/z",
        "/auth",
        "/auth/github/nope",
        "/auth/logout/x",
        "/otel",
        "/otel/v1/nope",
        "/metrics",
        "/metrics/x",
        "/readyz/x",
        "/healthz/x",
        "/assets/missing.js",
        "/assets/app-1234.js.map",
        "/.env",
        "/x/.git/config",
        "/mockServiceWorker.js",
    ],
)
def test_spa_fallback_never_shadows_api_or_probe_paths(
    portal_client: TestClient, path: str
) -> None:
    r = portal_client.get(path)
    assert not _is_index(r)
    assert r.status_code in (401, 404, 405)


def test_api_routes_still_answer_as_api(portal_client: TestClient) -> None:
    assert portal_client.get("/v1/health").json()["status"] == "ok"
    assert portal_client.get("/healthz").json() == {"status": "ok"}
    r = portal_client.get("/readyz")
    assert r.headers["content-type"].startswith("application/json")
    assert r.json()["status"] in ("ok", "fail")
    assert "checks" not in r.json()  # detail stays internal
    me = portal_client.get("/v1/me")
    assert me.status_code == 401
    assert me.headers["content-type"].startswith("application/problem+json")
    assert portal_client.post("/somewhere", json={}).status_code in (404, 405)


def test_assets_are_served_with_long_cache(portal_client: TestClient) -> None:
    r = portal_client.get("/assets/app-1234.js")
    assert r.status_code == 200
    assert r.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert portal_client.get("/brand/logo.svg").headers["cache-control"] == "public, max-age=3600"
    assert portal_client.get("/").headers["cache-control"] == "no-cache"


def test_portal_security_headers_match_nginx(portal_client: TestClient) -> None:
    nginx = (ROOT / "portal" / "nginx.conf").read_text()
    r = portal_client.get("/runs")
    for header in (
        "X-Content-Type-Options",
        "Referrer-Policy",
        "Permissions-Policy",
        "X-Frame-Options",
        "Cross-Origin-Opener-Policy",
        "Cross-Origin-Resource-Policy",
    ):
        assert f'add_header {header} "{r.headers[header]}" always;' in nginx, header
    # This app is in Entra mode, so its CSP is exactly the nginx one.
    assert f'add_header Content-Security-Policy "{r.headers["content-security-policy"]}"' in nginx
    assert r.headers["strict-transport-security"] == "max-age=31536000"
    api = portal_client.get("/v1/health")
    assert api.headers["x-content-type-options"] == "nosniff"
    assert "content-security-policy" not in api.headers
    assert api.headers["strict-transport-security"] == "max-age=31536000"


def test_github_mode_csp_drops_the_entra_host() -> None:
    csp = portal_csp("github")
    assert "microsoftonline" not in csp
    assert "connect-src 'self';" in csp
    assert "frame-ancestors 'none'" in csp
    assert "login.microsoftonline.com" in portal_csp("entra")


def test_is_portal_path() -> None:
    assert is_portal_path("/")
    assert is_portal_path("/v1beta")  # only the /v1 segment is reserved
    assert not is_portal_path("/v1")
    assert not is_portal_path("/auth/github/login")


def test_no_portal_headers_when_portal_not_served(client: TestClient) -> None:
    r = client.get("/v1/health")
    assert "content-security-policy" not in r.headers
    assert "strict-transport-security" not in r.headers
    assert client.get("/runs").status_code == 404


# ----- worker leader lock -----


def test_leader_lock_is_taken_once(migrated: Settings) -> None:
    from app.worker import try_lead

    eng = create_engine(migrated.database_url("app"), poolclass=NullPool)  # closed = session ends
    try:
        with eng.connect() as a, eng.connect() as b:
            assert try_lead(a) is True
            assert try_lead(b) is False
            assert try_lead(b) is False
        with eng.connect() as c:  # a's session ended, so the lock is free again
            assert try_lead(c) is True
    finally:
        eng.dispose()


def test_two_schedulers_only_one_runs_jobs(migrated: Settings) -> None:
    from app.worker import run_loop

    ticks = {"a": 0, "b": 0}
    stop = threading.Event()

    def make(name: str) -> Any:
        def tick(s: Settings, sched: Any, now: float) -> int:
            ticks[name] += 1
            return 1

        return tick

    threads = [
        threading.Thread(target=run_loop, args=(migrated, stop, make(n), 0.05), daemon=True)
        for n in ("a", "b")
    ]
    for th in threads:
        th.start()
    time.sleep(2.5)
    stop.set()
    for th in threads:
        th.join(timeout=10)
    assert sorted(v > 0 for v in ticks.values()) == [False, True], ticks


# ----- bootstrap as a Neon-like owner (non-superuser, CREATEROLE), passwords checked -----


@pytest.fixture(scope="module")
def neonlike() -> Iterator[PG]:
    if os.environ.get("INSIGHTS_TEST_PG_PORT") or not (PG_BIN / "initdb").exists():
        pytest.skip("needs local PostgreSQL 16 binaries for a second, password-checking cluster")
    with pg_cluster(auth_host="scram-sha-256") as cluster:
        su = create_engine(
            f"postgresql+psycopg://postgres@/postgres?host={cluster.sock}&port={cluster.port}",
            isolation_level="AUTOCOMMIT",
        )
        with su.connect() as c:
            c.execute(text("SET password_encryption = 'scram-sha-256'"))
            c.execute(
                text(
                    "CREATE ROLE neondb_owner LOGIN CREATEROLE CREATEDB NOSUPERUSER "
                    "PASSWORD 'owner-pw-for-tests-only'"
                )
            )
            c.execute(text("CREATE DATABASE neondb OWNER neondb_owner"))
        su.dispose()
        yield cluster


@pytest.fixture(scope="module")
def catalogue_tree(tmp_path_factory: pytest.TempPathFactory) -> Path:
    d = tmp_path_factory.mktemp("catalogue")
    for part in ("plugins", "pods", "tsl"):
        (d / part).symlink_to(ROOT / part)
    (d / ".release-tag").write_text("v0.1.0 " + "a" * 40 + "\n")
    return d


def test_bootstrap_as_non_superuser_owner(neonlike: PG, catalogue_tree: Path) -> None:
    from app.db import dispose_all, engine

    url = (
        f"postgresql://neondb_owner:owner-pw-for-tests-only@127.0.0.1:{neonlike.port}/neondb"
        "?sslmode=disable"
    )
    s = Settings(
        env="test",
        database_url_value=SecretStr(url),
        db_role_password_key=SecretStr(ROLE_KEY),
        data_key_value=SecretStr(_b64(32)),
        pseudonym_pepper_value=SecretStr(_b64(32)),
        schemas_dir=ROOT / "schemas",
        otel_allowlist_file=SERVICE / "tests" / "fixtures" / "otel_allowlist.yaml",
        catalogue_source_dir=catalogue_tree,
        github_webhook_hooks=("987654:example-org/companion",),
        github_webhook_secret=SecretStr("w" * 32),
        database_pool_size=2,
    )
    try:
        with create_engine(s.migrations_url()).connect() as c:
            assert (
                c.execute(
                    text("SELECT rolsuper FROM pg_roles WHERE rolname = current_user")
                ).scalar()
                is False
            )
        hosted.bootstrap(s)
        hosted.bootstrap(s)  # idempotent: a restart runs it again

        with engine("app", s).connect() as c:
            assert c.execute(text("SELECT current_user")).scalar() == "insights_app"
            assert c.execute(text("SELECT count(*) FROM catalogue_releases")).scalar() == 1
            assert c.execute(text("SELECT count(*) FROM skills")).scalar_one() > 0
        with engine("read", s).connect() as c:
            assert c.execute(text("SELECT current_user")).scalar() == "insights_read"
            with pytest.raises(Exception, match="permission denied"):
                c.execute(text("SELECT secret_enc FROM github_hooks"))
        with engine("reveal", s).connect() as c:
            assert c.execute(text("SELECT current_user")).scalar() == "insights_reveal"
        with engine("owner", s).connect() as c:
            row = c.execute(
                text("SELECT target, revoked_at FROM github_hooks WHERE hook_id = 987654")
            ).one()
            assert row == ("example-org/companion", None)
            n = c.execute(text("SELECT count(*) FROM pg_inherits")).scalar()
            assert n and n >= 6  # current + 2 months ahead, for two tables

        wrong = hosted_database_url(url, ("insights_app", "not-the-password"))
        with pytest.raises(Exception, match="password authentication failed"):
            create_engine(wrong).connect()

        from app.obs.probe import readiness

        ok, checks = readiness(s, None)
        assert checks["db"] == "ok" and checks["migration"] == "ok" and checks["secrets"] == "ok"
        assert "jwks" in checks  # provider entra here; GitHub mode skips it
        gh = s.model_copy(update={"identity_provider": "github", "github_client_id": "Iv1.x"})
        ok, checks = readiness(gh, None)
        assert ok, checks
    finally:
        dispose_all()
