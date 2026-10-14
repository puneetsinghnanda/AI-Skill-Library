"""Test fixtures: a real PostgreSQL 16 cluster, a locally generated Entra signing key, the app.

The cluster is created with ``initdb`` and ``pg_ctl`` from /usr/lib/postgresql/16/bin on a random
port in a temporary directory. In CI an empty PostgreSQL 16 service container can be used instead:
set ``INSIGHTS_TEST_PG_PORT`` (and optionally ``INSIGHTS_TEST_PG_HOST``) to a server that trusts the
``postgres`` superuser on that address and holds no other data. Authentication in tests uses ordinary RS256 tokens signed by a key
generated here and published through a JWKS file (``ENTRA_JWKS_FILE``): the service validates them
exactly like Entra tokens. There is no bypass.
"""

from __future__ import annotations

import base64
import json
import os
import random
import shutil
import socket
import subprocess
import tempfile
import time
import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from jwt.algorithms import RSAAlgorithm
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.config import Settings
from app.crypto import ulid

PG_BIN = Path(os.environ.get("PG_BIN", "/usr/lib/postgresql/16/bin"))
SERVICE = Path(__file__).resolve().parent.parent
ROOT = SERVICE.parent.parent
# Scratch space for generated config files. Use the system temp dir (writable everywhere,
# including dev containers where the repo's parent folder is root-owned); override with
# INSIGHTS_TEST_TMP if needed.
TMP_BASE = Path(os.environ.get("INSIGHTS_TEST_TMP") or tempfile.gettempdir()) / "tmp-insights"
TENANT = "11111111-2222-4333-8444-555555555555"
AUDIENCE = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"
TSL_CLIENT = "0f0f0f0f-1111-4222-8333-444444444444"
PORTAL_CLIENT = "0e0e0e0e-1111-4222-8333-444444444444"
PASSWORDS = {
    "owner": "owner-test-pw",
    "app": "app-test-pw",
    "read": "read-test-pw",
    "reveal": "reveal-test-pw",
}


def skill_version(skill_id: str) -> str:
    """Current version of a plugin skill, read from its skill.yaml (tests must not pin versions)."""
    import yaml

    data = yaml.safe_load(
        (ROOT / "plugins" / "truminds" / "skills" / skill_id / "skill.yaml").read_text()
    )
    return str(data["version"])


def next_patch(version: str) -> str:
    major, minor, patch = version.split(".")
    return f"{major}.{minor}.{int(patch) + 1}"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _as_postgres(cmd: list[str]) -> list[str]:
    if os.geteuid() == 0:
        return ["runuser", "-u", "postgres", "--", *cmd]
    return cmd


@dataclass
class PG:
    port: int
    data: Path | None
    sock: Path | None
    host: str = "127.0.0.1"

    def url(self, user: str = "postgres", password: str | None = None, db: str = "postgres") -> str:
        auth = f"{user}:{password}" if password else user
        return f"postgresql+psycopg://{auth}@{self.host}:{self.port}/{db}?sslmode=disable"


@pytest.fixture(scope="session")
def pg() -> Iterator[PG]:
    external = os.environ.get("INSIGHTS_TEST_PG_PORT")
    if external:  # CI service container (empty, throwaway); see the module docstring
        yield PG(int(external), None, None, os.environ.get("INSIGHTS_TEST_PG_HOST", "127.0.0.1"))
        return
    if not (PG_BIN / "initdb").exists():
        pytest.skip("PostgreSQL 16 binaries not found")
    # The cluster lives in the system temp directory: when tests run as root, initdb must run as the
    # postgres user, which cannot traverse a private scratch tree.
    work = Path(tempfile.mkdtemp(prefix="insights-pg-"))
    data, sock = work / "data", work / "sock"
    sock.mkdir()
    if os.geteuid() == 0:
        shutil.chown(work, "postgres")
        shutil.chown(sock, "postgres")
    subprocess.run(
        _as_postgres(
            [
                str(PG_BIN / "initdb"),
                "-D",
                str(data),
                "-U",
                "postgres",
                "--auth=trust",
                "-E",
                "UTF8",
                "--no-instructions",
            ]
        ),
        check=True,
        capture_output=True,
    )
    port = _free_port()
    opts = f"-p {port} -k {sock} -c listen_addresses=127.0.0.1 -c fsync=off -c max_connections=200 -c timezone=UTC"
    subprocess.run(
        _as_postgres(
            [
                str(PG_BIN / "pg_ctl"),
                "-D",
                str(data),
                "-o",
                opts,
                "-l",
                str(work / "log"),
                "-w",
                "start",
            ]
        ),
        check=True,
        capture_output=True,
    )
    try:
        yield PG(port, data, sock)
    finally:
        subprocess.run(
            _as_postgres([str(PG_BIN / "pg_ctl"), "-D", str(data), "-m", "immediate", "stop"]),
            capture_output=True,
        )
        shutil.rmtree(work, ignore_errors=True)


@dataclass
class Keys:
    private: rsa.RSAPrivateKey
    kid: str
    other: rsa.RSAPrivateKey


@pytest.fixture(scope="session")
def signing() -> Keys:
    return Keys(
        rsa.generate_private_key(public_exponent=65537, key_size=2048),
        "test-kid-1",
        rsa.generate_private_key(public_exponent=65537, key_size=2048),
    )


@pytest.fixture(scope="session")
def settings(pg: PG, signing: Keys) -> Settings:
    TMP_BASE.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="cfg-", dir=TMP_BASE))
    files: dict[str, Path] = {}
    for role, pw in PASSWORDS.items():
        files[role] = work / f"db_{role}"
        files[role].write_text(pw)
    (work / "pepper").write_text(base64.b64encode(os.urandom(32)).decode())
    (work / "data_key").write_text(base64.b64encode(os.urandom(32)).decode())
    jwk = json.loads(RSAAlgorithm.to_jwk(signing.private.public_key()))
    jwk |= {"kid": signing.kid, "use": "sig", "alg": "RS256"}
    (work / "jwks.json").write_text(json.dumps({"keys": [jwk]}))
    # bootstrap: owner role and database (what deploy/compose/postgres-init does in production)
    su = create_engine(pg.url(), isolation_level="AUTOCOMMIT")
    with su.connect() as c:
        c.execute(
            text(f"CREATE ROLE insights_owner LOGIN CREATEROLE PASSWORD '{PASSWORDS['owner']}'")
        )
        c.execute(text("CREATE DATABASE insights OWNER insights_owner"))
    su.dispose()
    s = Settings(
        env="test",
        database_host=pg.host,
        database_port=pg.port,
        database_name="insights",
        database_sslmode="disable",
        database_owner_password_file=files["owner"],
        database_app_password_file=files["app"],
        database_read_password_file=files["read"],
        database_reveal_password_file=files["reveal"],
        pseudonym_pepper_file=work / "pepper",
        data_key_file=work / "data_key",
        entra_tenant_id=TENANT,
        entra_api_audience=AUDIENCE,
        entra_tsl_client_id=TSL_CLIENT,
        entra_portal_client_id=PORTAL_CLIENT,
        entra_jwks_file=work / "jwks.json",
        schemas_dir=ROOT / "schemas",
        otel_allowlist_file=SERVICE / "tests" / "fixtures" / "otel_allowlist.yaml",
        marketplace_repo="example-org/skill-library",
        view_refresh_interval_s=300,
    )
    return s


@pytest.fixture(scope="session")
def migrated(pg: PG, settings: Settings) -> Settings:
    from alembic.config import Config

    from alembic import command

    cfg = Config(str(SERVICE / "alembic.ini"))
    cfg.set_main_option("script_location", str(SERVICE / "alembic"))
    cfg.attributes["url"] = settings.database_url("owner")
    command.upgrade(cfg, "head")
    su = create_engine(pg.url(db="insights"), isolation_level="AUTOCOMMIT")
    with su.connect() as c:
        for role in ("app", "read", "reveal"):
            c.execute(text(f"ALTER ROLE insights_{role} LOGIN PASSWORD '{PASSWORDS[role]}'"))
    su.dispose()
    from app.jobs import partitions

    partitions.run(settings, role="owner")
    return settings


@pytest.fixture(scope="session")
def owner_db(migrated: Settings) -> Iterator[Engine]:
    eng = create_engine(migrated.database_url("owner"))
    yield eng
    eng.dispose()


@pytest.fixture(scope="session")
def catalogue(migrated: Settings) -> Any:
    from app.catalogue.sync import sync

    return sync(migrated, ROOT, "v0.1.0", "0" * 40)


@pytest.fixture(scope="session")
def app(migrated: Settings, catalogue: Any) -> Any:
    from app.main import create_app

    return create_app(migrated)


@pytest.fixture()
def client(app: Any) -> TestClient:
    app.state.rate_limiter._b.clear()
    return TestClient(app)


TokenFactory = Callable[..., str]


@pytest.fixture(scope="session")
def token(signing: Keys) -> TokenFactory:
    def make(
        oid: str,
        roles: list[str] | None = None,
        client: str = "tsl",
        scp: str | None = None,
        exp_delta: int = 3600,
        aud: str = AUDIENCE,
        tid: str = TENANT,
        key: Any = None,
        name: str | None = None,
        alg: str = "RS256",
        kid: str | None = None,
    ) -> str:
        now = int(time.time())
        claims: dict[str, Any] = {
            "iss": f"https://login.microsoftonline.com/{tid}/v2.0",
            "aud": aud,
            "tid": tid,
            "oid": oid,
            "azp": TSL_CLIENT
            if client == "tsl"
            else (PORTAL_CLIENT if client == "portal" else client),
            "scp": scp or ("Events.Write" if client == "tsl" else "Portal.Read Portal.Write"),
            "roles": roles if roles is not None else ["Engineer"],
            "iat": now - 10,
            "nbf": now - 10,
            "exp": now + exp_delta,
        }
        if name:
            claims["name"] = name
        out: str = jwt.encode(
            claims, key or signing.private, algorithm=alg, headers={"kid": kid or signing.kid}
        )
        return out

    return make


@dataclass
class Person:
    oid: str
    roles: list[str]
    name: str
    pseudonym: str = ""
    user_id: str = ""


def bearer(tok: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture(scope="session")
def people(app: Any, token: TokenFactory) -> dict[str, Person]:
    """Invented users, created on first sight through GET /v1/me."""
    c = TestClient(app)
    ps = {
        "admin": Person(str(uuid.uuid4()), ["Admin", "TechLead"], "Avery Admin"),
        "admin2": Person(str(uuid.uuid4()), ["Admin"], "Blake Admin"),
        "lead": Person(str(uuid.uuid4()), ["TechLead"], "Casey Lead"),
        "eng": Person(str(uuid.uuid4()), ["Engineer"], "Devon Engineer"),
        "eng2": Person(str(uuid.uuid4()), ["Engineer"], "Emery Engineer"),
        "biz": Person(str(uuid.uuid4()), ["Business"], "Finley Business"),
        "owner": Person(str(uuid.uuid4()), ["Engineer"], "Gray Owner"),
        "englead": Person(str(uuid.uuid4()), ["TechLead"], "Harper EngLead"),
    }
    for p in ps.values():
        r = c.get("/v1/me", headers=bearer(token(p.oid, p.roles, client="portal", name=p.name)))
        assert r.status_code == 200, r.text
        p.pseudonym = r.json()["pseudonym"]
    return ps


@dataclass
class World:
    project: str
    system: str
    system_id: str
    other_system: str
    other_system_id: str
    repo: str


def rand_code(prefix: str, n: int = 4) -> str:
    return prefix + "".join(random.choice("ABCDEFGHJKMNPQRSTVWXYZ0123456789") for _ in range(n))


@pytest.fixture(scope="session")
def world(app: Any, token: TokenFactory, people: dict[str, Person], owner_db: Engine) -> World:
    """Client, project, two systems and role grants, created through the admin API."""
    c = TestClient(app)
    adm = bearer(token(people["admin"].oid, people["admin"].roles, client="portal"))
    client_code, project, sys_a, sys_b = "CL-DEMO", "PRJ-DEMO", "SYS-ORD", "SYS-TKT"
    assert (
        c.post(
            "/v1/admin/clients",
            json={
                "code": client_code,
                "display_name": "Northwind Quillfeather",
                "aliases": ["Northwind"],
            },
            headers=adm,
        ).status_code
        == 201
    )
    r = c.post(
        f"/v1/admin/clients/{client_code}/consent",
        headers=adm,
        json={
            "consent_ref": "CONSENT-0001",
            "scope": ["code_processing", "companion_storage", "product_prs", "ci_webhook"],
        },
    )
    assert r.status_code == 200, r.text
    assert (
        c.post(
            "/v1/admin/projects", json={"client": client_code, "code": project}, headers=adm
        ).status_code
        == 201
    )
    for code, repo in ((sys_a, "orders-api"), (sys_b, "tickets-web")):
        r = c.post(
            "/v1/admin/systems",
            headers=adm,
            json={
                "project": project,
                "code": code,
                "domain": "digital",
                "companion_repo": f"example-org/cl-demo-{code.lower()}-companion",
                "product_repos": [
                    {"name": repo, "github_full_name": f"example-org/{repo}", "kind": "product"}
                ],
            },
        )
        assert r.status_code == 201, r.text
    grants = [
        ("eng", "engineer", "system", sys_a),
        ("eng2", "engineer", "system", sys_b),
        ("lead", "tech_lead", "system", sys_a),
        ("lead", "engineer", "system", sys_a),
        ("owner", "skill_owner", "skill", "design"),
        ("englead", "eng_lead", "project", project),
    ]
    for who, role, st, scope in grants:
        r = c.post(
            "/v1/admin/role-grants",
            headers=adm,
            json={"user": people[who].pseudonym, "role": role, "scope_type": st, "scope": scope},
        )
        assert r.status_code == 201, r.text
    with owner_db.connect() as conn:
        ids: dict[str, str] = dict(conn.execute(text("SELECT code, id::text FROM systems")).all())
        for p in people.values():
            p.user_id = conn.execute(
                text("SELECT id::text FROM users WHERE pseudonym = :p"), {"p": p.pseudonym}
            ).scalar_one()
    return World(project, sys_a, ids[sys_a], sys_b, ids[sys_b], "orders-api")


# ----------------------------------------------------------------------------- event builders
def now_iso(delta_s: float = 0) -> str:
    return (datetime.now(UTC) + timedelta(seconds=delta_s)).strftime("%Y-%m-%dT%H:%M:%SZ")


def event(
    type_: str,
    body: dict[str, Any],
    run_id: str | None = None,
    occurred: str | None = None,
    version: int = 1,
) -> dict[str, Any]:
    ev: dict[str, Any] = {
        "event_id": ulid("evt"),
        "type": type_,
        "schema_version": version,
        "occurred_at": occurred or now_iso(),
        "body": body,
    }
    if run_id:
        ev["run_id"] = run_id
    return ev


def run_started(
    system: str,
    workflow: str = "brownfield-change",
    ticket: str = "T-1",
    pod: str | None = None,
    session: str | None = None,
) -> dict[str, Any]:
    b: dict[str, Any] = {
        "workflow": workflow,
        "workflow_version": "1.3.0",
        "ticket_ref": ticket,
        "system": system,
        "plugin_version": "0.1.0",
        "pinned_skills": {"design": skill_version("design")},
    }
    if pod:
        b["pod"] = pod
    if session:
        b["session_id"] = session
    return b


def step_decided(
    step: str,
    skill: str,
    version: str,
    attempt: int,
    outcome: str,
    band: str | None,
    key_id: str,
    seq: int,
    reasons: list[str] | None = None,
    session: str | None = None,
) -> dict[str, Any]:
    b: dict[str, Any] = {
        "step": step,
        "skill": skill,
        "skill_version": version,
        "attempt": attempt,
        "outcome": outcome,
        "band": band,
        "signals": {
            "S1": 0.9,
            "S2": 1.0,
            "S3": 4.0,
            "S4": 0,
            "S5": "fresh",
            "S6": {"lines": 10, "files": 1, "sensitive": False},
        },
        "caps": [],
        "gate_failures": [],
        "findings_count": {"blocker": 0, "major": 0, "minor": 1},
        "duration_ms": 1200,
        "verification_sha256": os.urandom(32).hex(),
        "seq": seq,
        "reasons": reasons or [],
        "key_id": key_id,
        "decided_by": "tsl@0.1.0",
    }
    if session:
        b["session_id"] = session
    return b


# ----------------------------------------------------------------------------- helpers
def b64url(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def key_registration(
    oid: str,
    key_id: str | None = None,
    device_id: str | None = None,
    iat: str | None = None,
    priv: Any = None,
    sub: str | None = None,
) -> tuple[dict[str, Any], Any]:
    import rfc8785
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

    priv = priv or Ed25519PrivateKey.generate()
    pub = b64url(priv.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw))
    key_id = key_id or ulid("key")
    device_id = device_id or ulid("dev")
    iat = iat or now_iso()
    proof = {
        "key_id": key_id,
        "public_key": pub,
        "device_id": device_id,
        "sub": sub or oid,
        "iat": iat,
    }
    body = {
        "key_id": key_id,
        "algorithm": "Ed25519",
        "public_key": pub,
        "device_id": device_id,
        "device_label": "laptop-test",
        "iat": iat,
        "proof": b64url(priv.sign(rfc8785.dumps(proof))),
    }
    return body, priv


@pytest.fixture(scope="session")
def keys_of(app: Any, token: TokenFactory, people: dict[str, Person]) -> dict[str, str]:
    """One registered signing key per engineer-type person."""
    c = TestClient(app)
    out = {}
    for who in ("eng", "eng2", "lead", "owner"):
        p = people[who]
        body, _ = key_registration(p.oid)
        r = c.post("/v1/keys", json=body, headers=bearer(token(p.oid, p.roles)))
        assert r.status_code == 201, r.text
        out[who] = body["key_id"]
    return out


@pytest.fixture(scope="session")
def ci_token(migrated: Settings) -> str:
    from app.auth import ingest_tokens
    from app.db import tx

    with tx("app", migrated) as conn:
        _id, tok = ingest_tokens.create(conn, "ci", "example-org")
    return tok


@pytest.fixture(scope="session")
def otel_token(migrated: Settings) -> str:
    from app.auth import ingest_tokens
    from app.db import tx

    with tx("app", migrated) as conn:
        _id, tok = ingest_tokens.create(conn, "otel", "managed-settings")
    return tok


def post(c: TestClient, tok: str, events: list[Any], strict: bool = False) -> dict[str, Any]:
    r = c.post("/v1/events", json={"events": events}, headers=bearer(tok))
    assert r.status_code == 202, r.text
    body: dict[str, Any] = r.json()
    if strict:
        assert body["rejected"] == [], body["rejected"]
    return body


def project(s: Settings, refresh: bool = False) -> None:
    from app.jobs import refresh_views
    from app.projector.loop import project_all

    project_all(s)
    if refresh:
        refresh_views.run(s)


def new_run() -> str:
    return ulid("run")
