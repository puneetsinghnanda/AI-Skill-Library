"""Token validation matrix (SDD-07 ID-T-10, SDD-08 §12 Auth, TC-INS-003). No bypass exists."""

from __future__ import annotations

from typing import Any

import jwt
import pytest
from fastapi.testclient import TestClient

from tests.conftest import AUDIENCE, Keys, Person, TokenFactory, bearer, event, now_iso


def _hook(sid: str) -> dict[str, Any]:
    return event(
        "hook.decision", {"hook": "pre-tool", "decision": "allow", "code": None, "session_id": sid}
    )


def test_missing_token(client: TestClient) -> None:
    r = client.post("/v1/events", json={"events": []})
    assert r.status_code == 401
    assert r.json()["code"] == "E-ING-07"
    r = client.get("/v1/status")
    assert r.status_code == 401 and r.json()["code"] == "E-API-02"
    assert r.headers["content-type"].startswith("application/problem+json")


@pytest.mark.parametrize(
    "kw",
    [
        {"exp_delta": -3600},
        {"aud": "99999999-0000-4000-8000-000000000000"},
        {"tid": "22222222-0000-4000-8000-000000000000"},
        {"client": "33333333-0000-4000-8000-000000000000"},
    ],
)
def test_bad_tokens_rejected(
    client: TestClient, token: TokenFactory, people: dict[str, Person], kw: dict[str, Any]
) -> None:
    p = people["eng"]
    r = client.post(
        "/v1/events", json={"events": [_hook("s-1")]}, headers=bearer(token(p.oid, p.roles, **kw))
    )
    assert r.status_code == 401
    assert r.json()["code"] == "E-ING-07"


def test_wrong_signing_key(
    client: TestClient, token: TokenFactory, signing: Keys, people: dict[str, Person]
) -> None:
    p = people["eng"]
    tok = token(p.oid, p.roles, key=signing.other)
    assert client.post("/v1/events", json={"events": []}, headers=bearer(tok)).status_code == 401
    tok = token(p.oid, p.roles, key=signing.other, kid="unknown-kid")
    assert client.post("/v1/events", json={"events": []}, headers=bearer(tok)).status_code == 401


def test_alg_none_and_hs256_refused(client: TestClient, people: dict[str, Person]) -> None:
    p = people["eng"]
    claims = {"iss": "x", "aud": AUDIENCE, "oid": p.oid}
    none_tok = jwt.encode(claims, None, algorithm="none")  # type: ignore[arg-type]
    hs_tok = jwt.encode(claims, "secret-secret-secret-secret-1234", algorithm="HS256")
    for t in (none_tok, hs_tok, "not-a-jwt"):
        assert client.post("/v1/events", json={"events": []}, headers=bearer(t)).status_code == 401


def test_portal_token_on_ingest_and_tsl_token_on_read(
    client: TestClient, token: TokenFactory, people: dict[str, Person]
) -> None:
    p = people["eng"]
    r = client.post(
        "/v1/events", json={"events": []}, headers=bearer(token(p.oid, p.roles, client="portal"))
    )
    assert r.status_code == 401
    r = client.get("/v1/runs", headers=bearer(token(p.oid, p.roles, client="tsl")))
    assert r.status_code == 401 and r.json()["code"] == "E-API-02"
    # portal token with only Portal.Read cannot use a Portal.Write route
    r = client.post(
        "/v1/admin/projects",
        json={"client": "CL-DEMO", "code": "PRJ-X1"},
        headers=bearer(
            token(people["admin"].oid, people["admin"].roles, client="portal", scp="Portal.Read")
        ),
    )
    assert r.status_code == 401


def test_no_app_role_is_403(client: TestClient, token: TokenFactory) -> None:
    import uuid

    r = client.get("/v1/me", headers=bearer(token(str(uuid.uuid4()), [], client="portal")))
    assert r.status_code == 403 and r.json()["code"] == "E-AUTH-08"


def test_business_token_cannot_send_events(
    client: TestClient, token: TokenFactory, people: dict[str, Person]
) -> None:
    p = people["biz"]
    r = client.post(
        "/v1/events", json={"events": [_hook("s-2")]}, headers=bearer(token(p.oid, p.roles))
    )
    assert r.status_code == 403 and r.json()["code"] == "E-AUTH-08"


def test_ci_token_only_ci_verified(client: TestClient, ci_token: str, world: Any) -> None:
    from tests.conftest import new_run, run_started

    evs = [
        event("run.started", run_started(world.system), new_run()),
        event(
            "ci.verified",
            {
                "repo": world.repo,
                "number": 9001,
                "result": "pass",
                "codes": [],
                "head_sha": "a" * 40,
            },
        ),
    ]
    r = client.post("/v1/events", json={"events": evs}, headers=bearer(ci_token))
    assert r.status_code == 202, r.text
    body = r.json()
    assert body["accepted"] == 1
    assert body["rejected"][0]["code"] == "E-ING-05"


def test_otel_token_not_accepted_on_events(client: TestClient, otel_token: str) -> None:
    r = client.post("/v1/events", json={"events": []}, headers=bearer(otel_token))
    assert r.status_code == 401


def test_revoked_ingest_token(client: TestClient, migrated: Any) -> None:
    from app.auth import ingest_tokens
    from app.db import tx

    with tx("app", migrated) as conn:
        tid, tok = ingest_tokens.create(conn, "ci", "temp")
        ingest_tokens.revoke(conn, tid)
    assert client.post("/v1/events", json={"events": []}, headers=bearer(tok)).status_code == 401


def test_rate_limit(
    client: TestClient, token: TokenFactory, people: dict[str, Person], app: Any
) -> None:
    p = people["biz"]
    hdr = bearer(token(p.oid, p.roles, client="portal"))
    codes = [client.get("/v1/status", headers=hdr).status_code for _ in range(80)]
    assert 429 in codes
    app.state.rate_limiter._b.clear()


def test_clock_now_helper() -> None:
    assert now_iso().endswith("Z")
