"""Keys and signatures (SDD-07 §5, §7.2; ID-T-06, ID-T-07, ID-T-09; TC-INS-007)."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.engine import Engine

from tests.conftest import Person, TokenFactory, bearer, key_registration, now_iso


def _tsl(token: TokenFactory, p: Person) -> dict[str, str]:
    return bearer(token(p.oid, p.roles))


def test_register_idempotent_conflict(
    client: TestClient, token: TokenFactory, people: dict[str, Person]
) -> None:
    p = people["eng2"]
    body, _priv = key_registration(p.oid)
    r = client.post("/v1/keys", json=body, headers=_tsl(token, p))
    assert r.status_code == 201, r.text
    out = r.json()
    assert out["key_id"] == body["key_id"] and out["pseudonym"] == p.pseudonym and out["expires_at"]
    assert client.post("/v1/keys", json=body, headers=_tsl(token, p)).status_code == 200
    other, _ = key_registration(p.oid, key_id=body["key_id"])
    r = client.post("/v1/keys", json=other, headers=_tsl(token, p))
    assert r.status_code == 409 and r.json()["code"] == "E-KEY-03"


def test_register_bad_proof_and_old_iat(
    client: TestClient, token: TokenFactory, people: dict[str, Person]
) -> None:
    p = people["eng2"]
    body, _ = key_registration(p.oid, sub=str(uuid.uuid4()))  # proof bound to another user
    r = client.post("/v1/keys", json=body, headers=_tsl(token, p))
    assert r.status_code == 400 and r.json()["code"] == "E-KEY-02"
    body, _ = key_registration(p.oid, iat=now_iso(-600))
    r = client.post("/v1/keys", json=body, headers=_tsl(token, p))
    assert r.status_code == 400 and r.json()["code"] == "E-KEY-02"


def test_business_cannot_register(
    client: TestClient, token: TokenFactory, people: dict[str, Person]
) -> None:
    p = people["biz"]
    body, _ = key_registration(p.oid)
    r = client.post("/v1/keys", json=body, headers=_tsl(token, p))
    assert r.status_code == 403 and r.json()["code"] == "E-AUTH-08"


def test_rotation_replaces_previous(
    client: TestClient, token: TokenFactory, people: dict[str, Person], owner_db: Engine
) -> None:
    p = people["eng2"]
    a, _ = key_registration(p.oid)
    b, _ = key_registration(p.oid, device_id=a["device_id"])
    assert client.post("/v1/keys", json=a, headers=_tsl(token, p)).status_code == 201
    assert client.post("/v1/keys", json=b, headers=_tsl(token, p)).status_code == 201
    with owner_db.connect() as c:
        assert (
            c.execute(
                text("SELECT revoked_reason FROM keys WHERE key_id = :k"), {"k": a["key_id"]}
            ).scalar_one()
            == "replaced"
        )
    keys = client.get("/v1/me/keys", headers=_tsl(token, p)).json()["keys"]
    assert {a["key_id"], b["key_id"]} <= {k["key_id"] for k in keys}


def test_get_key_and_revoke(
    client: TestClient,
    token: TokenFactory,
    people: dict[str, Person],
    world: Any,
    ci_token: str,
    owner_db: Engine,
) -> None:
    p = people["eng2"]
    body, _ = key_registration(p.oid)
    assert client.post("/v1/keys", json=body, headers=_tsl(token, p)).status_code == 201
    kid = body["key_id"]
    r = client.get(
        f"/v1/keys/{kid}", params={"system": world.other_system}, headers=bearer(ci_token)
    )
    assert (
        r.status_code == 200
        and r.json()["revoked_at"] is None
        and r.json()["roles_at"] == ["engineer"]
    )
    # not the owner and not admin -> E-KEY-04
    r = client.post(
        f"/v1/keys/{kid}/revoke",
        json={"reason": "user_request"},
        headers=_tsl(token, people["eng"]),
    )
    assert r.status_code == 404 and r.json()["code"] == "E-KEY-04"
    # owner may not use admin-only reasons
    r = client.post(f"/v1/keys/{kid}/revoke", json={"reason": "offboarded"}, headers=_tsl(token, p))
    assert r.status_code == 403 and r.json()["code"] == "E-AUTH-08"
    r = client.post(
        f"/v1/keys/{kid}/revoke",
        json={"reason": "user_request", "note": "rotating laptop"},
        headers=_tsl(token, p),
    )
    assert r.status_code == 200 and r.json()["revoked_reason"] == "user_request"
    r = client.get(f"/v1/keys/{kid}", headers=bearer(ci_token))
    assert r.json()["revoked_at"] is not None  # TC-INS-007
    # a revoked key is never re-activated
    r = client.post("/v1/keys", json={**body, "iat": now_iso()}, headers=_tsl(token, p))
    assert r.status_code in (400, 409)
    with owner_db.connect() as c:
        assert (
            c.execute(
                text("SELECT count(*) FROM audit_log WHERE action = 'key_revoke' AND target = :k"),
                {"k": kid},
            ).scalar_one()
            == 1
        )


def test_compromised_since_rules(
    client: TestClient, token: TokenFactory, people: dict[str, Person]
) -> None:
    p = people["eng2"]
    body, _ = key_registration(p.oid)
    assert client.post("/v1/keys", json=body, headers=_tsl(token, p)).status_code == 201
    kid = body["key_id"]
    r = client.post(
        f"/v1/keys/{kid}/revoke",
        json={"reason": "compromised", "compromised_since": "2001-01-01T00:00:00Z"},
        headers=_tsl(token, p),
    )
    assert r.status_code == 422 and r.json()["code"] == "E-KEY-06"
    r = client.post(
        f"/v1/keys/{kid}/revoke", json={"reason": "lost_device"}, headers=_tsl(token, p)
    )
    assert r.status_code == 200
    first = r.json()["compromised_since"]
    import time

    time.sleep(2)
    # admin via portal (Portal.Write) may move it earlier only
    adm = bearer(token(people["admin"].oid, people["admin"].roles, client="portal"))
    r = client.post(
        f"/v1/keys/{kid}/revoke",
        json={"reason": "compromised", "compromised_since": now_iso()},
        headers=adm,
    )
    assert r.status_code == 422
    r = client.post(
        f"/v1/keys/{kid}/revoke",
        json={"reason": "compromised", "compromised_since": first},
        headers=adm,
    )
    assert r.status_code == 200 and r.json()["revoked_reason"] == "compromised"


def test_signatures_verify(
    client: TestClient, ci_token: str, keys_of: dict[str, str], world: Any
) -> None:
    items = [
        {
            "kind": "verification",
            "key_id": keys_of["eng"],
            "signed_at": now_iso(),
            "roles_needed": ["engineer"],
            "anchor_sha256": "e" * 64,
        },
        {"kind": "approval", "key_id": "key_01ZZZZZZZZZZZZZZZZZZZZZZZZ", "signed_at": now_iso()},
    ]
    r = client.post(
        "/v1/signatures/verify",
        json={"system": world.system, "items": items},
        headers=bearer(ci_token),
    )
    assert r.status_code == 200, r.text
    out = r.json()["items"]
    assert (
        out[0]["known"] is True
        and out[0]["roles_at"] == ["engineer"]
        and out[0]["anchored_at"] is None
    )
    assert out[1]["known"] is False


def test_roles_at_history(
    client: TestClient,
    token: TokenFactory,
    people: dict[str, Person],
    world: Any,
    keys_of: dict[str, str],
    ci_token: str,
) -> None:
    """ID-T-09: a revoked grant is absent at later times but present before."""
    before = now_iso(-1)
    adm = bearer(token(people["admin"].oid, people["admin"].roles, client="portal"))
    r = client.post(
        "/v1/admin/role-grants",
        headers=adm,
        json={
            "user": people["owner"].pseudonym,
            "role": "engineer",
            "scope_type": "system",
            "scope": world.other_system,
        },
    )
    assert r.status_code == 201
    gid = r.json()["id"]
    import time

    time.sleep(1.1)
    mid = now_iso()
    time.sleep(1.1)
    assert (
        client.post(
            f"/v1/admin/role-grants/{gid}/revoke", json={"reason": "left the team"}, headers=adm
        ).status_code
        == 200
    )
    k = keys_of["owner"]

    def at(t: str) -> list[str]:
        r = client.get(
            f"/v1/keys/{k}",
            params={"at": t, "system": world.other_system},
            headers=bearer(ci_token),
        )
        out: list[str] = r.json()["roles_at"]
        return out

    assert at(before) == []
    assert at(mid) == ["engineer"]
    assert at(now_iso(5)) == []
