"""SDD-07: canonical JSON, Ed25519 sign/verify and tamper detection, accept rule,
sealed MSAL cache, keyring backend rule, Entra device code through a fake msal module,
and the login / logout / whoami / keys commands against the fake insights service."""

from __future__ import annotations

import json
import sys
import types
from datetime import timedelta
from pathlib import Path
from typing import Any, ClassVar

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from helpers import START, World
from tsl.core.clock import iso
from tsl.core.errors import TslError
from tsl.identity import keystore
from tsl.identity.entra import MsalIdentity, SealedCache
from tsl.identity.keystore import KeyringKeyStore, MemoryKeyStore
from tsl.identity.org import OrgConfig
from tsl.identity.signing import (
    NotSignable,
    canonical,
    public_key_b64,
    sign_object,
    signature_ok,
)
from tsl.identity.verify import KeyFacts, accept, facts_from


# ------------------------------------------------------------------------- canonical JSON
def test_rfc8785_key_order_utf16() -> None:
    obj = {"€": 1, "\r": 2, "1": 3, "\U0001f600": 4, "\u0080": 5, "ö": 6}
    out = canonical(obj).decode("utf-8")
    keys = [k for k in json.loads(out)]
    assert keys == ["\r", "1", "\u0080", "ö", "€", "\U0001f600"]


def test_rfc8785_literals_and_escapes() -> None:
    obj = {"string": '€$\u000f\nA\'B"\\\\"/', "literals": [None, True, False]}
    assert canonical(obj) == (
        b'{"literals":[null,true,false],"string":"\xe2\x82\xac$\\u000f\\nA\'B\\"\\\\\\\\\\"/"}'
    )


def test_rfc8785_no_whitespace_and_integers() -> None:
    assert canonical({"b": [1, 2], "a": {"y": 1, "x": 0}}) == b'{"a":{"x":0,"y":1},"b":[1,2]}'


@pytest.mark.parametrize(
    "bad",
    [{"f": 0.12345}, {"f": float("nan")}, {"i": 2**53}, {"s": "é"}, {"t": (1, 2)}],
)
def test_not_signable(bad: dict[str, Any]) -> None:
    with pytest.raises(NotSignable):
        canonical(bad)


# ------------------------------------------------------------------------- sign / verify
@pytest.fixture
def key() -> Ed25519PrivateKey:
    return Ed25519PrivateKey.generate()


def _pub(k: Ed25519PrivateKey) -> bytes:
    from tsl.identity.signing import b64url_decode

    return b64url_decode(public_key_b64(k))


def test_sign_verify_round_trip(key: Ed25519PrivateKey) -> None:
    rec = {"schema": "verification.v1", "outcome": "PASS", "signals": {"S1": 0.9}}
    signed = sign_object(rec, "key_01", key)
    assert signed["key_id"] == "key_01" and signature_ok(signed, _pub(key))
    # verification is over the stored content: key order on disk does not matter
    reordered = json.loads(json.dumps(dict(reversed(list(signed.items())))))
    assert signature_ok(reordered, _pub(key))


@pytest.mark.parametrize(
    "tamper",
    [
        lambda r: r.update(outcome="ESCALATE"),
        lambda r: r["signals"].update(S1=1.0),
        lambda r: r.update(key_id="key_02"),
        lambda r: r.update(extra="added"),
        lambda r: r.pop("schema"),
        lambda r: r.update(
            signature=r["signature"][:-2] + ("AA" if r["signature"][-2:] != "AA" else "BB")
        ),
    ],
)
def test_tamper_is_detected(key: Ed25519PrivateKey, tamper: Any) -> None:
    signed = sign_object(
        {"schema": "x.v1", "outcome": "PASS", "signals": {"S1": 0.9}}, "key_01", key
    )
    t = json.loads(json.dumps(signed))
    tamper(t)
    assert not signature_ok(t, _pub(key))


def test_wrong_key_and_double_sign(key: Ed25519PrivateKey) -> None:
    signed = sign_object({"a": 1}, "key_01", key)
    assert not signature_ok(signed, _pub(Ed25519PrivateKey.generate()))
    assert not signature_ok({"a": 1}, _pub(key))
    with pytest.raises(NotSignable):
        sign_object(signed, "key_01", key)


# ------------------------------------------------------------------------- accept rule
def _facts(key: Ed25519PrivateKey, **kw: Any) -> KeyFacts:
    base = {
        "known": True,
        "public_key": public_key_b64(key),
        "created_at": iso(START),
        "expires_at": iso(START + timedelta(days=180)),
        "roles_at": ["tech_lead"],
        "anchored_at": iso(START + timedelta(hours=1)),
    }
    base.update(kw)
    return facts_from(base)


def test_accept_rules(key: Ed25519PrivateKey) -> None:
    rec = sign_object({"a": 1}, "key_01", key)
    at = START + timedelta(minutes=10)
    assert accept(rec, at, ["tech_lead"], _facts(key)) == ("ok", None)
    assert accept(rec, at, [], KeyFacts(known=False)) == ("bad", "unknown_key")
    assert accept(rec, at, ["approver"], _facts(key))[1] == "role_missing"
    assert accept(rec, START - timedelta(hours=1), [], _facts(key))[1] == "signed_before_key"
    assert accept(rec, START + timedelta(days=200), [], _facts(key))[1] == "key_expired"
    revoked = _facts(
        key, revoked_at=iso(START + timedelta(minutes=5)), revoked_reason="user_request"
    )
    assert accept(rec, at, [], revoked)[1] == "revoked"
    early = START + timedelta(minutes=1)
    assert accept(rec, early, [], revoked) == ("ok", None)
    comp = _facts(
        key,
        revoked_at=iso(at),
        revoked_reason="compromised",
        compromised_since=iso(START + timedelta(minutes=5)),
    )
    assert accept(rec, at, [], comp)[1] == "compromised"
    assert accept(rec, at, [], _facts(key, anchored_at=None)) == ("unanchored", None)
    assert (
        accept(rec, at, [], _facts(key, anchored_at=None), require_anchor=True)[1] == "not_anchored"
    )
    tampered = dict(rec, a=2)
    assert accept(tampered, at, [], _facts(key))[1] == "bad_signature"


# ------------------------------------------------------------------------- key stores
def test_sealed_cache_round_trip_and_tamper(tmp_path: Path) -> None:
    ks = MemoryKeyStore()
    c = SealedCache(tmp_path / "msal-cache.bin", ks, "dev_A")
    assert c.load() is None
    c.save('{"AccessToken": {}}')
    raw = (tmp_path / "msal-cache.bin").read_bytes()
    assert b"AccessToken" not in raw and c.load() == '{"AccessToken": {}}'
    (tmp_path / "msal-cache.bin").write_bytes(raw[:-1] + bytes([raw[-1] ^ 1]))
    assert c.load() is None
    c.save("x")
    assert SealedCache(tmp_path / "msal-cache.bin", ks, "dev_OTHER").load() is None
    c.clear()
    assert not (tmp_path / "msal-cache.bin").exists() and ks.get("msal-cache-key") is None


def test_keyring_refuses_unlisted_platform(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "plan9")
    with pytest.raises(TslError) as e:
        KeyringKeyStore().get("x")
    assert e.value.code == "E-KEY-01"


def test_keyring_refuses_unusable_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    mod = types.ModuleType("fake_backend_mod")

    class Weak:
        priority = 0

    mod.Weak = Weak  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "fake_backend_mod", mod)
    monkeypatch.setitem(keystore.ALLOWED_BACKENDS, sys.platform, "fake_backend_mod.Weak")
    with pytest.raises(TslError) as e:
        KeyringKeyStore().set("x", "y")
    assert e.value.code == "E-KEY-01"


# ------------------------------------------------------------------------- Entra via msal
class _FakeApp:
    tenant = "tenant"
    accounts: ClassVar[list[dict[str, str]]] = []

    def __init__(self, client_id: str, authority: str, token_cache: Any) -> None:
        self.cache = token_cache

    def initiate_device_flow(self, scopes: list[str]) -> dict[str, str]:
        return {"user_code": "ABCD", "message": "Open https://microsoft.com/devicelogin, code ABCD"}

    def acquire_token_by_device_flow(self, flow: dict[str, str]) -> dict[str, Any]:
        self.cache.has_state_changed = True
        _FakeApp.accounts = [{"username": "eng"}]
        return {"access_token": "AT", "id_token_claims": {"tid": _FakeApp.tenant, "oid": "o1"}}

    def get_accounts(self) -> list[dict[str, str]]:
        return _FakeApp.accounts

    def acquire_token_silent(self, scopes: list[str], account: Any, force_refresh: bool) -> Any:
        return {"access_token": "AT2" if force_refresh else "AT"}


class _FakeCache:
    def __init__(self) -> None:
        self.has_state_changed = False

    def deserialize(self, text: str) -> None:
        self.text = text

    def serialize(self) -> str:
        return '{"cache": 1}'


@pytest.fixture
def fake_msal(monkeypatch: pytest.MonkeyPatch) -> None:
    mod = types.ModuleType("msal")
    mod.PublicClientApplication = _FakeApp  # type: ignore[attr-defined]
    mod.SerializableTokenCache = _FakeCache  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "msal", mod)
    _FakeApp.accounts = []
    _FakeApp.tenant = "tenant"


def _org() -> OrgConfig:
    return OrgConfig(
        configured=True,
        tenant_id="tenant",
        tsl_client_id="client",
        api_scope="api://x/Events.Write",
        service_url="https://svc.invalid",
        companion_remote_template="x/{repo}",
        github_api_url="https://gh.invalid",
        link_hosts=(),
    )


def test_msal_device_code_and_silent(fake_msal: None, tmp_path: Path) -> None:
    ks = MemoryKeyStore()
    ident = MsalIdentity(_org(), SealedCache(tmp_path / "c.bin", ks, "dev_A"))
    with pytest.raises(TslError) as e:
        ident.silent_token()
    assert e.value.code == "E-AUTH-01"
    shown: list[str] = []
    res = ident.device_login(shown.append)
    assert res["access_token"] == "AT" and "devicelogin" in shown[0]
    assert (tmp_path / "c.bin").is_file()
    assert ident.silent_token() == "AT" and ident.silent_token(force_refresh=True) == "AT2"
    ident.logout()
    assert not (tmp_path / "c.bin").exists()


def test_msal_wrong_tenant_and_unconfigured(fake_msal: None, tmp_path: Path) -> None:
    _FakeApp.tenant = "other-tenant"
    ident = MsalIdentity(_org(), SealedCache(tmp_path / "c.bin", MemoryKeyStore(), "dev_A"))
    with pytest.raises(TslError) as e:
        ident.device_login(lambda s: None)
    assert e.value.code == "E-AUTH-01" and not (tmp_path / "c.bin").exists()
    org = _org().model_copy(update={"configured": False})
    bare = MsalIdentity(org, SealedCache(tmp_path / "d.bin", MemoryKeyStore(), "dev_A"))
    with pytest.raises(TslError):
        bare.silent_token()


# ------------------------------------------------------------------------- commands
def test_login_registers_key_and_writes_device_code_to_stderr(world: World) -> None:
    rt = world.rt("eng2")
    code, env, _out, _err = world.cli(["login", "--json"], user="eng2")
    # non-interactive (stdin is not a tty) and no cached token: refuses
    assert code == 1 and env is not None and env["code"] == "E-USE-01"
    data = world.login("eng2")
    assert data["pseudonym"] == "eng-77b1" and data["key_new"] is True
    assert data["key_id"] in world.insights.keys
    assert any("devicelogin" in line for line in rt.stderr_lines)
    code, env, _, _ = world.cli(["login", "--json"], user="eng2")  # silent token now works
    assert code == 0 and env is not None and env["data"]["key_new"] is False


def test_login_without_app_role(world: World) -> None:
    with pytest.raises(TslError) as e:
        world.login("biz")
    assert e.value.code == "E-AUTH-08"


def test_login_offline(world: World) -> None:
    world.identities.clear()
    world.runtimes.pop("eng2", None)
    world.insights.offline = True
    with pytest.raises(TslError) as e:
        world.login("eng2")
    assert e.value.code == "E-NET-02"


def test_whoami_and_role_cache(world: World) -> None:
    code, env, _, _ = world.cli(["whoami", "--json"])
    assert code == 0 and env is not None
    assert env["data"]["pseudonym"] == "eng-4f2a" and env["data"]["key_status"] == "active"
    # cache is fresh: offline still answers
    world.insights.offline = True
    code, env, _, _ = world.cli(["whoami", "--json"])
    assert code == 0
    # cache older than 24 h and offline: E-AUTH-07
    world.clock.advance(hours=25)
    code, env, _, _ = world.cli(["whoami", "--json"])
    assert code == 10 and env is not None and env["code"] == "E-AUTH-07"


def test_keys_list_rotate_revoke(world: World) -> None:
    code, env, _, _ = world.cli(["keys", "list", "--json"])
    assert code == 0 and env is not None
    old = next(k for k in env["data"]["keys"] if k["local_active"])["key_id"]
    code, env, _, _ = world.cli(["keys", "rotate", "--json"])
    assert code == 0 and env is not None and env["data"]["previous"] == old
    new = env["data"]["key_id"]
    assert world.insights.keys[old]["revoked_reason"] == "replaced"
    code, env, _, _ = world.cli(["keys", "revoke", "key_01NOTMINE0000000000000000", "--json"])
    assert code == 10 and env is not None and env["code"] == "E-KEY-04"
    code, env, _, _ = world.cli(["keys", "revoke", new, "--json"])
    assert code == 0
    code, env, _, _ = world.cli(["whoami", "--json"])
    assert env is not None and env["data"]["key_status"] == "unknown"


def test_logout_revoke_key(world: World) -> None:
    rt = world.rt("eng")
    kid = json.loads(rt.home.active_key.read_text())["key_id"]
    code, env, _, _ = world.cli(["logout", "--revoke-key", "--json"])
    assert code == 0 and env is not None and env["data"]["revoked_key"] == kid
    assert world.insights.keys[kid]["revoked_reason"] == "user_request"
    assert not rt.home.me.exists()
    code, env, _, _ = world.cli(["whoami", "--json"])
    assert code == 10 and env is not None and env["code"] == "E-AUTH-01"


def test_signing_needs_a_key(world: World) -> None:
    from tsl.identity.keys import load_signer

    rt = world.rt("eng")
    rt.keystore.items.clear()  # type: ignore[attr-defined]
    with pytest.raises(TslError) as e:
        load_signer(rt)
    assert e.value.code == "E-AUTH-02"
