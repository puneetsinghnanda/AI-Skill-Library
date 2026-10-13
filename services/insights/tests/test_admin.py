"""Admin routes (SDD-13 §7.2), systems record (SDD-12 §5.3) and the client denylist (SEC-01 §7.4)."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.engine import Engine

from tests.conftest import Person, TokenFactory, bearer, key_registration


def _p(token: TokenFactory, p: Person) -> dict[str, str]:
    return bearer(token(p.oid, p.roles, client="portal"))


def test_admin_only(client: TestClient, token: TokenFactory, people: dict[str, Person]) -> None:
    r = client.post(
        "/v1/admin/projects",
        json={"client": "CL-DEMO", "code": "PRJ-NOPE"},
        headers=_p(token, people["lead"]),
    )
    assert r.status_code == 403 and r.json()["code"] == "E-API-03"


def test_self_grant_refused(
    client: TestClient, token: TokenFactory, people: dict[str, Person], world: Any
) -> None:
    a = people["admin"]
    r = client.post(
        "/v1/admin/role-grants",
        headers=_p(token, a),
        json={
            "user": a.pseudonym,
            "role": "tech_lead",
            "scope_type": "system",
            "scope": world.system,
        },
    )
    assert r.status_code == 403 and r.json()["code"] == "E-ADM-01"


def test_ceiling_and_scope_checks(
    client: TestClient, token: TokenFactory, people: dict[str, Person], world: Any
) -> None:
    h = _p(token, people["admin"])
    r = client.post(
        "/v1/admin/role-grants",
        headers=h,
        json={
            "user": people["biz"].pseudonym,
            "role": "engineer",
            "scope_type": "system",
            "scope": world.system,
        },
    )
    assert r.status_code == 400  # Business app role does not allow engineer (SDD-07 §3.3)
    r = client.post(
        "/v1/admin/role-grants",
        headers=h,
        json={
            "user": people["eng"].pseudonym,
            "role": "engineer",
            "scope_type": "system",
            "scope": "SYS-NONE",
        },
    )
    assert r.status_code == 404
    r = client.post(
        "/v1/admin/role-grants",
        headers=h,
        json={"user": people["eng"].pseudonym, "role": "engineer", "scope_type": "org"},
    )
    assert r.status_code == 400


def test_consent_and_system_record(
    client: TestClient, token: TokenFactory, people: dict[str, Person], world: Any, owner_db: Engine
) -> None:
    h = _p(token, people["admin"])
    lead = bearer(token(people["lead"].oid, people["lead"].roles))
    rec = client.get(f"/v1/systems/{world.system}", headers=lead).json()
    assert (
        rec["consent"]["recorded"] is True and rec["client"] == "CL-DEMO" and rec["product_repos"]
    )
    assert client.get(f"/v1/systems/{world.other_system}", headers=lead).status_code == 403
    assert client.get("/v1/systems/SYS-NONE", headers=lead).status_code == 404
    assert (
        client.post(
            "/v1/admin/clients",
            headers=h,
            json={"code": "CL-T2", "display_name": "Zephyrine Quarto"},
        ).status_code
        == 201
    )
    r = client.post(
        "/v1/admin/clients/CL-T2/consent",
        headers=h,
        json={"consent_ref": "CONSENT-0002", "scope": ["code_processing"]},
    )
    assert r.status_code == 200
    r = client.post("/v1/admin/clients/CL-T2/consent", headers=h, json={"action": "withdraw"})
    assert r.status_code == 200 and r.json()["withdrawn_at"]
    assert (
        client.post(
            "/v1/admin/clients", headers=h, json={"code": "CL-T2", "display_name": "x"}
        ).status_code
        == 400
    )
    with owner_db.connect() as c:
        actions = set(c.execute(text("SELECT DISTINCT action FROM audit_log")).scalars())
    assert {
        "client_create",
        "consent_record",
        "consent_withdraw",
        "project_create",
        "system_create",
        "role_grant",
        "denylist_change",
    } <= actions
    d = client.get("/v1/policy/denylist", headers=lead).json()
    assert d["version"] >= 2 and d["salt"] and len(d["hashes"]) > 3


def test_deactivate_user(
    client: TestClient, token: TokenFactory, people: dict[str, Person], app: Any, owner_db: Engine
) -> None:
    import uuid

    from tests.conftest import Person as P

    temp = P(str(uuid.uuid4()), ["Engineer"], "Indigo Temp")
    me = client.get("/v1/me", headers=bearer(token(temp.oid, temp.roles))).json()
    body, _ = key_registration(temp.oid)
    assert (
        client.post("/v1/keys", json=body, headers=bearer(token(temp.oid, temp.roles))).status_code
        == 201
    )
    r = client.post(
        f"/v1/admin/users/{me['pseudonym']}/deactivate",
        json={"reason": "left the company"},
        headers=_p(token, people["admin"]),
    )
    assert r.status_code == 200 and r.json()["keys_revoked"] == [body["key_id"]]
    with owner_db.connect() as c:
        assert (
            c.execute(
                text("SELECT revoked_reason FROM keys WHERE key_id = :k"), {"k": body["key_id"]}
            ).scalar_one()
            == "offboarded"
        )
        assert (
            c.execute(
                text(
                    "SELECT count(*) FROM role_grants g JOIN users u ON u.id = g.user_id "
                    "WHERE u.pseudonym = :p AND g.revoked_at IS NULL"
                ),
                {"p": me["pseudonym"]},
            ).scalar_one()
            == 0
        )
    r = client.get("/v1/me", headers=bearer(token(temp.oid, temp.roles)))
    assert r.status_code == 403 and r.json()["code"] == "E-AUTH-08"


def test_app_role_sync_revokes(
    client: TestClient, token: TokenFactory, people: dict[str, Person], world: Any, owner_db: Engine
) -> None:
    """SDD-07 §3.4: a token without TechLead revokes tech_lead grants."""
    import uuid

    oid = str(uuid.uuid4())
    me = client.get("/v1/me", headers=bearer(token(oid, ["TechLead"], client="portal"))).json()
    r = client.post(
        "/v1/admin/role-grants",
        headers=_p(token, people["admin"]),
        json={
            "user": me["pseudonym"],
            "role": "tech_lead",
            "scope_type": "system",
            "scope": world.other_system,
        },
    )
    assert r.status_code == 201
    me2 = client.get("/v1/me", headers=bearer(token(oid, ["Engineer"], client="portal"))).json()
    assert all(g["role"] != "tech_lead" for g in me2["grants"])
    with owner_db.connect() as c:
        assert (
            c.execute(
                text(
                    "SELECT count(*) FROM audit_log WHERE action = 'role_sync_revoke' AND target = :g"
                ),
                {"g": r.json()["id"]},
            ).scalar_one()
            == 1
        )
