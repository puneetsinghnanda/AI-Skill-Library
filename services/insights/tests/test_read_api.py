"""Read API (SDD-09 §5): every route, role and scope filtering (TC-INS-009), business safety
(TC-POR-002), name rule (RD-1), pagination (TC-INS-011), golden metric checks (SDD-08 §12 Views)."""

from __future__ import annotations

import json
import random
import re
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
    now_iso,
    post,
    project,
    run_started,
    skill_version,
    step_decided,
)

FORBIDDEN = re.compile(r"run_[0-9A-HJKMNP-TV-Z]{26}|SYS-|PRJ-|CL-|\beng-[0-9a-f]{4}")


def portal(token: TokenFactory, p: Person) -> dict[str, str]:
    return bearer(token(p.oid, p.roles, client="portal"))


def _run(
    world_system: str,
    key: str,
    i: int,
    outcome: str,
    merged: bool,
    repo: str,
    ticket: str,
    pod: str | None = None,
) -> tuple[str, list[dict[str, Any]]]:
    run_id = new_run()
    base = -86400 * 3 + i * 60
    evs = [
        event(
            "run.started",
            run_started(world_system, ticket=ticket, pod=pod, session=f"sess-ds-{run_id}"),
            run_id,
            now_iso(base),
        ),
        event(
            "step.started",
            {
                "step": "design",
                "skill": "design",
                "skill_version": skill_version("design"),
                "attempt": 1,
                "seq": 4,
            },
            run_id,
            now_iso(base + 1),
        ),
        event(
            "step.decided",
            step_decided(
                "design",
                "design",
                skill_version("design"),
                1,
                outcome,
                "High" if outcome == "PASS" else "Low",
                key,
                4,
                [] if outcome == "PASS" else ["S1", "REVIEW-MAJOR"],
            ),
            run_id,
            now_iso(base + 2),
        ),
    ]
    if merged:
        n = random.randint(100_000, 999_999)
        evs.append(
            event(
                "pr.opened",
                {"repo": repo, "number": n, "draft": False, "lowest_band": "High"},
                run_id,
                now_iso(base + 3),
            )
        )
        evs.append(
            event(
                "run.status_changed",
                {"from": "RUNNING", "to": "COMPLETED", "reason_code": "pr_opened"},
                run_id,
                now_iso(base + 4),
            )
        )
    return run_id, evs


@pytest.fixture(scope="module")
def dataset(
    app: Any,
    token: TokenFactory,
    people: dict[str, Person],
    world: Any,
    keys_of: dict[str, str],
    migrated: Any,
    owner_db: Engine,
) -> dict[str, Any]:
    client = TestClient(app)
    tok_a = token(people["eng"].oid, people["eng"].roles)
    tok_b = token(people["eng2"].oid, people["eng2"].roles)
    runs_a, runs_b, evs_a, evs_b = [], [], [], []
    for i in range(30):
        r, e = _run(
            world.system,
            keys_of["eng"],
            i,
            "PASS" if i % 3 else "RETRY",
            i % 2 == 0,
            world.repo,
            f"ORD-{i}",
            pod="brownfield-change-pod" if i < 6 else None,
        )
        runs_a.append(r)
        evs_a += e
    for i in range(6):
        r, e = _run(
            world.other_system, keys_of["eng2"], i, "PASS", False, "tickets-web", f"TKT-{i}"
        )
        runs_b.append(r)
        evs_b += e
    # one run of eng paused for approval with an open blocking question
    paused = new_run()
    evs_a += [
        event("run.started", run_started(world.system, ticket="ORD-900"), paused, now_iso(-30)),
        event(
            "question.created",
            {
                "step": "design",
                "question_id": "Q-01",
                "blocking": True,
                "ask_role": "product_owner",
            },
            paused,
            now_iso(-20),
        ),
        event(
            "run.status_changed",
            {"from": "RUNNING", "to": "PAUSED_INPUT", "reason_code": "paused_input"},
            paused,
            now_iso(-10),
        ),
    ]
    gate_run = new_run()
    evs_b += [
        event("run.started", run_started(world.system, ticket="ORD-901"), gate_run, now_iso(-30)),
        event(
            "run.status_changed",
            {
                "from": "RUNNING",
                "to": "PAUSED_APPROVAL",
                "reason_code": "paused_approval",
                "gate": "G-design",
                "step": "design",
            },
            gate_run,
            now_iso(-10),
        ),
    ]
    for chunk in range(0, len(evs_a), 200):
        post(client, tok_a, evs_a[chunk : chunk + 200], strict=True)
    post(client, tok_b, evs_b, strict=True)
    project(migrated)
    # merge the PRs through the webhook-equivalent columns (owner write keeps the test short)
    with owner_db.begin() as c:
        c.execute(
            text(
                "UPDATE pull_requests SET state = 'merged', merged_at = now() - interval '1 day' "
                "WHERE run_id = ANY(:r)"
            ),
            {"r": runs_a},
        )
    from app.jobs import refresh_views

    refresh_views.run(migrated)
    return {"runs_a": runs_a, "runs_b": runs_b, "paused": paused, "gate_run": gate_run}


# ----------------------------------------------------------------------------- business (class A)
CLASS_A = [
    "/v1/catalogue/summary",
    "/v1/catalogue/skills",
    "/v1/catalogue/skills/design",
    "/v1/catalogue/releases",
    "/v1/catalogue/pods",
    "/v1/capability-map",
    "/v1/capability-map?audience=shared",
    "/v1/insights/business",
    "/v1/insights/business?period=12m",
    "/v1/insights/business?period=all",
]
CLASS_B = [
    "/v1/runs",
    "/v1/me/home",
    "/v1/insights/engineering/runs",
    "/v1/insights/engineering/skills",
    "/v1/insights/engineering/usage",
    "/v1/insights/engineering/health",
    "/v1/catalogue/skills/design/quality",
    "/v1/pods/brownfield-change-pod/runs",
    "/v1/pods/brownfield-change-pod/fit?system=SYS-ORD",
]


def test_business_sees_aggregates_only(
    client: TestClient, token: TokenFactory, people: dict[str, Person], dataset: dict[str, Any]
) -> None:
    h = portal(token, people["biz"])
    me = client.get("/v1/me", headers=h).json()["data"]
    assert (
        me["default_view"] == "business"
        and me["can_switch_view"] is False
        and me["scope"]["projects"] == []
    )
    for path in CLASS_A:
        r = client.get(path, headers=h)
        assert r.status_code == 200, (path, r.text)
        assert not FORBIDDEN.search(json.dumps(r.json())), (
            path,
            FORBIDDEN.search(json.dumps(r.json())),
        )
        assert r.json()["meta"]["scope"] == {"level": "org"}
    for path in [*CLASS_B, f"/v1/runs/{dataset['runs_a'][0]}"]:
        r = client.get(path, headers=h)
        assert r.status_code == 403, (path, r.status_code)
        assert r.json()["code"] == "E-API-03"
    assert client.get("/v1/status", headers=h).status_code == 200


def test_business_numbers(
    client: TestClient,
    token: TokenFactory,
    people: dict[str, Person],
    dataset: dict[str, Any],
    owner_db: Engine,
) -> None:
    data = client.get(
        "/v1/insights/business?period=90d", headers=portal(token, people["biz"])
    ).json()["data"]
    with owner_db.connect() as c:
        gold_ftp = c.execute(
            text(
                "SELECT count(*) FILTER (WHERE outcome IN ('PASS','PASS-WITH-FINDINGS'))::numeric / count(*) FROM steps "
                "WHERE attempt = 1 AND decided_at >= current_date - 89"
            )
        ).scalar_one()
        gold_merged = c.execute(
            text(
                "SELECT count(*) FROM pull_requests WHERE merged_at::date >= current_date - 89 "
                "AND run_id IS NOT NULL"
            )
        ).scalar_one()
        gold_eng = c.execute(
            text(
                "SELECT count(DISTINCT user_id) FROM runs WHERE started_at::date >= current_date - 89"
            )
        ).scalar_one()
    assert data["first_try_pass"]["value"] == pytest.approx(float(gold_ftp), abs=1e-3)  # M-03
    assert data["prs_delivered"]["value"] == gold_merged  # M-04
    assert data["engineers_using"]["value"] == gold_eng  # M-08
    assert data["systems_served"]["value"] >= 2 and data["active_pods"]["value"] >= 1
    assert len(data["prs_by_month"]) == 6


def test_capability_map_shared_hides_pilot(
    client: TestClient, token: TokenFactory, people: dict[str, Person]
) -> None:
    h = portal(token, people["biz"])
    shared = client.get("/v1/capability-map?audience=shared", headers=h).json()["data"]
    internal = client.get("/v1/capability-map?audience=internal", headers=h).json()["data"]
    statuses = {x["status"] for r in shared["rows"] for v in r["cells"].values() for x in v}
    assert statuses == {"production"}
    assert "pilot" in {
        x["status"] for r in internal["rows"] for v in r["cells"].values() for x in v
    }
    assert all(any(x for v in r["cells"].values() for x in v) for r in shared["rows"])


def test_catalogue_routes(
    client: TestClient, token: TokenFactory, people: dict[str, Person]
) -> None:
    hb, he = portal(token, people["biz"]), portal(token, people["eng"])
    s = client.get("/v1/catalogue/summary", headers=hb).json()["data"]
    assert s["skills_in_production"] >= 10 and len(s["roles"]) == 8
    biz_ids = {
        x["id"]
        for x in client.get("/v1/catalogue/skills?limit=100", headers=hb).json()["data"]["items"]
    }
    eng_ids = {
        x["id"]
        for x in client.get("/v1/catalogue/skills?limit=100", headers=he).json()["data"]["items"]
    }
    assert (
        "requirement-review" not in biz_ids and "requirement-review" in eng_ids
    )  # draft: engineers only
    assert client.get("/v1/catalogue/skills/requirement-review", headers=hb).status_code == 404
    q = client.get("/v1/catalogue/skills?q=threat", headers=hb).json()["data"]["items"]
    assert [x["id"] for x in q] == ["threat-model"]
    d = client.get("/v1/catalogue/skills/design", headers=hb).json()["data"]
    assert (
        d["workflows"]
        and d["current"]["version"] == skill_version("design")
        and "cases" in d["eval"]
    )
    rel = client.get("/v1/catalogue/releases?limit=1", headers=hb).json()
    assert rel["data"]["items"][0]["tag"] == "v0.1.0"
    # cursor paging over skills
    p1 = client.get("/v1/catalogue/skills?limit=5", headers=he).json()
    p2 = client.get(
        f"/v1/catalogue/skills?limit=5&cursor={p1['page']['next_cursor']}", headers=he
    ).json()
    assert not {x["id"] for x in p1["data"]["items"]} & {x["id"] for x in p2["data"]["items"]}
    bad = client.get(
        f"/v1/catalogue/skills?limit=5&role=developer&cursor={p1['page']['next_cursor']}",
        headers=he,
    )
    assert bad.status_code == 400 and bad.json()["code"] == "E-API-01"
    assert client.get("/v1/catalogue/skills?period=7d", headers=he).status_code == 400


# ----------------------------------------------------------------------------- engineer scope
def test_engineer_sees_own_system_only(
    client: TestClient,
    token: TokenFactory,
    people: dict[str, Person],
    world: Any,
    dataset: dict[str, Any],
) -> None:
    h = portal(token, people["eng"])
    me = client.get("/v1/me", headers=h).json()
    assert me["data"]["default_view"] == "engineer"
    assert [s["code"] for p in me["data"]["scope"]["projects"] for s in p["systems"]] == [
        world.system
    ]
    assert {"role": "engineer", "scope": f"system:{world.system}"} in me["grants"]
    items = []
    cur = None
    while True:
        url = "/v1/runs?limit=7" + (f"&cursor={cur}" if cur else "")
        body = client.get(url, headers=h).json()
        items += body["data"]["items"]
        cur = body["page"]["next_cursor"]
        if not cur:
            break
    ids = [x["run_id"] for x in items]
    assert len(ids) == len(set(ids))  # no duplicates across pages
    assert set(dataset["runs_a"]) <= set(ids)
    assert not set(dataset["runs_b"]) & set(ids)
    assert {x["system"] for x in items} == {world.system}
    assert all(x["engineer"]["display_name"] is None for x in items)
    r = client.get(f"/v1/runs/{dataset['runs_b'][0]}", headers=h)
    assert r.status_code == 404 and r.json()["code"] == "E-API-04"
    assert client.get(f"/v1/runs?system={world.other_system}", headers=h).status_code == 404
    assert client.get(f"/v1/runs?project={world.project}&status=open", headers=h).status_code == 200


def test_run_detail(
    client: TestClient, token: TokenFactory, people: dict[str, Person], dataset: dict[str, Any]
) -> None:
    h = portal(token, people["eng"])
    d = client.get(f"/v1/runs/{dataset['runs_a'][0]}", headers=h).json()["data"]
    assert d["run"]["status"] == "COMPLETED" and d["run"]["next_action"]["text"].startswith("PR #")
    design = next(s for s in d["steps"] if s["step_id"] == "design")
    assert (
        design["attempt_count"] == 1
        and design["attempts"][0]["record"]["decided_by"] == "tsl@0.1.0"
    )
    assert d["pull_requests"][0]["state"] == "merged"
    pr_step = next((s for s in d["steps"] if s["kind"] == "pr"), None)
    assert pr_step is not None and pr_step["outcome"] == "merged"  # from the run's PRs
    assert d["links"]["companion_runs_url"].endswith(dataset["runs_a"][0])
    p = client.get(f"/v1/runs/{dataset['paused']}", headers=h).json()["data"]
    assert p["questions"][0]["question_id"] == "Q-01" and "file_url" in p["questions"][0]
    assert "text" not in p["questions"][0]  # RD-3: no question text in the cloud


def test_name_rule(
    client: TestClient,
    token: TokenFactory,
    people: dict[str, Person],
    dataset: dict[str, Any],
    owner_db: Engine,
) -> None:
    run = dataset["runs_a"][0]
    lead = client.get(
        f"/v1/runs/{run}?include=names", headers=portal(token, people["lead"])
    ).json()["data"]
    assert lead["run"]["engineer"]["display_name"] is None  # RD-1 (a): tech_lead does not see names
    with owner_db.connect() as c:
        before = c.execute(
            text("SELECT count(*) FROM audit_log WHERE action = 'reveal_names'")
        ).scalar_one()
    el = client.get(
        f"/v1/runs/{run}?include=names", headers=portal(token, people["englead"])
    ).json()["data"]
    assert el["run"]["engineer"]["display_name"] == "Devon Engineer"
    lst = client.get(
        "/v1/runs?include=names&limit=5", headers=portal(token, people["englead"])
    ).json()["data"]
    assert all(x["engineer"]["display_name"] for x in lst["items"])
    plain = client.get(f"/v1/runs/{run}", headers=portal(token, people["englead"])).json()["data"]
    assert plain["run"]["engineer"]["display_name"] is None
    with owner_db.connect() as c:
        after = c.execute(
            text("SELECT count(*) FROM audit_log WHERE action = 'reveal_names'")
        ).scalar_one()
    assert after == before + 2
    assert "email" not in json.dumps(el)


def test_read_role_privileges(owner_db: Engine, migrated: Any) -> None:
    """insights_read cannot read raw intake or encrypted columns (SDD-08 §9.4, §12 Privacy)."""
    from sqlalchemy.exc import ProgrammingError

    from app.db import engine

    eng = engine("read", migrated)
    for sql in (
        "SELECT 1 FROM events_raw LIMIT 1",
        "SELECT 1 FROM otel_events LIMIT 1",
        "SELECT display_name_enc FROM users LIMIT 1",
        "SELECT 1 FROM ingest_tokens LIMIT 1",
        "SELECT secret_enc FROM github_hooks LIMIT 1",
        "SELECT display_name_enc FROM clients LIMIT 1",
    ):
        with eng.connect() as c, pytest.raises(ProgrammingError):
            c.execute(text(sql))
    with eng.connect() as c:
        assert c.execute(text("SELECT count(*) FROM mv_skill_daily")).scalar_one() >= 0
    rev = engine("reveal", migrated)
    with rev.connect() as c, pytest.raises(ProgrammingError):
        c.execute(text("SELECT email_enc FROM users LIMIT 1"))
    app_eng = engine("app", migrated)
    with app_eng.connect() as c, pytest.raises(ProgrammingError):
        c.execute(text("DELETE FROM audit_log"))


def test_home(
    client: TestClient,
    token: TokenFactory,
    people: dict[str, Person],
    dataset: dict[str, Any],
    world: Any,
) -> None:
    eng = client.get("/v1/me/home?tz=Asia/Kolkata", headers=portal(token, people["eng"])).json()[
        "data"
    ]
    assert eng["tiles"]["waiting_on_me"]["questions"] >= 1
    assert eng["tiles"]["my_first_try_pass"]["n"] == 30
    assert eng["tiles"]["my_prs_this_month"] >= 0
    assert eng["systems"][0]["system"] == world.system
    lead = client.get("/v1/me/home", headers=portal(token, people["lead"])).json()["data"]
    assert any(
        w["kind"] == "approval" and w["run_id"] == dataset["gate_run"] for w in lead["waiting"]
    ), lead
    assert (
        client.get("/v1/me/home?tz=Mars/Base", headers=portal(token, people["eng"])).status_code
        == 400
    )


def test_engineering_tabs(
    client: TestClient,
    token: TokenFactory,
    people: dict[str, Person],
    dataset: dict[str, Any],
    world: Any,
    owner_db: Engine,
) -> None:
    he, hl = portal(token, people["eng"]), portal(token, people["lead"])
    runs = client.get("/v1/insights/engineering/runs", headers=he).json()["data"]
    assert runs["status_counts"]["completed"] >= 15 and runs["status_counts"]["paused_input"] >= 1
    assert runs["step_outcomes"]["total"] >= 30
    assert runs["oldest_input_wait_s"] is not None
    skills = client.get("/v1/insights/engineering/skills", headers=he).json()["data"]["items"]
    design = next(x for x in skills if x["skill_id"] == "design")
    with owner_db.connect() as c:
        gold = c.execute(
            text(
                "SELECT count(*) FILTER (WHERE s.outcome IN ('PASS','PASS-WITH-FINDINGS'))::numeric / count(*) FROM steps s "
                "JOIN runs r ON r.id = s.run_id WHERE s.attempt = 1 AND s.skill_id = 'design' AND s.skill_version = :v "
                "AND r.system_id = CAST(:s AS uuid) AND s.decided_at::date >= current_date - 29"
            ),
            {"s": world.system_id, "v": skill_version("design")},
        ).scalar_one()
    assert design["first_try_pass"] == pytest.approx(float(gold), abs=1e-3)  # M-03 golden SQL
    assert design["below_target"] is True and design["top_cause"]["code"] in ("S1", "REVIEW-MAJOR")
    usage = client.get("/v1/insights/engineering/usage", headers=he).json()["data"]
    assert (
        usage["runs_started"] >= 31
        and usage["active_engineers"] >= 1
        and usage["pr_merge_rate"] == 1.0
    )
    health_e = client.get("/v1/insights/engineering/health", headers=he).json()["data"]
    assert health_e["telemetry"] is None
    health_l = client.get("/v1/insights/engineering/health", headers=hl).json()["data"]
    assert health_l["telemetry"]["events_today"] > 0
    assert (
        client.get(
            f"/v1/insights/engineering/runs?system={world.other_system}", headers=he
        ).status_code
        == 404
    )


def test_skill_owner_scope(
    client: TestClient, token: TokenFactory, people: dict[str, Person], dataset: dict[str, Any]
) -> None:
    h = portal(token, people["owner"])
    skills = client.get("/v1/insights/engineering/skills", headers=h).json()["data"]["items"]
    assert "design" in {x["skill_id"] for x in skills} <= {"design", "threat-model"}
    assert all(x["scope_level"] == "org" for x in skills)
    q = client.get("/v1/catalogue/skills/design/quality", headers=h).json()["data"]
    assert q["scope_level"] == "org" and q["first_attempts"] >= 36
    assert client.get("/v1/catalogue/skills/unit-test/quality", headers=h).status_code == 403
    assert client.get("/v1/runs", headers=h).status_code == 403
    q2 = client.get(
        "/v1/catalogue/skills/design/quality", headers=portal(token, people["eng"])
    ).json()["data"]
    assert q2["scope_level"] == "systems" and q2["causes"]


def test_pods_routes(
    client: TestClient,
    token: TokenFactory,
    people: dict[str, Person],
    world: Any,
    dataset: dict[str, Any],
    owner_db: Engine,
) -> None:
    he, hb = portal(token, people["eng"]), portal(token, people["biz"])
    cards = client.get("/v1/catalogue/pods", headers=he).json()["data"]["items"]
    bf = next(x for x in cards if x["id"] == "brownfield-change-pod")
    assert bf["workflows"] and bf["skill_count"] > 0 and "metrics" not in bf
    assert (
        client.get("/v1/pods/brownfield-change-pod", headers=hb).status_code == 404
    )  # draft hidden from Business
    d = client.get("/v1/pods/brownfield-change-pod", headers=he).json()["data"]
    assert d["flow"] and "step_id" in d["flow"][0] and d["agents"][0]["skills"]
    m = client.get("/v1/pods/brownfield-change-pod/metrics?period=all", headers=he).json()["data"]
    assert (m["status"] == "ok" and m["completed_runs"] >= 3) or m == {"status": "no_data"}
    runs = client.get("/v1/pods/brownfield-change-pod/runs", headers=he).json()["data"]["items"]
    assert runs and all(r["pod"] == "brownfield-change-pod" for r in runs)
    fit = client.get(
        f"/v1/pods/brownfield-change-pod/fit?system={world.system}", headers=he
    ).json()["data"]
    assert {c["key"]: c["status"] for c in fit["checks"]}["docker"] == "confirm_locally"
    assert (
        client.get(
            f"/v1/pods/brownfield-change-pod/fit?system={world.other_system}", headers=he
        ).status_code
        == 404
    )
    one = client.get("/v1/pods/brownfield-change-pod/one-pager", headers=he).json()["data"]
    assert one["markdown"] and one["internal_only"] is True
    # a pilot pod is visible to Business with aggregate fields only
    with owner_db.begin() as c:
        c.execute(text("UPDATE pods SET status = 'pilot' WHERE id = 'quality-security-pod'"))
        c.execute(
            text("UPDATE pod_versions SET status = 'pilot' WHERE pod_id = 'quality-security-pod'")
        )
    biz_cards = client.get("/v1/catalogue/pods", headers=hb).json()["data"]["items"]
    q = next(x for x in biz_cards if x["id"] == "quality-security-pod")
    assert "metrics" in q and "workflows" not in q and "skill_count" not in q
    detail = client.get("/v1/pods/quality-security-pod", headers=hb).json()["data"]
    assert "step_id" not in detail["flow"][0] and "skills" not in detail["agents"][0]
    assert client.get("/v1/pods/quality-security-pod/one-pager", headers=hb).status_code == 200


def test_status(
    client: TestClient, token: TokenFactory, people: dict[str, Person], dataset: dict[str, Any]
) -> None:
    d = client.get("/v1/status", headers=portal(token, people["eng"])).json()["data"]
    assert (
        d["behind"] is False and d["last_event_received_at"] and d["catalogue_release"] == "v0.1.0"
    )


def test_cancelled_runs_are_labelled_and_not_counted_as_completed(
    client: TestClient,
    token: TokenFactory,
    people: dict[str, Person],
    dataset: dict[str, Any],
    world: Any,
    migrated: Any,
) -> None:
    he = portal(token, people["eng"])
    before = client.get("/v1/insights/engineering/runs", headers=he).json()["data"]["status_counts"]
    run_id = new_run()
    post(
        client,
        token(people["eng"].oid, people["eng"].roles),
        [
            event("run.started", run_started(world.system, ticket="ORD-950"), run_id, now_iso(-5)),
            event(
                "run.status_changed",
                {"from": "RUNNING", "to": "COMPLETED", "reason_code": "cancelled"},
                run_id,
                now_iso(-1),
            ),
        ],
        strict=True,
    )
    project(migrated)

    def items(status: str) -> dict[str, Any]:
        res = client.get(f"/v1/runs?status={status}&limit=100", headers=he).json()["data"]
        return {r["run_id"]: r for r in res["items"]}

    row = items("cancelled")[run_id]
    assert row["status_label"] == "Cancelled"
    assert row["next_action"]["text"] == "Run cancelled"
    assert run_id not in items("completed")
    after = client.get("/v1/insights/engineering/runs", headers=he).json()["data"]["status_counts"]
    assert after["cancelled"] == before["cancelled"] + 1
    assert after["completed"] == before["completed"]
