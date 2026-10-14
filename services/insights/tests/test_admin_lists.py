"""Admin list routes (SDD-13 §5.3, §7.2; SDD-09 §4.16): admin only, pagination, filters, RD-1."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.engine import Engine

from tests.conftest import Person, TokenFactory, bearer

LISTS = [
    "/v1/admin/clients",
    "/v1/admin/projects",
    "/v1/admin/systems",
    "/v1/admin/role-grants",
    "/v1/admin/users",
]


def _h(token: TokenFactory, p: Person, scp: str | None = None) -> dict[str, str]:
    return bearer(token(p.oid, p.roles, client="portal", scp=scp))


def _all(c: TestClient, url: str, h: dict[str, str], /, **q: Any) -> list[dict[str, Any]]:
    """Walks every page with limit=1 and checks the cursor chain ends."""
    out: list[dict[str, Any]] = []
    cursor: str | None = None
    for _ in range(500):
        params = {**q, "limit": 1, **({"cursor": cursor} if cursor else {})}
        r = c.get(url, headers=h, params=params)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["page"]["limit"] == 1 and len(body["data"]["items"]) <= 1
        out += body["data"]["items"]
        cursor = body["page"]["next_cursor"]
        if not cursor:
            return out
    raise AssertionError("cursor chain did not end")


@pytest.mark.parametrize("who", ["lead", "eng", "biz", "englead", "owner"])
def test_lists_are_admin_only(
    client: TestClient, token: TokenFactory, people: dict[str, Person], world: Any, who: str
) -> None:
    h = _h(token, people[who])
    for url in [*LISTS, f"/v1/admin/users/{people['eng'].pseudonym}/keys"]:
        r = client.get(url, headers=h)
        assert r.status_code == 403 and r.json()["code"] == "E-API-03", (url, r.text)


def test_lists_need_portal_read(
    client: TestClient, token: TokenFactory, people: dict[str, Person], world: Any
) -> None:
    a = people["admin"]
    tsl = bearer(token(a.oid, a.roles))  # Events.Write from tsl: not a portal read token
    assert client.get("/v1/admin/clients", headers=tsl).status_code == 401
    only_write = _h(token, a, scp="Portal.Write")
    assert client.get("/v1/admin/clients", headers=only_write).status_code == 401
    assert client.get("/v1/admin/clients").status_code == 401
    r = client.get("/v1/admin/clients", headers=_h(token, a, scp="Portal.Read"))
    assert r.status_code == 200 and r.headers["cache-control"] == "no-store"


def test_clients_with_consent_status(
    client: TestClient, token: TokenFactory, people: dict[str, Person], world: Any
) -> None:
    h = _h(token, people["admin"])
    for code in ("CL-LSTA", "CL-LSTB"):
        r = client.post("/v1/admin/clients", headers=h, json={"code": code, "display_name": "Zz"})
        assert r.status_code in (201, 400)
    client.post(
        "/v1/admin/clients/CL-LSTA/consent",
        headers=h,
        json={"consent_ref": "CONSENT-0099", "scope": ["code_processing"]},
    )
    client.post("/v1/admin/clients/CL-LSTA/consent", headers=h, json={"action": "withdraw"})
    items = _all(client, "/v1/admin/clients", h)
    by = {c["code"]: c for c in items}
    assert [c["code"] for c in items] == sorted(by)
    assert by["CL-DEMO"]["consent"]["status"] == "recorded"
    assert by["CL-DEMO"]["consent"]["ref"] == "CONSENT-0001" and by["CL-DEMO"]["projects"] >= 1
    assert by["CL-LSTA"]["consent"]["status"] == "withdrawn"
    assert by["CL-LSTB"]["consent"] == {
        "status": "none",
        "ref": None,
        "scope": [],
        "recorded_at": None,
        "withdrawn_at": None,
    }
    assert all("display_name" not in c for c in items)  # codes only, never a client name
    none = client.get("/v1/admin/clients", headers=h, params={"consent": "none"}).json()
    assert {c["consent"]["status"] for c in none["data"]["items"]} == {"none"}
    wd = client.get("/v1/admin/clients", headers=h, params={"consent": "withdrawn"}).json()
    assert "CL-LSTA" in {c["code"] for c in wd["data"]["items"]}
    bad = client.get("/v1/admin/clients", headers=h, params={"consent": "maybe"})
    assert bad.status_code == 400 and bad.json()["code"] == "E-API-01"


def test_projects_and_systems_filter(
    client: TestClient, token: TokenFactory, people: dict[str, Person], world: Any
) -> None:
    h = _h(token, people["admin"])
    projects = _all(client, "/v1/admin/projects", h, client="CL-DEMO")
    assert {"code": world.project, "client": "CL-DEMO", "systems": 2} in projects
    assert all(p["client"] == "CL-DEMO" for p in projects)
    r = client.get("/v1/admin/projects", headers=h, params={"client": "CL-NOPE"})
    assert r.status_code == 200 and r.json()["data"]["items"] == []
    assert client.get("/v1/admin/projects", headers=h, params={"client": "x"}).status_code == 400
    systems = _all(client, "/v1/admin/systems", h, project=world.project)
    assert {s["code"] for s in systems} == {world.system, world.other_system}
    sa = next(s for s in systems if s["code"] == world.system)
    assert sa["client"] == "CL-DEMO" and sa["domain"] == "digital"
    assert sa["product_repos"] == [
        {"name": "orders-api", "github_full_name": "example-org/orders-api", "kind": "product"}
    ]
    by_client = client.get("/v1/admin/systems", headers=h, params={"client": "CL-DEMO"}).json()
    assert {world.system, world.other_system} <= {s["code"] for s in by_client["data"]["items"]}


def test_role_grants_active_and_revoked(
    client: TestClient, token: TokenFactory, people: dict[str, Person], world: Any
) -> None:
    h = _h(token, people["admin"])
    import uuid

    eng2 = people["eng2"].pseudonym
    oid = str(uuid.uuid4())
    temp = client.get("/v1/me", headers=bearer(token(oid, ["TechLead"], client="portal"))).json()
    r = client.post(
        "/v1/admin/role-grants",
        headers=h,
        json={
            "user": temp["pseudonym"],
            "role": "tech_lead",
            "scope_type": "system",
            "scope": world.system,
        },
    )
    assert r.status_code == 201, r.text
    rv = client.post(
        f"/v1/admin/role-grants/{r.json()['id']}/revoke", headers=h, json={"reason": "test"}
    )
    assert rv.status_code == 200
    mine = _all(client, "/v1/admin/role-grants", h, user=temp["pseudonym"], status="revoked")
    assert [g["id"] for g in mine] == [r.json()["id"]] and mine[0]["scope"] == world.system
    every = _all(client, "/v1/admin/role-grants", h, user=eng2)
    assert {g["user"] for g in every} == {eng2}
    sys_grant = next(g for g in every if g["role"] == "engineer")
    assert sys_grant["scope_type"] == "system" and sys_grant["scope"] == world.other_system
    assert sys_grant["status"] == "active" and sys_grant["revoked_at"] is None
    assert sys_grant["granted_by"] == people["admin"].pseudonym
    revoked = _all(client, "/v1/admin/role-grants", h, status="revoked")
    assert revoked and all(g["status"] == "revoked" and g["revoked_at"] for g in revoked)
    active = _all(client, "/v1/admin/role-grants", h, status="active", role="eng_lead")
    assert any(g["scope"] == world.project and g["scope_type"] == "project" for g in active)
    assert all(g["role"] == "eng_lead" and g["status"] == "active" for g in active)
    skill = _all(client, "/v1/admin/role-grants", h, role="skill_owner")
    assert any(g["scope"] == "design" for g in skill)
    # Newest first, and the walk matches one big page.
    big = client.get("/v1/admin/role-grants", headers=h, params={"limit": 100}).json()
    walked = _all(client, "/v1/admin/role-grants", h)
    assert [g["id"] for g in walked][: len(big["data"]["items"])] == [
        g["id"] for g in big["data"]["items"]
    ]
    stamps = [g["granted_at"] for g in big["data"]["items"]]
    assert stamps == sorted(stamps, reverse=True)
    assert (
        client.get("/v1/admin/role-grants", headers=h, params={"role": "boss"}).status_code == 400
    )


def test_cursor_is_bound_to_filters(
    client: TestClient, token: TokenFactory, people: dict[str, Person], world: Any
) -> None:
    h = _h(token, people["admin"])
    first = client.get("/v1/admin/role-grants", headers=h, params={"limit": 1}).json()
    cur = first["page"]["next_cursor"]
    assert cur
    r = client.get(
        "/v1/admin/role-grants", headers=h, params={"limit": 1, "cursor": cur, "status": "active"}
    )
    assert r.status_code == 400 and r.json()["code"] == "E-API-01"
    r = client.get("/v1/admin/users", headers=h, params={"cursor": "%%%"})
    assert r.status_code == 400
    r = client.get("/v1/admin/users", headers=h, params={"limit": 101})
    assert r.status_code == 400


def test_users_roles_active_and_names(
    client: TestClient,
    token: TokenFactory,
    people: dict[str, Person],
    world: Any,
    app: Any,
    owner_db: Engine,
) -> None:
    h = _h(token, people["admin"])
    users = _all(client, "/v1/admin/users", h)
    by = {u["pseudonym"]: u for u in users}
    assert [u["pseudonym"] for u in users] == sorted(by)
    lead = by[people["lead"].pseudonym]
    assert {"engineer", "tech_lead"} <= set(lead["roles"]) and lead["app_roles"] == ["TechLead"]
    assert lead["active"] is True and lead["display_name"] is None
    tl = _all(client, "/v1/admin/users", h, role="tech_lead")
    assert people["lead"].pseudonym in {u["pseudonym"] for u in tl}
    assert all("tech_lead" in u["roles"] for u in tl)
    inactive = client.get("/v1/admin/users", headers=h, params={"active": "false"}).json()
    assert all(u["active"] is False for u in inactive["data"]["items"])

    with owner_db.connect() as c:
        before = c.execute(
            text("SELECT count(*) FROM audit_log WHERE action = 'reveal_names' AND target = :t"),
            {"t": "/v1/admin/users"},
        ).scalar_one()
    named = client.get(
        "/v1/admin/users", headers=h, params={"include": "names", "limit": 100}
    ).json()
    names = {u["pseudonym"]: u["display_name"] for u in named["data"]["items"]}
    assert names.get(people["lead"].pseudonym) == "Casey Lead"
    with owner_db.connect() as c:
        after = c.execute(
            text("SELECT count(*) FROM audit_log WHERE action = 'reveal_names' AND target = :t"),
            {"t": "/v1/admin/users"},
        ).scalar_one()
    assert after == before + 1

    # RD-1 is configuration: with admin outside rd1_name_reveal_roles, no name is returned.
    saved = app.state.settings
    app.state.settings = saved.model_copy(update={"rd1_name_reveal_roles": ("eng_lead",)})
    try:
        r = client.get("/v1/admin/users", headers=h, params={"include": "names", "limit": 100})
    finally:
        app.state.settings = saved
    assert r.status_code == 200
    assert all(u["display_name"] is None for u in r.json()["data"]["items"])


def test_user_keys(
    client: TestClient,
    token: TokenFactory,
    people: dict[str, Person],
    world: Any,
    keys_of: dict[str, str],
) -> None:
    h = _h(token, people["admin"])
    owner = people["owner"].pseudonym
    url = f"/v1/admin/users/{owner}/keys"
    keys = _all(client, url, h)
    k = next(x for x in keys if x["key_id"] == keys_of["owner"])
    assert set(k) == {
        "key_id",
        "device_label",
        "status",
        "created_at",
        "expires_at",
        "revoked_at",
        "revoked_reason",
    }
    assert k["device_label"] == "laptop-test" and k["expires_at"]
    if k["status"] == "active":
        active = client.get(url, headers=h, params={"status": "active"}).json()
        assert keys_of["owner"] in {x["key_id"] for x in active["data"]["items"]}
    revoked = client.get(url, headers=h, params={"status": "revoked"}).json()
    assert all(x["status"] == "revoked" for x in revoked["data"]["items"])
    r = client.get("/v1/admin/users/eng-ffffffff/keys", headers=h)
    assert r.status_code == 404 and r.json()["code"] == "E-API-04"
    assert client.get("/v1/admin/users/nobody/keys", headers=h).status_code == 400
    assert client.get(url, headers=h, params={"status": "lost"}).status_code == 400
