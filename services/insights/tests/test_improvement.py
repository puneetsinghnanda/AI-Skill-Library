"""Improvement loop: weekly report job and SDD-11 §5.4 routes."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.engine import Engine

from tests.conftest import (
    Person,
    TokenFactory,
    bearer,
    event,
    new_run,
    next_patch,
    now_iso,
    post,
    project,
    run_started,
    skill_version,
    step_decided,
)


@pytest.fixture(scope="module")
def report(
    app: Any,
    token: TokenFactory,
    people: dict[str, Person],
    world: Any,
    keys_of: dict[str, str],
    migrated: Any,
) -> dict[str, int]:
    c = TestClient(app)
    tok = token(people["eng"].oid, people["eng"].roles)
    evs = []
    for i in range(12):  # 12 first attempts on threat-model, 3 pass -> IS-1 = 0.25 < 0.80
        run_id = new_run()
        evs += [
            event("run.started", run_started(world.system), run_id, now_iso(-500 + i)),
            event(
                "step.decided",
                step_decided(
                    "threat",
                    "threat-model",
                    skill_version("threat-model"),
                    1,
                    "PASS" if i < 3 else "RETRY",
                    "Low",
                    keys_of["eng"],
                    6,
                    ["H5"],
                ),
                run_id,
                now_iso(-400 + i),
            ),
        ]
    post(c, tok, evs, strict=True)
    project(migrated)
    from app.jobs import improvement_report

    return improvement_report.run(migrated)


def test_report_job_opens_flag(report: dict[str, int], owner_db: Engine) -> None:
    assert report["reports"] >= 1
    with owner_db.connect() as c:
        f = c.execute(
            text(
                "SELECT signal, value, status FROM skill_flags WHERE skill_id = 'threat-model' "
                "AND signal = 'IS-1'"
            )
        ).one()
    assert f.status == "OPEN" and float(f.value) == pytest.approx(0.25)


def test_flag_routes(
    client: TestClient,
    token: TokenFactory,
    people: dict[str, Person],
    report: dict[str, int],
    world: Any,
) -> None:
    adm = bearer(token(people["admin"].oid, people["admin"].roles, client="portal"))
    # give the owner the threat-model skill too
    r = client.post(
        "/v1/admin/role-grants",
        headers=adm,
        json={
            "user": people["owner"].pseudonym,
            "role": "skill_owner",
            "scope_type": "skill",
            "scope": "threat-model",
        },
    )
    assert r.status_code in (201, 400)
    owner = bearer(token(people["owner"].oid, people["owner"].roles, client="portal"))
    eng = bearer(token(people["eng"].oid, people["eng"].roles, client="portal"))
    flags = client.get("/v1/improvement/flags?skill=threat-model", headers=owner).json()["data"][
        "items"
    ]
    assert flags and flags[0]["signal"] == "IS-1"
    assert client.get("/v1/improvement/flags", headers=eng).status_code == 403
    rep = client.get("/v1/improvement/skills/threat-model", headers=owner).json()
    assert rep["data"]["header"]["skill_id"] == "threat-model" and rep["clusters"] and rep["flags"]
    assert rep["clusters"][0]["references"][0]["system"] == world.system
    # tsl reads the same report with an Events.Write token
    tsl_owner = bearer(token(people["owner"].oid, people["owner"].roles))
    assert client.get("/v1/improvement/skills/threat-model", headers=tsl_owner).status_code == 200
    fid = flags[0]["flag_id"]
    r = client.patch(f"/v1/improvement/flags/{fid}", json={"status": "DISMISSED"}, headers=owner)
    assert r.status_code == 400
    r = client.patch(f"/v1/improvement/flags/{fid}", json={"status": "IN_PROGRESS"}, headers=eng)
    assert r.status_code == 403
    r = client.patch(f"/v1/improvement/flags/{fid}", json={"status": "IN_PROGRESS"}, headers=owner)
    assert r.status_code == 200 and r.json()["data"]["status"] == "IN_PROGRESS"
    r = client.patch(
        f"/v1/improvement/flags/{fid}",
        json={"status": "DISMISSED", "reason": "known gap"},
        headers=owner,
    )
    assert r.status_code == 400  # only OPEN flags may be dismissed
    el = bearer(token(people["englead"].oid, people["englead"].roles, client="portal"))
    assert client.get("/v1/improvement/flags", headers=el).status_code == 200


def test_improvement_proposed_event(
    client: TestClient,
    token: TokenFactory,
    people: dict[str, Person],
    report: dict[str, int],
    migrated: Any,
    owner_db: Engine,
) -> None:
    from app.crypto import ulid

    with owner_db.connect() as c:
        fid = c.execute(
            text("SELECT id FROM skill_flags WHERE skill_id = 'threat-model' LIMIT 1")
        ).scalar_one()
    imp = ulid("imp")
    post(
        client,
        token(people["owner"].oid, people["owner"].roles),
        [
            event(
                "improvement.proposed",
                {
                    "improvement_id": imp,
                    "skill": "threat-model",
                    "from_version": skill_version("threat-model"),
                    "to_version": next_patch(skill_version("threat-model")),
                    "flag_ids": [fid],
                    "before_pass_rate": 0.8,
                    "after_pass_rate": 0.95,
                    "cases_added": 2,
                },
            )
        ],
        strict=True,
    )
    project(migrated)
    with owner_db.connect() as c:
        assert (
            c.execute(text("SELECT state FROM improvements WHERE id = :i"), {"i": imp}).scalar_one()
            == "proposed"
        )
        assert (
            c.execute(text("SELECT status FROM skill_flags WHERE id = :f"), {"f": fid}).scalar_one()
            == "PROPOSED"
        )
