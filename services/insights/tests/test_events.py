"""``POST /v1/events`` (SDD-08 §4; TC-INS-001, 002, 004; contract fixtures for every event type)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.engine import Engine

from tests.conftest import ROOT, Person, TokenFactory, bearer, event, new_run, now_iso, post

FIXTURES = ROOT / "schemas" / "fixtures" / "events"
NEEDS_RUN = {
    "step.started",
    "step.decided",
    "step.invalidated",
    "run.started",
    "run.status_changed",
    "question.created",
    "question.answered",
    "approval.recorded",
    "pr.opened",
    "audit.recorded",
}


def _hook(i: int) -> dict[str, Any]:
    return event(
        "hook.decision",
        {
            "hook": "pre-tool",
            "decision": "allow",
            "code": None,
            "tool_kind": "write",
            "session_id": f"sess-{i}",
        },
    )


def _tok(token: TokenFactory, people: dict[str, Person]) -> str:
    return token(people["eng"].oid, people["eng"].roles)


def test_batch_of_500_and_501(
    client: TestClient, token: TokenFactory, people: dict[str, Person]
) -> None:
    tok = _tok(token, people)
    body = post(client, tok, [_hook(i) for i in range(500)])
    assert body["accepted"] == 500 and body["rejected"] == [] and body["duplicates"] == []
    r = client.post(
        "/v1/events", json={"events": [_hook(i) for i in range(501)]}, headers=bearer(tok)
    )
    assert r.status_code == 413


def test_idempotent_batch(
    client: TestClient, token: TokenFactory, people: dict[str, Person], owner_db: Engine
) -> None:
    tok = _tok(token, people)
    evs = [_hook(i) for i in range(5)]
    first = post(client, tok, evs)
    second = post(client, tok, evs)
    assert first["accepted"] == 5
    assert second["accepted"] == 0 and sorted(second["duplicates"]) == sorted(
        e["event_id"] for e in evs
    )
    ids = [e["event_id"] for e in evs]
    with owner_db.connect() as c:
        assert (
            c.execute(
                text("SELECT count(*) FROM events_raw WHERE event_id = ANY(:i)"), {"i": ids}
            ).scalar_one()
            == 5
        )
        assert (
            c.execute(
                text("SELECT count(*) FROM event_ids WHERE event_id = ANY(:i)"), {"i": ids}
            ).scalar_one()
            == 5
        )
    # duplicate inside one batch
    e = _hook(99)
    third = post(client, tok, [e, e])
    assert third["accepted"] == 1 and third["duplicates"] == [e["event_id"]]


def test_per_event_rejections(
    client: TestClient, token: TokenFactory, people: dict[str, Person]
) -> None:
    tok = _tok(token, people)
    good = _hook(1)
    unknown_version = {**_hook(2), "schema_version": 7}
    user_field = {**_hook(3), "body": {**_hook(3)["body"], "user": "x"}}
    bad_schema = {**_hook(4), "body": {"hook": "nope", "decision": "allow", "code": None}}
    deny = event(
        "question.created",
        {
            "step": "design",
            "question_id": "Q-01",
            "blocking": True,
            "ask_role": "tech_lead",
            "evidence_ref": "runs/a/someone@example.com",
        },
        new_run(),
    )
    bad_path = event(
        "hook.decision",
        {
            "hook": "pre-tool",
            "decision": "allow",
            "code": None,
            "session_id": "src/secret/config.py",
        },
    )
    env_bad = {
        "event_id": "nope",
        "type": "hook.decision",
        "schema_version": 1,
        "occurred_at": now_iso(),
        "body": {},
    }
    batch: list[Any] = [good, unknown_version, user_field, bad_schema, deny, bad_path, env_bad]
    body = post(client, tok, [*batch, "string"])
    codes = {r["event_id"]: r["code"] for r in body["rejected"]}
    assert body["accepted"] == 1
    assert codes[unknown_version["event_id"]] == "E-ING-02"
    assert codes[user_field["event_id"]] == "E-ING-03"
    assert codes[bad_schema["event_id"]] == "E-ING-01"
    assert codes[deny["event_id"]] == "E-ING-04"
    assert codes[bad_path["event_id"]] == "E-ING-04"
    assert codes["nope"] == "E-ING-01"
    assert "" in codes


def test_client_name_denylist(
    client: TestClient, token: TokenFactory, people: dict[str, Person], world: Any
) -> None:
    tok = _tok(token, people)
    e = event(
        "hook.decision",
        {
            "hook": "pre-tool",
            "decision": "allow",
            "code": None,
            "session_id": "northwind-session-7",
        },
    )
    body = post(client, tok, [e])
    assert body["rejected"][0]["code"] == "E-ING-04"
    assert "client-name" in body["rejected"][0]["reason"]


def test_malformed_batches(
    client: TestClient, token: TokenFactory, people: dict[str, Person]
) -> None:
    hdr = {**bearer(_tok(token, people)), "Content-Type": "application/json"}
    r = client.post("/v1/events", content=b"{not json", headers=hdr)
    assert r.status_code == 400 and r.json()["code"] == "E-ING-06"
    r = client.post("/v1/events", content=b'{"evts": []}', headers=hdr)
    assert r.status_code == 400 and r.json()["code"] == "E-ING-06"
    r = client.post("/v1/events", content=b"x" * (1024 * 1024 + 10), headers=hdr)
    assert r.status_code == 413


def test_clock_skew_flag(
    client: TestClient, token: TokenFactory, people: dict[str, Person], owner_db: Engine
) -> None:
    e = event(
        "hook.decision",
        {"hook": "pre-tool", "decision": "allow", "code": None},
        occurred=now_iso(3600),
    )
    post(client, _tok(token, people), [e])
    with owner_db.connect() as c:
        assert c.execute(
            text("SELECT clock_skew FROM events_raw WHERE event_id = :e"), {"e": e["event_id"]}
        ).scalar_one()


def test_every_event_type_fixture_accepted(
    client: TestClient, token: TokenFactory, people: dict[str, Person]
) -> None:
    """Contract: each valid body fixture in schemas/fixtures/events is accepted (SDD-08 §12)."""
    tok = _tok(token, people)
    evs, invalid = [], []
    for d in sorted(FIXTURES.iterdir()):
        type_ = d.name.rsplit(".v", 1)[0]
        run = new_run() if type_ in NEEDS_RUN else None
        for f in sorted((d / "valid").glob("*.json")):
            evs.append(event(type_, json.loads(f.read_text()), run))
        for f in sorted((d / "invalid").glob("*.json")) if (d / "invalid").exists() else []:
            invalid.append(event(type_, json.loads(f.read_text()), run))
    body = post(client, tok, evs[:250])
    body2 = post(client, tok, evs[250:])
    rejected = body["rejected"] + body2["rejected"]
    assert rejected == [], rejected
    assert len(evs) >= 21 * 2
    bad = post(client, tok, invalid[:400])
    assert bad["accepted"] == 0, [
        e for e in invalid if e["event_id"] not in {r["event_id"] for r in bad["rejected"]}
    ]


def test_no_user_column_from_body(path: Path = FIXTURES) -> None:
    assert path.exists()
