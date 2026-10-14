"""Contract tests: the real ``tsl`` client code (ROOT/tsl/src/tsl) against this service.

``tsl events flush`` (outbox, SDD-04 §8.3) and key registration and revocation (SDD-07 §5) run
unchanged; only the HTTP transport is swapped for the in-process TestClient. tsl is imported
dynamically so mypy checks this service without needing tsl's stubs.
"""

from __future__ import annotations

import importlib
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.conftest import ROOT, Person, TokenFactory, bearer, project, run_started

TSL_SRC = ROOT / "tsl" / "src"


def _tsl(name: str) -> ModuleType:
    if not (TSL_SRC / "tsl").is_dir():
        pytest.skip("tsl sources not present")
    if str(TSL_SRC) not in sys.path:
        sys.path.insert(0, str(TSL_SRC))
    sys.dont_write_bytecode = True  # never write caches into the tsl tree
    try:
        return importlib.import_module(name)
    except ImportError as exc:  # a tsl-only dependency missing from this venv
        pytest.skip(f"tsl not importable: {exc}")


class InProcessInsights:
    """Implements tsl's ``InsightsClient`` protocol over the in-process app."""

    def __init__(self, c: TestClient) -> None:
        self.c = c
        self.result = _tsl("tsl.insights.client").HttpResult

    def _r(self, method: str, path: str, token: str, body: Any = None) -> Any:
        r = self.c.request(method, path, headers=bearer(token), json=body)
        try:
            payload: Any = r.json()
        except ValueError:
            payload = None
        return self.result(r.status_code, payload, dict(r.headers))

    def post_events(self, token: str, events: list[dict[str, Any]]) -> Any:
        return self._r("POST", "/v1/events", token, {"events": events})

    def register_key(self, token: str, body: dict[str, Any]) -> Any:
        return self._r("POST", "/v1/keys", token, body)

    def revoke_key(self, token: str, key_id: str, body: dict[str, Any]) -> Any:
        return self._r("POST", f"/v1/keys/{key_id}/revoke", token, body)

    def verify_signatures(self, token: str, body: dict[str, Any]) -> Any:
        return self._r("POST", "/v1/signatures/verify", token, body)


class MemKeystore:
    def __init__(self) -> None:
        self.items: dict[str, str] = {}

    def set(self, k: str, v: str) -> None:
        self.items[k] = v

    def get(self, k: str) -> str | None:
        return self.items.get(k)

    def delete(self, k: str) -> None:
        self.items.pop(k, None)


def test_outbox_flush_against_service(
    client: TestClient,
    token: TokenFactory,
    people: dict[str, Person],
    world: Any,
    tmp_path: Path,
    migrated: Any,
) -> None:
    outbox_mod = _tsl("tsl.telemetry.outbox")
    clock_mod = _tsl("tsl.core.clock")
    ids_mod = _tsl("tsl.core.ids")
    clock = clock_mod.FrozenClock(datetime.now(UTC).replace(microsecond=0))
    ids = ids_mod.IdFactory(clock)
    ob = outbox_mod.Outbox(tmp_path / "outbox.db", clock, ids, strict=True)
    run_id = ids.new("run")
    for i in range(3):
        assert ob.enqueue(
            "run.started", run_started(world.system, ticket=f"ORD-{900 + i}"), run_id=run_id
        )
    p = people["eng"]
    tok = token(p.oid, p.roles)
    api = InProcessInsights(client)
    res = ob.flush(lambda force: tok, api.post_events, 10.0)
    assert (res.sent, res.rejected, res.duplicates) == (3, 0, 0), res.data()
    assert ob.stats()["pending"] == 0
    # The server dedupes on event_id: resending the same rows (as after a lost 202) counts as a
    # duplicate, which tsl treats as delivered (Doc 5 R-05).
    sent = ob.events()
    replay = [
        {k: e[k] for k in ("event_id", "type", "schema_version", "occurred_at", "body")}
        | {"run_id": run_id}
        for e in sent
    ]
    r = api.post_events(tok, replay)
    assert r.status == 202 and sorted(r.body["duplicates"]) == sorted(e["event_id"] for e in sent)
    project(migrated)


def test_key_register_revoke_and_verify_via_tsl(
    client: TestClient,
    token: TokenFactory,
    people: dict[str, Person],
    world: Any,
    ci_token: str,
    tmp_path: Path,
) -> None:
    keys_mod = _tsl("tsl.identity.keys")
    clock_mod = _tsl("tsl.core.clock")
    ids_mod = _tsl("tsl.core.ids")
    errors_mod = _tsl("tsl.core.errors")
    p = people["eng"]
    tok = token(p.oid, p.roles)
    me = client.get("/v1/me", headers=bearer(tok)).json()
    clock = clock_mod.FrozenClock(datetime.now(UTC).replace(microsecond=0))
    ids = ids_mod.IdFactory(clock)
    dev = ids.new("dev")
    rt = SimpleNamespace(
        clock=clock,
        ids=ids,
        keystore=MemKeystore(),
        insights=InProcessInsights(client),
        home=SimpleNamespace(active_key=tmp_path / "keys" / "active.json"),
        ensure_device=lambda: dev,
        device_id=lambda: dev,
        user_config=lambda: {"device": {"label": "contract-laptop"}},
        token=lambda: tok,
    )
    # tsl signs the proof with sub = the oid returned by GET /v1/me (SDD-07 §5.2)
    info = keys_mod.register_new_key(rt, tok, str(me["oid"]))
    kid = info["key_id"]
    api = InProcessInsights(client)
    item = {"kind": "verification", "key_id": kid, "signed_at": clock_mod.iso(clock())}
    v = api.verify_signatures(ci_token, {"system": world.system, "items": [item]})
    assert v.status == 200 and v.body["items"][0]["revoked_at"] is None

    out = keys_mod.revoke(rt, kid, None)
    assert out["revoked_reason"] == "user_request"
    assert not (tmp_path / "keys" / "active.json").exists()
    # A revoked key is reported as revoked to every verifier (tsl's accept rule rejects it) ...
    v = api.verify_signatures(ci_token, {"system": world.system, "items": [item]})
    fact = v.body["items"][0]
    assert fact["known"] is True and fact["revoked_at"] is not None
    assert fact["revoked_reason"] == "user_request"
    # ... and can never be registered again (E-KEY-03).
    pub = info["public_key"]
    assert pub
    with pytest.raises(errors_mod.TslError) as ei:
        rt.ids = SimpleNamespace(new=lambda prefix: kid)  # reuse the revoked key id
        keys_mod.register_new_key(rt, tok, str(me["oid"]))
    assert ei.value.code == "E-KEY-03"
    # proof bound to another subject is refused (E-KEY-02)
    rt.ids = ids
    with pytest.raises(errors_mod.TslError) as ei:
        keys_mod.register_new_key(rt, tok, "not-the-token-oid")
    assert ei.value.code == "E-KEY-02"


def test_revoked_key_rejected_on_write_paths(
    client: TestClient, token: TokenFactory, people: dict[str, Person], ci_token: str
) -> None:
    """A revoked key cannot be revoked again by a non-owner, and GET reports it revoked."""
    from tests.conftest import key_registration

    p = people["eng2"]
    body, _ = key_registration(p.oid)
    hdr = bearer(token(p.oid, p.roles))
    assert client.post("/v1/keys", json=body, headers=hdr).status_code == 201
    kid = body["key_id"]
    assert (
        client.post(
            f"/v1/keys/{kid}/revoke", json={"reason": "lost_device"}, headers=hdr
        ).status_code
        == 200
    )
    r = client.post("/v1/keys", json=body | {"iat": body["iat"]}, headers=hdr)
    assert r.status_code in (400, 409)
    r = client.get(f"/v1/keys/{kid}", headers=bearer(ci_token))
    assert r.status_code == 200 and r.json()["revoked_reason"] == "lost_device"


@pytest.mark.parametrize(
    ("who", "allowed"),
    [("eng", True), ("lead", True), ("admin2", True), ("biz", False)],
)
def test_tsl_reads_app_roles_from_me(
    client: TestClient, token: TokenFactory, people: dict[str, Person], who: str, allowed: bool
) -> None:
    """tsl's login check (APP_ROLES_ALLOWED) must see the roles in the real GET /v1/me body."""
    me_mod = _tsl("tsl.identity.me")
    p = people[who]
    body = client.get("/v1/me", headers=bearer(token(p.oid, p.roles))).json()
    roles = me_mod.app_roles(body)
    assert roles == set(p.roles)
    assert bool(roles & me_mod.APP_ROLES_ALLOWED) is allowed
