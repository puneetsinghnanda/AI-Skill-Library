"""Interim GitHub identity provider (ADR 0006, SDD-07 §"Identity providers").

GitHub is faked with an ``httpx.MockTransport``; sleeping is recorded, never real. No test talks to
GitHub. The Entra path keeps its own tests in test_identity.py.
"""

from __future__ import annotations

import json
import tomllib
from pathlib import Path
from typing import Any

import httpx
import pytest

from helpers import World
from tsl.core.errors import TslError
from tsl.identity.entra import MsalIdentity
from tsl.identity.github import GRANT, GitHubIdentity, github_cache
from tsl.identity.keystore import MemoryKeyStore
from tsl.identity.org import OrgConfig

ROOT = Path(__file__).resolve().parents[2]
OAUTH = "https://github.example"
API = "https://api.github.example"


def _org(**kw: Any) -> OrgConfig:
    base: dict[str, Any] = {
        "configured": True,
        "tenant_id": "unused",
        "tsl_client_id": "unused",
        "api_scope": "unused",
        "service_url": "https://insights.example.invalid",
        "companion_remote_template": "x/{repo}",
        "github_api_url": API,
        "provider": "github",
        "github_client_id": "Iv1.testclientid",
        "github_oauth_url": OAUTH,
    }
    base.update(kw)
    return OrgConfig(**base)


class FakeGitHub:
    """Device-flow and /user endpoints. ``polls`` is the queue of answers to the token poll."""

    def __init__(self, polls: list[dict[str, Any]], token: str = "gho_test_token") -> None:  # noqa: S107
        self.polls = polls
        self.token = token
        self.valid_tokens = {token}
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path
        if path == "/login/device/code":
            form = dict(httpx.QueryParams(request.content.decode()))
            assert form == {"client_id": "Iv1.testclientid", "scope": "read:user"}
            return httpx.Response(
                200,
                json={
                    "device_code": "dc-123",
                    "user_code": "WDJB-MJHT",
                    "verification_uri": f"{OAUTH}/login/device",
                    "expires_in": 900,
                    "interval": 5,
                },
            )
        if path == "/login/oauth/access_token":
            form = dict(httpx.QueryParams(request.content.decode()))
            assert form["grant_type"] == GRANT and form["device_code"] == "dc-123"
            return httpx.Response(200, json=self.polls.pop(0))
        if path == "/user":
            auth = request.headers.get("authorization", "")
            if auth.removeprefix("Bearer ") in self.valid_tokens:
                return httpx.Response(200, json={"id": 4242, "login": "tester-one"})
            return httpx.Response(401, json={"message": "Bad credentials"})
        return httpx.Response(404)


class Clock:
    def __init__(self) -> None:
        self.t = 0.0
        self.slept: list[float] = []

    def sleep(self, s: float) -> None:
        self.slept.append(s)
        self.t += s

    def now(self) -> float:
        return self.t


def _ident(tmp_path: Path, gh: FakeGitHub, clock: Clock, org: OrgConfig | None = None) -> Any:
    ks = MemoryKeyStore()
    cache = github_cache(tmp_path / "github-token.bin", ks, "dev_A")
    ident = GitHubIdentity(
        org or _org(),
        cache,
        transport=httpx.MockTransport(gh),
        sleep=clock.sleep,
        monotonic=clock.now,
    )
    return ident, ks


def test_device_flow_pending_slow_down_then_token(tmp_path: Path) -> None:
    gh = FakeGitHub(
        [
            {"error": "authorization_pending"},
            {"error": "slow_down", "interval": 10},
            {"error": "authorization_pending"},
            {"access_token": "gho_test_token", "token_type": "bearer", "scope": "read:user"},
        ]
    )
    clock = Clock()
    ident, ks = _ident(tmp_path, gh, clock)
    shown: list[str] = []
    res = ident.device_login(shown.append)
    assert res["access_token"] == "gho_test_token"
    assert res["id_token_claims"] == {"login": "tester-one"}
    assert "WDJB-MJHT" in shown[0] and f"{OAUTH}/login/device" in shown[0]
    # interval honoured; slow_down raises it by at least 5 s and it stays raised
    assert clock.slept == [5.0, 5.0, 10.0, 10.0]
    # sealed at rest: the token is not in the file, and the key is in the keychain item
    raw = (tmp_path / "github-token.bin").read_bytes()
    assert b"gho_test_token" not in raw
    assert ks.get("github-token-key") is not None and ks.get("msal-cache-key") is None
    assert ident.silent_token() == "gho_test_token"
    ident.logout()
    assert not (tmp_path / "github-token.bin").exists()
    with pytest.raises(TslError) as e:
        ident.silent_token()
    assert e.value.code == "E-AUTH-01" and e.value.next == "tsl login"


@pytest.mark.parametrize(
    ("answer", "words"),
    [({"error": "expired_token"}, "expired"), ({"error": "access_denied"}, "cancelled")],
)
def test_device_flow_ends_on_expired_or_denied(
    tmp_path: Path, answer: dict[str, Any], words: str
) -> None:
    gh = FakeGitHub([{"error": "authorization_pending"}, answer])
    ident, _ = _ident(tmp_path, gh, Clock())
    with pytest.raises(TslError) as e:
        ident.device_login(lambda s: None)
    assert e.value.code == "E-AUTH-01" and words in e.value.message
    assert e.value.next == "tsl login"
    assert not (tmp_path / "github-token.bin").exists()


def test_device_flow_local_deadline(tmp_path: Path) -> None:
    gh = FakeGitHub([{"error": "authorization_pending"}] * 400)
    clock = Clock()
    ident, _ = _ident(tmp_path, gh, clock)
    with pytest.raises(TslError) as e:
        ident.device_login(lambda s: None)
    assert "expired" in e.value.message and clock.t >= 900


def test_device_flow_disabled_on_the_app(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": "device_flow_disabled"})

    ident = GitHubIdentity(
        _org(),
        github_cache(tmp_path / "t.bin", MemoryKeyStore(), "dev_A"),
        transport=httpx.MockTransport(handler),
        sleep=lambda s: None,
    )
    with pytest.raises(TslError) as e:
        ident.device_login(lambda s: None)
    assert "device_flow_disabled" in e.value.message and "Device Flow" in e.value.next


def test_rejected_token_is_deleted_on_force_refresh(tmp_path: Path) -> None:
    gh = FakeGitHub([{"access_token": "gho_test_token"}])
    ident, _ = _ident(tmp_path, gh, Clock())
    ident.device_login(lambda s: None)
    assert ident.silent_token(force_refresh=True) == "gho_test_token"  # still valid at GitHub
    gh.valid_tokens.clear()  # revoked on GitHub
    with pytest.raises(TslError) as e:
        ident.silent_token(force_refresh=True)
    assert e.value.code == "E-AUTH-01" and e.value.next == "tsl login"
    assert not (tmp_path / "github-token.bin").exists()


def test_unconfigured_build_refuses(tmp_path: Path) -> None:
    for org in (_org(github_client_id=""), _org(configured=False)):
        ident, _ = _ident(tmp_path, FakeGitHub([]), Clock(), org)
        with pytest.raises(TslError) as e:
            ident.silent_token()
        assert e.value.code == "E-AUTH-01"


def test_runtime_picks_provider_from_org(world: World) -> None:
    rt = world.rt("eng")
    rt.identity_provider = None
    rt.org = rt.org.model_copy(update={"provider": "github", "github_client_id": "Iv1.x"})
    assert isinstance(rt.identity(), GitHubIdentity)
    rt.identity_provider = None
    rt.org = rt.org.model_copy(update={"provider": "entra"})
    assert isinstance(rt.identity(), MsalIdentity)


# ----------------------------------------------------------------- commands with provider github
def _github_runtime(world: World, user: str, gh: FakeGitHub) -> None:
    rt = world.rt(user)
    rt.org = rt.org.model_copy(
        update={
            "provider": "github",
            "github_client_id": "Iv1.testclientid",
            "github_oauth_url": OAUTH,
            "github_api_url": API,
        }
    )
    rt.identity_provider = GitHubIdentity(
        rt.org,
        github_cache(rt.home.github_token, rt.keystore, rt.ensure_device()),
        transport=httpx.MockTransport(gh),
        sleep=lambda s: None,
    )


def test_login_whoami_doctor_logout_with_github(world: World) -> None:
    # The fake insights service knows tokens of the form tok:<user>.
    gh = FakeGitHub([{"error": "authorization_pending"}, {"access_token": "tok:eng2"}], "tok:eng2")
    _github_runtime(world, "eng2", gh)
    data = world.login("eng2")
    assert data["pseudonym"] == "eng-77b1" and data["key_new"] is True
    rt = world.rt("eng2")
    assert any("WDJB-MJHT" in line for line in rt.stderr_lines)
    # second login: silent token, no device flow
    before = len(gh.requests)
    data = world.login("eng2")
    assert data["key_new"] is False and len(gh.requests) == before
    code, env, _, _ = world.cli(["whoami", "--json"], user="eng2")
    assert code == 0 and env is not None and env["data"]["pseudonym"] == "eng-77b1"
    code, env, _, _ = world.cli(["doctor", "--json"], user="eng2")
    assert env is not None
    login_check = next(c for c in env["data"]["checks"] if c["id"] == "login")
    assert login_check["status"] == "pass" and login_check["detail"] == "provider github"
    code, env, _, _ = world.cli(["logout", "--json"], user="eng2")
    assert code == 0 and not rt.home.github_token.exists()
    code, env, _, _ = world.cli(["doctor", "--json"], user="eng2")
    assert env is not None
    login_check = next(c for c in env["data"]["checks"] if c["id"] == "login")
    assert login_check["status"] == "fail" and login_check["fix"] == "tsl login"


def test_login_replaces_a_stored_token_the_service_rejects(world: World) -> None:
    gh = FakeGitHub([{"access_token": "tok:eng2"}], "tok:eng2")
    _github_runtime(world, "eng2", gh)
    rt = world.rt("eng2")
    # a stale token the service no longer accepts (unknown user -> 401)
    rt.identity().cache.save(json.dumps({"access_token": "tok:ghost"}))  # type: ignore[attr-defined]
    data = world.login("eng2")
    assert data["pseudonym"] == "eng-77b1"
    assert rt.identity().silent_token() == "tok:eng2"


def test_test_org_example_is_a_valid_github_org_file() -> None:
    data = tomllib.loads((ROOT / "deploy" / "test-org.github.toml.example").read_text())
    org = OrgConfig.model_validate(data)
    assert org.provider == "github" and org.github_oauth_url == "https://github.com"
    assert org.service_url.startswith("http")
