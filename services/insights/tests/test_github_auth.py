"""Interim GitHub identity provider (ADR 0006, SDD-07 §1.4, SDD-09 §3.4.1).

A second app runs on the same test database with ``IDENTITY_PROVIDER=github``. GitHub is an
``httpx.MockTransport``: ``GET /user`` and ``POST /login/oauth/access_token``. No test talks to
GitHub. The Entra path is covered by every other test module, unchanged.
"""

from __future__ import annotations

import base64
import hashlib
import random
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.config import Settings
from tests.conftest import Person, TokenFactory, World, bearer

BASE = "http://testserver"
CSRF = {"X-Requested-With": "truminds-portal", "Origin": BASE}


@dataclass
class FakeGitHub:
    users: dict[str, dict[str, Any]] = field(default_factory=dict)  # token -> /user body
    codes: dict[str, str] = field(default_factory=dict)  # code -> token
    user_calls: int = 0
    exchanges: list[dict[str, str]] = field(default_factory=list)
    down: bool = False

    def add(self, login: str, name: str | None = None) -> tuple[str, int]:
        uid = random.randint(10_000, 99_999_999)
        tok = f"gho_{login}_{uid}"
        self.users[tok] = {"id": uid, "login": login, "name": name}
        return tok, uid

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if self.down:
            raise httpx.ConnectError("down", request=request)
        if request.url.path == "/user":
            self.user_calls += 1
            tok = request.headers.get("authorization", "").removeprefix("Bearer ")
            if tok in self.users:
                return httpx.Response(200, json=self.users[tok])
            return httpx.Response(401, json={"message": "Bad credentials"})
        if request.url.path == "/login/oauth/access_token":
            form = {k: v[0] for k, v in parse_qs(request.content.decode()).items()}
            self.exchanges.append(form)
            tok = self.codes.get(form.get("code", ""))
            if tok and form.get("client_secret") == "test-client-secret":
                return httpx.Response(200, json={"access_token": tok, "token_type": "bearer"})
            return httpx.Response(200, json={"error": "bad_verification_code"})
        return httpx.Response(404)


@pytest.fixture(scope="module")
def gh() -> FakeGitHub:
    return FakeGitHub()


@pytest.fixture(scope="module")
def gh_settings(migrated: Settings) -> Settings:
    return Settings(
        **{
            **migrated.model_dump(),
            "identity_provider": "github",
            "github_client_id": "Iv1.testclient",
            "github_client_secret": "test-client-secret",
            "github_oauth_url": "https://github.example",
            "github_api_url": "https://api.github.example",
            "bootstrap_admin_github_logins": "Boot-Admin",
            "public_base_url": BASE,
            "env": "test",
        }
    )


@pytest.fixture(scope="module")
def gh_app(gh_settings: Settings, catalogue: Any, gh: FakeGitHub) -> Any:
    from app.main import create_app

    app = create_app(gh_settings)
    app.state.github.transport = httpx.MockTransport(gh)
    app.state.github_flow.transport = httpx.MockTransport(gh)
    return app


@pytest.fixture()
def gc(gh_app: Any) -> Iterator[TestClient]:
    gh_app.state.rate_limiter._b.clear()
    with TestClient(gh_app, base_url=BASE) as c:
        yield c


def _admin_token(gh: FakeGitHub) -> str:
    """The one GitHub user named boot-admin (listed in BOOTSTRAP_ADMIN_GITHUB_LOGINS)."""
    for tok, u in gh.users.items():
        if u["login"] == "boot-admin":
            return tok
    return gh.add("boot-admin", "Boot Admin")[0]


def _sign_in(c: TestClient, gh: FakeGitHub, tok: str, return_to: str = "/skills") -> None:
    r = c.get(f"/auth/github/login?return_to={return_to}", follow_redirects=False)
    assert r.status_code == 302
    q = parse_qs(urlsplit(r.headers["location"]).query)
    code = f"code-{random.randint(0, 10**9)}"
    gh.codes[code] = tok
    r = c.get(f"/auth/github/callback?code={code}&state={q['state'][0]}", follow_redirects=False)
    assert r.status_code == 302 and r.headers["location"] == return_to, r.text


# ----------------------------------------------------------------------------- configuration
def test_github_refused_in_prod_and_needs_client_id(gh_settings: Settings) -> None:
    from app.main import create_app

    with pytest.raises(RuntimeError, match="test phase only"):
        create_app(Settings(**{**gh_settings.model_dump(), "env": "prod"}))
    with pytest.raises(RuntimeError, match="GITHUB_CLIENT_ID"):
        create_app(Settings(**{**gh_settings.model_dump(), "github_client_id": ""}))


def test_entra_app_has_no_github_routes(client: TestClient) -> None:
    assert client.get("/auth/github/login", follow_redirects=False).status_code == 404
    assert client.post("/auth/logout").status_code == 404


def test_entra_jwt_is_not_accepted_by_github_app(
    gc: TestClient, token: TokenFactory, people: dict[str, Person]
) -> None:
    p = people["eng"]
    r = gc.get("/v1/me", headers=bearer(token(p.oid, p.roles, client="portal")))
    assert r.status_code == 401


# ----------------------------------------------------------------------------- token validation
def test_valid_token_creates_user_but_no_role_means_403(
    gc: TestClient, gh: FakeGitHub, owner_db: Engine
) -> None:
    tok, _ = gh.add("new-tester", "New Tester")
    r = gc.get("/v1/me", headers=bearer(tok))
    assert r.status_code == 403 and r.json()["code"] == "E-AUTH-08"
    assert "@new-tester" in r.json()["detail"] and "eng-" in r.json()["detail"]
    assert tok not in r.text
    with owner_db.connect() as conn:
        row = conn.execute(
            text("SELECT github_login, app_roles FROM users WHERE github_login = 'new-tester'")
        ).one()
    assert row.github_login == "new-tester" and list(row.app_roles) == []


def test_invalid_token_rejected(gc: TestClient) -> None:
    r = gc.get("/v1/me", headers=bearer("gho_not_a_real_token"))
    assert r.status_code == 401 and r.json()["code"] == "E-ING-07"
    r = gc.get("/v1/status", headers=bearer("gho_not_a_real_token"))
    assert r.status_code == 401 and r.json()["code"] == "E-API-02"
    r = gc.get("/v1/status")
    assert r.status_code == 401


def test_github_unreachable_is_503(gc: TestClient, gh: FakeGitHub) -> None:
    gh.down = True
    try:
        r = gc.get("/v1/me", headers=bearer("gho_unseen_token_while_down"))
    finally:
        gh.down = False
    assert r.status_code == 503 and r.json()["code"] == "E-AUTH-10"


def test_token_cache_five_minutes_keyed_by_sha256(
    gc: TestClient, gh_app: Any, gh: FakeGitHub
) -> None:
    tok, _ = gh.add("cache-tester")
    v = gh_app.state.github
    before = gh.user_calls
    gc.get("/v1/me", headers=bearer(tok))
    gc.get("/v1/me", headers=bearer(tok))
    assert gh.user_calls == before + 1
    assert tok not in v._cache and hashlib.sha256(tok.encode()).hexdigest() in v._cache
    real = v.clock
    t0 = real()
    v.clock = lambda: t0 + 301
    try:
        gc.get("/v1/me", headers=bearer(tok))
    finally:
        v.clock = real
    assert gh.user_calls == before + 2


# ----------------------------------------------------------------------------- roles
def test_bootstrap_admin_then_role_grants_from_the_portal(
    gc: TestClient, gh: FakeGitHub, owner_db: Engine, world: World
) -> None:
    admin_tok = _admin_token(gh)  # setting is "Boot-Admin": the match is case-insensitive
    r = gc.get("/v1/me", headers=bearer(admin_tok))
    assert r.status_code == 200, r.text
    me = r.json()
    assert {"role": "admin", "scope": "org"} in me["grants"]
    assert me["oid"].startswith("github:") and "Admin" in me["data"]["app_roles"]
    with owner_db.connect() as conn:
        n = conn.execute(
            text(
                "SELECT count(*) FROM audit_log WHERE action = 'bootstrap_admin_grant' "
                "AND after->>'github_login' = 'boot-admin'"
            )
        ).scalar_one()
    assert n == 2  # viewer and admin, once each
    gc.get("/v1/me", headers=bearer(admin_tok))  # idempotent on later sign-ins
    with owner_db.connect() as conn:
        n2 = conn.execute(
            text("SELECT count(*) FROM audit_log WHERE action = 'bootstrap_admin_grant'")
        ).scalar_one()
    assert n2 == n

    # A tester signs in once (403, row created), then the admin grants roles in the portal.
    tester_tok, _ = gh.add("tester-two")
    r = gc.get("/v1/me", headers=bearer(tester_tok))
    assert r.status_code == 403
    m = re.search(r"\b(eng-[0-9a-f]{4,8})\b", r.json()["detail"])
    assert m is not None
    pseudonym = m.group(1)
    _sign_in(gc, gh, admin_tok, "/admin/users")
    users = gc.get("/v1/admin/users?include=names").json()["data"]["items"]
    assert any(u["display_name"] == "@tester-two" for u in users)  # admin can find the tester
    for role, st, scope in (
        ("viewer", "org", None),
        ("engineer", "system", world.system),
        ("tech_lead", "system", world.system),
    ):
        r = gc.post(
            "/v1/admin/role-grants",
            headers=CSRF,
            json={"user": pseudonym, "role": role, "scope_type": st, "scope": scope},
        )
        assert r.status_code == 201, r.text
    gc.cookies.clear()
    r = gc.get("/v1/me", headers=bearer(tester_tok))
    assert r.status_code == 200, r.text
    me = r.json()
    assert set(me["data"]["app_roles"]) == {"Business", "Engineer", "TechLead"}
    assert {"role": "engineer", "scope": f"system:{world.system}"} in me["grants"]
    # the tsl route for its own system now answers
    r = gc.get(f"/v1/systems/{world.system}", headers=bearer(tester_tok))
    assert r.status_code == 200, r.text


def test_bearer_token_cannot_use_portal_write_routes(gc: TestClient, gh: FakeGitHub) -> None:
    admin_tok = _admin_token(gh)
    r = gc.post(
        "/v1/admin/projects", headers=bearer(admin_tok), json={"client": "CL-X", "code": "PRJ-X"}
    )
    assert r.status_code == 401


# ----------------------------------------------------------------------------- session cookie
def test_cookie_flow_state_pkce_and_cookie_flags(gc: TestClient, gh: FakeGitHub) -> None:
    tok, _ = gh.add("boot-admin-cookie")
    r = gc.get("/auth/github/login?return_to=/insights", follow_redirects=False)
    assert r.status_code == 302
    loc = urlsplit(r.headers["location"])
    assert (
        f"{loc.scheme}://{loc.netloc}{loc.path}" == "https://github.example/login/oauth/authorize"
    )
    q = {k: v[0] for k, v in parse_qs(loc.query).items()}
    assert q["client_id"] == "Iv1.testclient" and q["scope"] == "read:user"
    assert q["redirect_uri"] == f"{BASE}/auth/github/callback"
    assert q["code_challenge_method"] == "S256" and len(q["state"]) >= 32
    set_cookie = r.headers["set-cookie"].lower()
    assert "tm_session=" in set_cookie and "httponly" in set_cookie and "samesite=lax" in set_cookie
    assert "secure" not in set_cookie  # http://testserver; Secure follows an https PUBLIC_BASE_URL
    gh.codes["code-ok"] = tok
    r = gc.get(f"/auth/github/callback?code=code-ok&state={q['state']}", follow_redirects=False)
    assert r.status_code == 302 and r.headers["location"] == "/insights"
    ex = gh.exchanges[-1]
    assert ex["client_secret"] == "test-client-secret" and ex["code"] == "code-ok"
    digest = hashlib.sha256(ex["code_verifier"].encode()).digest()
    assert base64.urlsafe_b64encode(digest).rstrip(b"=").decode() == q["code_challenge"]
    cookie = gc.cookies.get("tm_session") or ""
    assert tok not in cookie and tok not in base64.b64decode(cookie.split(".")[0] + "==").decode(
        "latin-1"
    )
    # the cookie alone authenticates reads (403 here: this login has no role yet)
    assert gc.get("/v1/me").json()["code"] == "E-AUTH-08"


def test_state_mismatch_and_missing_code_rejected(gc: TestClient, gh: FakeGitHub) -> None:
    r = gc.get("/auth/github/login", follow_redirects=False)
    state = parse_qs(urlsplit(r.headers["location"]).query)["state"][0]
    gh.codes["code-x"] = gh.add("state-tester")[0]
    r = gc.get("/auth/github/callback?code=code-x&state=forged", follow_redirects=False)
    assert r.status_code == 400 and r.json()["code"] == "E-AUTH-09"
    # the state is single use: the real one no longer works after a failed attempt
    r = gc.get(f"/auth/github/callback?code=code-x&state={state}", follow_redirects=False)
    assert r.status_code == 400 and r.json()["code"] == "E-AUTH-09"
    # no login started in this browser at all
    gc.cookies.clear()
    r = gc.get("/auth/github/callback?code=code-x&state=anything", follow_redirects=False)
    assert r.status_code == 400
    # GitHub said no
    r = gc.get("/auth/github/login", follow_redirects=False)
    state = parse_qs(urlsplit(r.headers["location"]).query)["state"][0]
    r = gc.get(f"/auth/github/callback?error=access_denied&state={state}", follow_redirects=False)
    assert r.status_code == 400 and r.json()["code"] == "E-AUTH-09"
    # bad code at the exchange
    r = gc.get("/auth/github/login", follow_redirects=False)
    state = parse_qs(urlsplit(r.headers["location"]).query)["state"][0]
    r = gc.get(f"/auth/github/callback?code=unknown&state={state}", follow_redirects=False)
    assert r.status_code == 400 and r.json()["code"] == "E-AUTH-09"


def test_open_redirect_refused(gc: TestClient, gh: FakeGitHub) -> None:
    tok, _ = gh.add("redirect-tester")
    for bad in ("//evil.example/x", "https://evil.example", "/auth/github/login", "/v1/me"):
        r = gc.get(f"/auth/github/login?return_to={bad}", follow_redirects=False)
        state = parse_qs(urlsplit(r.headers["location"]).query)["state"][0]
        gh.codes["code-r"] = tok
        r = gc.get(f"/auth/github/callback?code=code-r&state={state}", follow_redirects=False)
        assert r.headers["location"] == "/", bad


def test_csrf_header_and_origin_required_on_cookie_writes(gc: TestClient, gh: FakeGitHub) -> None:
    admin_tok = _admin_token(gh)
    _sign_in(gc, gh, admin_tok)
    body = {"client": "CL-NOPE", "code": "PRJ-NOPE"}
    r = gc.post("/v1/admin/projects", json=body)
    assert r.status_code == 403 and r.json()["code"] == "E-API-07"
    r = gc.post("/v1/admin/projects", json=body, headers={"X-Requested-With": "truminds-portal"})
    assert r.status_code == 403 and r.json()["code"] == "E-API-07"  # no Origin
    r = gc.post(
        "/v1/admin/projects",
        json=body,
        headers={"X-Requested-With": "truminds-portal", "Origin": "https://evil.example"},
    )
    assert r.status_code == 403 and r.json()["code"] == "E-API-07"
    r = gc.post("/v1/admin/projects", json=body, headers=CSRF)
    assert r.status_code == 404 and r.json()["code"] == "E-API-04"  # authorised; client unknown
    # reads need no CSRF header
    assert gc.get("/v1/me").status_code == 200
    # logout is a cookie write too
    assert gc.post("/auth/logout").status_code == 403
    assert gc.post("/auth/logout", headers=CSRF).status_code == 204
    assert gc.get("/v1/me").status_code == 401


def test_status_reports_environment(gc: TestClient, gh: FakeGitHub) -> None:
    admin_tok = _admin_token(gh)
    r = gc.get("/v1/status", headers=bearer(admin_tok))
    assert r.status_code == 200, r.text
    assert r.json()["data"]["environment"] == "test"
    assert r.json()["data"]["identity_provider"] == "github"
