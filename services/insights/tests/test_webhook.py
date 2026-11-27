"""GitHub webhook (SDD-08 §6.1; TC-INS-005, TC-INS-006; join in both orders)."""

from __future__ import annotations

import itertools
import json
import random
import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.auth.github_hmac import signature
from tests.conftest import Person, TokenFactory, event, new_run, now_iso, post, project, run_started

HOOK_ID = 4242
SECRET = "webhook-secret-for-tests-only-0001"


@pytest.fixture(scope="module")
def hook(migrated: Any, world: Any) -> int:
    import io
    import sys

    from app.admin import main as admin_main

    old = sys.stdin
    sys.stdin = io.StringIO(SECRET + "\n")
    try:
        assert (
            admin_main(
                ["hook", "create", "--hook-id", str(HOOK_ID), "--target", "example-org"], migrated
            )
            == 0
        )
    finally:
        sys.stdin = old
    return HOOK_ID


def send(
    c: TestClient,
    event_name: str,
    payload: dict[str, Any],
    delivery: str | None = None,
    secret: str = SECRET,
    hook_id: int = HOOK_ID,
) -> Any:
    raw = json.dumps(payload).encode()
    return c.post(
        "/v1/webhooks/github",
        content=raw,
        headers={
            "X-GitHub-Event": event_name,
            "X-GitHub-Delivery": delivery or str(uuid.uuid4()),
            "X-GitHub-Hook-ID": str(hook_id),
            "X-Hub-Signature-256": signature(secret.encode(), raw),
            "Content-Type": "application/json",
        },
    )


def pr_payload(
    action: str,
    number: int,
    body: str = "",
    merged: bool = False,
    repo: str = "example-org/orders-api",
    head: str = "f" * 40,
) -> dict[str, Any]:
    return {
        "action": action,
        "repository": {"full_name": repo},
        "pull_request": {
            "number": number,
            "body": body,
            "draft": False,
            "merged": merged,
            "created_at": now_iso(-3600),
            "merged_at": now_iso() if merged else None,
            "closed_at": now_iso() if action == "closed" else None,
            "head": {"sha": head},
        },
    }


def test_bad_signature_and_unknown_hook(client: TestClient, hook: int) -> None:
    r = send(client, "pull_request", pr_payload("opened", 1), secret="wrong-secret-xxxxxxxxxxxx")
    assert r.status_code == 401
    r = send(client, "pull_request", pr_payload("opened", 1), hook_id=999)
    assert r.status_code == 401


def test_unlinked_pr_counted_only(client: TestClient, hook: int, owner_db: Engine) -> None:
    n = random.randint(10_000, 99_999)
    with owner_db.connect() as c:
        before = c.execute(
            text(
                "SELECT coalesce(sum(opened), 0) FROM pr_unlinked_daily "
                "WHERE github_full_name = 'example-org/orders-api'"
            )
        ).scalar_one()
    assert (
        send(client, "pull_request", pr_payload("opened", n, body="no marker here")).status_code
        == 200
    )
    with owner_db.connect() as c:
        after = c.execute(
            text(
                "SELECT coalesce(sum(opened), 0) FROM pr_unlinked_daily "
                "WHERE github_full_name = 'example-org/orders-api'"
            )
        ).scalar_one()
        assert after == before + 1
        assert (
            c.execute(
                text("SELECT count(*) FROM pull_requests WHERE number = :n"), {"n": n}
            ).scalar_one()
            == 0
        )


def test_webhook_before_pr_opened_and_duplicate_delivery(
    client: TestClient,
    hook: int,
    token: TokenFactory,
    people: dict[str, Person],
    world: Any,
    migrated: Any,
    owner_db: Engine,
) -> None:
    run_id = new_run()
    n = random.randint(10_000, 99_999)
    marker = f"Change for ticket\n<!-- tsl:run_id={run_id} -->\n"
    assert send(client, "pull_request", pr_payload("opened", n, marker)).status_code == 200
    tok = token(people["eng"].oid, people["eng"].roles)
    post(
        client,
        tok,
        [
            event("run.started", run_started(world.system), run_id),
            event(
                "pr.opened",
                {"repo": world.repo, "number": n, "draft": False, "lowest_band": "High"},
                run_id,
            ),
        ],
        strict=True,
    )
    project(migrated)
    d = str(uuid.uuid4())
    review = {
        "action": "submitted",
        "repository": {"full_name": "example-org/orders-api"},
        "pull_request": {"number": n},
        "review": {"state": "changes_requested", "submitted_at": now_iso()},
    }
    assert send(client, "pull_request_review", review, delivery=d).status_code == 200
    assert (
        send(client, "pull_request_review", review, delivery=d).status_code == 200
    )  # repeat: no-op
    comment = {
        "action": "created",
        "repository": {"full_name": "example-org/orders-api"},
        "pull_request": {"number": n},
    }
    assert send(client, "pull_request_review_comment", comment).status_code == 200
    assert (
        send(client, "pull_request", pr_payload("closed", n, marker, merged=True)).status_code
        == 200
    )
    with owner_db.connect() as c:
        pr = c.execute(
            text(
                "SELECT run_id, state, review_count, changes_requested, review_comments, merged_at "
                "FROM pull_requests WHERE number = :n"
            ),
            {"n": n},
        ).one()
    assert pr.run_id == run_id and pr.state == "merged" and pr.review_count == 1
    assert pr.changes_requested is True and pr.review_comments == 1 and pr.merged_at is not None


def test_pr_opened_before_webhook(
    client: TestClient,
    hook: int,
    token: TokenFactory,
    people: dict[str, Person],
    world: Any,
    migrated: Any,
    owner_db: Engine,
) -> None:
    run_id = new_run()
    n = random.randint(10_000, 99_999)
    tok = token(people["eng"].oid, people["eng"].roles)
    post(
        client,
        tok,
        [
            event("run.started", run_started(world.system), run_id),
            event(
                "pr.opened",
                {"repo": world.repo, "number": n, "draft": True, "lowest_band": "Medium"},
                run_id,
            ),
        ],
        strict=True,
    )
    project(migrated)
    assert (
        send(
            client,
            "pull_request",
            pr_payload("ready_for_review", n, f"<!-- tsl:run_id={run_id} -->", head="1" * 40),
        ).status_code
        == 200
    )
    check = {
        "action": "completed",
        "repository": {"full_name": "example-org/orders-api"},
        "check_run": {
            "name": "tsl-ci-verify",
            "head_sha": "1" * 40,
            "conclusion": "success",
            "completed_at": now_iso(),
            "pull_requests": [{"number": n}],
        },
    }
    assert send(client, "check_run", check).status_code == 200
    with owner_db.connect() as c:
        rows = c.execute(
            text("SELECT count(*) FROM pull_requests WHERE number = :n"), {"n": n}
        ).scalar_one()
        ci = c.execute(
            text("SELECT result, source FROM ci_checks WHERE head_sha = :h"), {"h": "1" * 40}
        ).one()
    assert rows == 1 and ci.result == "pass" and ci.source == "webhook"


# --- product CI (D5): one row per check run; every scenario in every delivery order ---------

_NUMS = itertools.count(random.randint(1_000_000, 8_000_000))
_RUN_IDS = itertools.count(random.randint(10_000_000, 80_000_000))


def _sha() -> str:
    return f"{random.getrandbits(160):040x}"


def _marker() -> str:
    return f"<!-- tsl:run_id={new_run()} -->"


def _open_pr(client: TestClient, head: str) -> int:
    n = next(_NUMS)
    assert (
        send(client, "pull_request", pr_payload("opened", n, _marker(), head=head)).status_code
        == 200
    )
    return n


def _run(
    action: str,
    run_id: int,
    head: str,
    conclusion: str | None = None,
    name: str = "build",
    started: str | None = "now",
    completed: str | None = "now",
    status: str | None = None,
    suite: int = 1,
) -> dict[str, Any]:
    return {
        "action": action,
        "repository": {"full_name": "example-org/orders-api"},
        "check_run": {
            "id": run_id,
            "name": name,
            "head_sha": head,
            "status": status or ("in_progress" if action == "created" else "completed"),
            "conclusion": conclusion,
            "started_at": now_iso() if started == "now" else started,
            "completed_at": None
            if action == "created"
            else (now_iso() if completed == "now" else completed),
            "check_suite": {"id": suite},
            "app": {"id": 15368},
            "pull_requests": [],
        },
    }


def _ci(owner_db: Engine, n: int) -> str | None:
    """The PR's CI status as the run page reads it."""
    from app.api.v1.read.runs import CI_RESULT_SQL

    with owner_db.connect() as c:
        return c.execute(  # type: ignore[no-any-return]
            text(f"SELECT {CI_RESULT_SQL} FROM pull_requests pr WHERE number = :n"),
            {"n": n, "ci_pending_hours": 30},
        ).scalar_one()


def _in_every_order(
    client: TestClient, owner_db: Engine, events: list[Any], want: str | None, harness: str = ""
) -> None:
    """Deliver `events(head)` in every order (and once more, duplicated) to a fresh PR each time."""
    orders = [(o, False) for o in itertools.permutations(range(len(events)))]
    for order, twice in [*orders, (orders[-1][0], True)]:
        head = _sha()
        n = _open_pr(client, head)
        if harness:
            send(client, "check_run", _harness(head, harness))
        ids = [next(_RUN_IDS) for _ in range(2)]  # GitHub check run ids are unique, rising
        evs = [events[k](head, ids) for k in order]
        for ev in evs + (evs if twice else []):  # one extra round: every event twice
            send(client, "check_run", ev)
        assert _ci(owner_db, n) == want, (order, want)


def _harness(head: str, conclusion: str) -> dict[str, Any]:
    return {
        "action": "completed",
        "repository": {"full_name": "example-org/orders-api"},
        "check_run": {
            "name": "tsl-ci-verify",
            "head_sha": head,
            "status": "completed",
            "conclusion": conclusion,
            "completed_at": now_iso(),
            "pull_requests": [],
        },
    }


def test_a_rerun_that_passes_wins_in_any_order(
    client: TestClient, hook: int, owner_db: Engine
) -> None:
    events = [
        lambda h, i: _run("created", i[0], h, started=now_iso(-300)),
        lambda h, i: _run(
            "completed", i[0], h, "failure", started=now_iso(-300), completed=now_iso(-200)
        ),
        lambda h, i: _run("created", i[1], h, started=now_iso(-100)),
        lambda h, i: _run(
            "completed", i[1], h, "success", started=now_iso(-100), completed=now_iso(-10)
        ),
    ]
    _in_every_order(client, owner_db, events, "pass")


def test_a_cancelled_rerun_keeps_the_failure_in_any_order(
    client: TestClient, hook: int, owner_db: Engine
) -> None:
    events = [
        lambda h, i: _run("created", i[0], h, started=now_iso(-300)),
        lambda h, i: _run("completed", i[0], h, "failure", started=now_iso(-300)),
        lambda h, i: _run("created", i[1], h, started=now_iso(-100)),
        lambda h, i: _run("completed", i[1], h, "cancelled", started=now_iso(-100)),
    ]
    _in_every_order(client, owner_db, events, "fail", harness="success")


def test_a_running_rerun_is_pending_in_any_order(
    client: TestClient, hook: int, owner_db: Engine
) -> None:
    events = [
        lambda h, i: _run("created", i[0], h, started=now_iso(-300)),
        lambda h, i: _run("completed", i[0], h, "failure", started=now_iso(-300)),
        lambda h, i: _run("created", i[1], h, started=now_iso(-100)),
    ]
    _in_every_order(client, owner_db, events, None)


def test_a_failure_wins_while_another_job_runs_or_passes(
    client: TestClient, hook: int, owner_db: Engine
) -> None:
    events = [
        lambda h, i: _run("completed", i[0], h, "failure"),
        lambda h, i: _run("created", i[1], h, name="ci / build (3.12)"),
    ]
    _in_every_order(client, owner_db, events, "fail")


def test_one_matrix_job_running_keeps_ci_pending(
    client: TestClient, hook: int, owner_db: Engine
) -> None:
    events: list[Any] = [
        lambda h, i: _run("completed", i[0], h, "success"),
        lambda h, i: _run("created", i[1], h, name="ci / build (3.12)"),
    ]
    _in_every_order(client, owner_db, events, None, harness="success")
    events.append(lambda h, i: _run("completed", i[1], h, "success", name="ci / build (3.12)"))
    _in_every_order(client, owner_db, events, "pass")


def test_no_result_conclusions_give_no_result_in_any_order(
    client: TestClient, hook: int, owner_db: Engine
) -> None:
    for conclusion in ("skipped", "neutral", "cancelled", "stale", "action_required"):
        events: list[Any] = [
            lambda h, i: _run("created", i[0], h),
            lambda h, i, c=conclusion: _run("completed", i[0], h, c),
        ]
        _in_every_order(client, owner_db, events, None)
        _in_every_order(client, owner_db, events, "pass", harness="success")


def test_newest_run_per_check_name_decides(client: TestClient, hook: int, owner_db: Engine) -> None:
    """Re-running a failed job (same workflow run, same suite) that passes clears the failure."""
    events = [
        lambda h, i: _run("completed", i[0], h, "failure", completed=now_iso(-100)),
        lambda h, i: _run(
            "completed", i[1], h, "success", completed=now_iso(-200)
        ),  # newer id wins
    ]
    _in_every_order(client, owner_db, events, "pass")


def test_any_failure_wins_between_harness_and_product(
    client: TestClient, hook: int, owner_db: Engine
) -> None:
    _in_every_order(
        client,
        owner_db,
        [lambda h, i: _run("completed", i[0], h, "success")],
        "fail",
        harness="failure",
    )
    _in_every_order(
        client,
        owner_db,
        [lambda h, i: _run("completed", i[1], h, "failure")],
        "fail",
        harness="success",
    )


def test_a_pending_run_older_than_the_limit_is_ignored(
    client: TestClient, hook: int, owner_db: Engine
) -> None:
    """A lost `completed` delivery doesn't leave CI pending for good (CI_PENDING_MAX_HOURS)."""
    old = [lambda h, i: _run("created", i[0], h, started=now_iso(-31 * 3600))]
    _in_every_order(client, owner_db, old, "pass", harness="success")
    _in_every_order(client, owner_db, old, None)


def test_a_job_queued_for_hours_is_still_pending(
    client: TestClient, hook: int, owner_db: Engine
) -> None:
    """started_at is the queue time: a job waiting 7 h for a runner is not a pass yet."""
    queued = [lambda h, i: _run("created", i[0], h, started=now_iso(-7 * 3600))]
    _in_every_order(client, owner_db, queued, None, harness="success")


def test_the_same_job_name_in_two_workflows_is_two_checks(
    client: TestClient, hook: int, owner_db: Engine
) -> None:
    """ci.yml's failing `build` is not hidden by release.yml's passing `build` (another suite),
    and a newer workflow run on the same commit doesn't clear an older run's failure: any
    failure wins until the failed run is re-run or a new commit is pushed."""
    events = [
        lambda h, i: _run("completed", i[0], h, "failure", suite=100),
        lambda h, i: _run("completed", i[1], h, "success", suite=101),
    ]
    _in_every_order(client, owner_db, events, "fail")
    rerun = [  # the failed workflow run re-run: its newest run passes
        *events,
        lambda h, i: _run("completed", next(_RUN_IDS), h, "success", suite=100),  # newest
    ]
    _in_every_order(client, owner_db, rerun, "pass")


def test_a_completed_run_without_a_conclusion_is_no_result(
    client: TestClient, hook: int, owner_db: Engine
) -> None:
    events = [lambda h, i: _run("completed", i[0], h, None)]
    _in_every_order(client, owner_db, events, None)
    _in_every_order(client, owner_db, events, "pass", harness="success")
    with owner_db.connect() as c:
        assert not c.execute(
            text("SELECT count(*) FROM product_ci_runs WHERE conclusion = ''")
        ).scalar_one()


def test_harness_checks_without_a_result_are_filtered(
    client: TestClient, hook: int, owner_db: Engine
) -> None:
    """A running, skipped or cancelled tsl-ci-verify: 204 before any lookup, nothing stored,
    so it never fails a PR whose product CI passed."""
    head = _sha()
    n = _open_pr(client, head)
    send(client, "check_run", _run("completed", next(_RUN_IDS), head, "success"))
    running = {**_harness(head, "success"), "action": "created"}
    running["check_run"] = {**running["check_run"], "status": "in_progress", "conclusion": None}
    assert send(client, "check_run", running).status_code == 204
    for conclusion in ("skipped", "cancelled", "neutral", "stale", "action_required"):
        assert send(client, "check_run", _harness(head, conclusion)).status_code == 204
    no_conclusion = _harness(head, "success")
    no_conclusion["check_run"] = {**no_conclusion["check_run"], "conclusion": None}
    assert send(client, "check_run", no_conclusion).status_code == 204
    assert _ci(owner_db, n) == "pass"
    with owner_db.connect() as c:
        assert not c.execute(
            text("SELECT count(*) FROM ci_checks WHERE head_sha = :h"), {"h": head}
        ).scalar_one()


def test_created_without_a_start_time_is_ignored(
    client: TestClient, hook: int, owner_db: Engine
) -> None:
    a = next(_RUN_IDS)
    head = _sha()
    n = _open_pr(client, head)
    send(client, "check_run", _harness(head, "success"))
    send(client, "check_run", _run("created", a, head, started=None))
    assert _ci(owner_db, n) == "pass"


def test_created_that_already_completed_counts_as_completed(
    client: TestClient, hook: int, owner_db: Engine
) -> None:
    head = _sha()
    n = _open_pr(client, head)
    send(client, "check_run", _run("created", next(_RUN_IDS), head, "failure", status="completed"))
    assert _ci(owner_db, n) == "fail"
    other = _sha()
    m = _open_pr(client, other)
    created_done = {**_harness(other, "failure"), "action": "created"}  # harness, same rule
    assert send(client, "check_run", created_done).status_code == 200
    assert _ci(owner_db, m) == "fail"


def test_a_check_before_the_pr_opens_counts(
    client: TestClient, hook: int, owner_db: Engine
) -> None:
    head = _sha()
    send(client, "check_run", _run("completed", next(_RUN_IDS), head, "failure"))
    n = _open_pr(client, head)
    assert _ci(owner_db, n) == "fail"


def test_unlisted_names_are_filtered_before_any_lookup(
    client: TestClient, hook: int, owner_db: Engine
) -> None:
    head = _sha()
    n = _open_pr(client, head)
    for name in ("lint", "Build", "build-docs"):  # not in CI_CHECK_NAMES (exact, case-sensitive)
        r = send(client, "check_run", _run("completed", next(_RUN_IDS), head, "failure", name=name))
        assert r.status_code == 204
    assert _ci(owner_db, n) is None
    with owner_db.connect() as c:
        assert not c.execute(
            text("SELECT count(*) FROM product_ci_runs WHERE head_sha = :h"), {"h": head}
        ).scalar_one()


def test_product_runs_never_become_harness_verifications(
    client: TestClient, hook: int, owner_db: Engine
) -> None:
    head = _sha()
    _open_pr(client, head)
    send(client, "check_run", _run("completed", next(_RUN_IDS), head, "success"))
    with owner_db.connect() as c:
        assert not c.execute(
            text("SELECT count(*) FROM ci_checks WHERE head_sha = :h"), {"h": head}
        ).scalar_one()


# --- pull request state and head: every delivery order ----------------------------------------


def _pr(
    action: str,
    n: int,
    head: str,
    at: str,
    marker: str,
    merged: bool = False,
    before: str | None = None,
) -> Any:
    p = pr_payload(action, n, marker, merged=merged, head=head)
    p["pull_request"]["updated_at"] = at
    if action == "synchronize":  # GitHub sends the old and new head of a push
        p["before"], p["after"] = before, head
    return p


def _pr_row(owner_db: Engine, n: int) -> tuple[str, str]:
    with owner_db.connect() as c:
        r = c.execute(
            text("SELECT state, head_sha FROM pull_requests WHERE number = :n"), {"n": n}
        ).one()
    return r.state, r.head_sha


def _pr_in_every_order(
    client: TestClient, owner_db: Engine, make: list[Any], want: tuple[str, int]
) -> None:
    for order in itertools.permutations(range(len(make))):
        n, marker, heads = next(_NUMS), _marker(), [_sha() for _ in range(4)]
        for i in order:
            assert send(client, "pull_request", make[i](n, heads, marker)).status_code == 200
        state, head = _pr_row(owner_db, n)
        assert (state, head) == (want[0], heads[want[1]]), order


def test_pushes_and_a_merge_in_any_order(client: TestClient, hook: int, owner_db: Engine) -> None:
    """Late pushes never move the head back or reopen the merged PR."""
    make = [
        lambda n, h, m: _pr("opened", n, h[0], now_iso(-400), m),
        lambda n, h, m: _pr("synchronize", n, h[1], now_iso(-300), m),
        lambda n, h, m: _pr("synchronize", n, h[2], now_iso(-200), m),
        lambda n, h, m: _pr("closed", n, h[2], now_iso(-100), m, merged=True),
    ]
    _pr_in_every_order(client, owner_db, make, ("merged", 2))


def test_close_and_reopen_in_any_order(client: TestClient, hook: int, owner_db: Engine) -> None:
    make = [
        lambda n, h, m: _pr("opened", n, h[0], now_iso(-400), m),
        lambda n, h, m: _pr("closed", n, h[0], now_iso(-300), m),
        lambda n, h, m: _pr("reopened", n, h[0], now_iso(-200), m),
    ]
    _pr_in_every_order(client, owner_db, make, ("open", 0))
    make.append(lambda n, h, m: _pr("closed", n, h[0], now_iso(-100), m))
    _pr_in_every_order(client, owner_db, make, ("closed", 0))


def test_a_merged_pr_stays_merged(client: TestClient, hook: int, owner_db: Engine) -> None:
    make = [
        lambda n, h, m: _pr("closed", n, h[0], now_iso(-300), m, merged=True),
        lambda n, h, m: _pr("reopened", n, h[1], now_iso(-100), m),  # newer: merged is final
    ]
    _pr_in_every_order(client, owner_db, make, ("merged", 0))


def test_a_late_opened_still_records_when_the_pr_opened(
    client: TestClient, hook: int, owner_db: Engine
) -> None:
    n, marker = next(_NUMS), _marker()
    send(client, "pull_request", _pr("synchronize", n, _sha(), now_iso(-60), marker))
    send(client, "pull_request", _pr("opened", n, _sha(), now_iso(-120), marker))  # late
    with owner_db.connect() as c:
        assert c.execute(
            text("SELECT opened_at IS NOT NULL FROM pull_requests WHERE number = :n"), {"n": n}
        ).scalar_one()


def test_concurrent_pushes_keep_the_newest_head(
    client: TestClient, hook: int, owner_db: Engine, migrated: Any
) -> None:
    """Two deliveries handled at once: the order rule runs inside the locked upsert."""
    from concurrent.futures import ThreadPoolExecutor

    for _ in range(5):
        n, marker, heads = next(_NUMS), _marker(), [_sha() for _ in range(6)]
        send(client, "pull_request", _pr("opened", n, heads[0], now_iso(-600), marker))
        evs = [_pr("synchronize", n, heads[k], now_iso(-500 + 60 * k), marker) for k in range(1, 6)]
        random.shuffle(evs)
        with ThreadPoolExecutor(max_workers=5) as pool:
            codes = list(pool.map(lambda e: send(client, "pull_request", e).status_code, evs))
        assert codes == [200] * 5
        assert _pr_row(owner_db, n) == ("open", heads[5])


def test_pushes_in_one_second_end_on_the_last_in_any_order(
    client: TestClient, hook: int, owner_db: Engine
) -> None:
    """Same updated_at: a push applies only when its `before` is the stored head."""
    at = now_iso(-60)
    make = [
        lambda n, h, m: _pr("opened", n, h[0], at, m),
        lambda n, h, m: _pr("synchronize", n, h[1], at, m, before=h[0]),
        lambda n, h, m: _pr("synchronize", n, h[2], at, m, before=h[1]),
    ]
    _pr_in_every_order(client, owner_db, make, ("open", 2))
    make.append(lambda n, h, m: _pr("closed", n, h[2], at, m, merged=True))
    _pr_in_every_order(client, owner_db, make, ("merged", 2))


def test_close_and_reopen_in_one_second_in_any_order(
    client: TestClient, hook: int, owner_db: Engine
) -> None:
    """GitHub only reopens a closed PR, so a close and a reopen in one second end open."""
    at = now_iso(-60)
    make = [
        lambda n, h, m: _pr("opened", n, h[0], now_iso(-400), m),
        lambda n, h, m: _pr("closed", n, h[0], at, m),
        lambda n, h, m: _pr("reopened", n, h[0], at, m),
    ]
    _pr_in_every_order(client, owner_db, make, ("open", 0))
    make.append(lambda n, h, m: _pr("closed", n, h[0], now_iso(-30), m))  # a later close
    _pr_in_every_order(client, owner_db, make, ("closed", 0))


def test_a_close_and_a_push_in_one_second_keep_the_pr_closed(
    client: TestClient, hook: int, owner_db: Engine
) -> None:
    at = now_iso(-60)
    make = [
        lambda n, h, m: _pr("opened", n, h[0], now_iso(-400), m),
        lambda n, h, m: _pr("synchronize", n, h[1], at, m, before=h[0]),
        lambda n, h, m: _pr("closed", n, h[1], at, m),
    ]
    _pr_in_every_order(client, owner_db, make, ("closed", 1))


def _draft(owner_db: Engine, n: int) -> bool:
    with owner_db.connect() as c:
        return bool(
            c.execute(
                text("SELECT draft FROM pull_requests WHERE number = :n"), {"n": n}
            ).scalar_one()
        )


def test_ready_for_review_in_a_tie_stays_ready_in_any_order(
    client: TestClient, hook: int, owner_db: Engine
) -> None:
    """Payloads snapshotted before ready_for_review in the same second don't set draft again."""
    at = now_iso(-60)

    def ev(
        action: str, n: int, h: list[str], m: str, draft: bool, before: str | None = None
    ) -> Any:
        p = _pr(action, n, h[1] if action == "synchronize" else h[0], at, m, before=before)
        p["pull_request"]["draft"] = draft
        return p

    make = [
        lambda n, h, m: ev("opened", n, h, m, True),
        lambda n, h, m: ev("synchronize", n, h, m, True, before=h[0]),
        lambda n, h, m: ev("ready_for_review", n, h, m, False),
    ]
    for order in itertools.permutations(range(len(make))):
        n, marker, heads = next(_NUMS), _marker(), [_sha() for _ in range(2)]
        for i in order:
            assert send(client, "pull_request", make[i](n, heads, marker)).status_code == 200
        assert not _draft(owner_db, n), order


def test_a_tied_event_keeps_the_reopen_marker(
    client: TestClient, hook: int, owner_db: Engine
) -> None:
    """Close, reopen and a push in one second: the PR ends open in any order."""
    at = now_iso(-60)
    make = [
        lambda n, h, m: _pr("opened", n, h[0], now_iso(-400), m),
        lambda n, h, m: _pr("closed", n, h[0], at, m),
        lambda n, h, m: _pr("reopened", n, h[0], at, m),
        lambda n, h, m: _pr("synchronize", n, h[1], at, m, before=h[0]),
    ]
    for order in itertools.permutations(range(len(make))):
        n, marker, heads = next(_NUMS), _marker(), [_sha() for _ in range(2)]
        for i in order:
            assert send(client, "pull_request", make[i](n, heads, marker)).status_code == 200
        assert _pr_row(owner_db, n)[0] == "open", order


def test_completed_fills_the_suite_a_created_lacked(
    client: TestClient, hook: int, owner_db: Engine
) -> None:
    head, rid = _sha(), next(_RUN_IDS)
    _open_pr(client, head)
    created = _run("created", rid, head)
    del created["check_run"]["check_suite"], created["check_run"]["app"]
    send(client, "check_run", created)
    send(client, "check_run", _run("completed", rid, head, "success", suite=7))
    with owner_db.connect() as c:
        row = c.execute(
            text("SELECT suite_id, app_id FROM product_ci_runs WHERE check_run_id = :i LIMIT 1"),
            {"i": rid},
        ).one()
    assert (row.suite_id, row.app_id) == (7, 15368)


def test_no_result_lists_match() -> None:
    """The SQL function and the webhook handler skip the same conclusions."""
    import importlib.util
    import re as _re
    from pathlib import Path

    from app.api.v1.webhooks_github import NO_RESULT

    path = Path(__file__).parents[1] / "alembic/versions/0008_product_ci_checks.py"
    spec = importlib.util.spec_from_file_location("m0008", path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    sql = _re.search(r"conclusion NOT IN \(([^)]*)\)", mod.RESULT_FN)
    assert sql is not None
    assert tuple(_re.findall(r"'([a-z_]+)'", sql.group(1))) == NO_RESULT


def test_a_merge_recorded_by_tsl_first_still_gets_its_head(
    client: TestClient,
    hook: int,
    token: TokenFactory,
    people: dict[str, Person],
    world: Any,
    migrated: Any,
    owner_db: Engine,
) -> None:
    """tsl pr-sync writes the merge with no head; the delayed webhooks still fill it in."""
    run_id, head = new_run(), _sha()
    n = next(_NUMS)
    tok = token(people["eng"].oid, people["eng"].roles)
    post(
        client,
        tok,
        [
            event("run.started", run_started(world.system), run_id, occurred=now_iso(-3)),
            event(
                "pr.opened",
                {"repo": world.repo, "number": n, "draft": False, "lowest_band": "Low"},
                run_id,
                occurred=now_iso(-2),
            ),
            event(
                "pr.closed",
                {"repo": world.repo, "number": n, "merged": True, "closed_at": now_iso()},
                run_id,
                occurred=now_iso(-1),
            ),
        ],
        strict=True,
    )
    project(migrated)
    marker = f"<!-- tsl:run_id={run_id} -->"
    old = _sha()  # a delayed push from before the merge arrives first
    send(client, "pull_request", _pr("synchronize", n, old, now_iso(-20), marker, before=_sha()))
    send(client, "pull_request", _pr("closed", n, head, now_iso(-10), marker, merged=True))
    send(client, "pull_request", _pr("synchronize", n, old, now_iso(-20), marker, before=_sha()))
    send(client, "check_run", _run("completed", next(_RUN_IDS), head, "success"))
    assert _pr_row(owner_db, n) == ("merged", head)
    with owner_db.connect() as c:
        assert c.execute(
            text("SELECT merged_at IS NOT NULL FROM pull_requests WHERE number = :n"), {"n": n}
        ).scalar_one()
    assert _ci(owner_db, n) == "pass"


def test_a_tsl_merge_takes_the_newest_webhook_head_until_the_merge_arrives(
    client: TestClient,
    hook: int,
    token: TokenFactory,
    people: dict[str, Person],
    world: Any,
    migrated: Any,
    owner_db: Engine,
) -> None:
    run_id, (h0, h1) = new_run(), (_sha(), _sha())
    n = next(_NUMS)
    tok = token(people["eng"].oid, people["eng"].roles)
    post(
        client,
        tok,
        [
            event("run.started", run_started(world.system), run_id, occurred=now_iso(-2)),
            event(
                "pr.closed",
                {"repo": world.repo, "number": n, "merged": True, "closed_at": now_iso()},
                run_id,
                occurred=now_iso(-1),
            ),
        ],
        strict=True,
    )
    project(migrated)
    marker = f"<!-- tsl:run_id={run_id} -->"
    send(client, "pull_request", _pr("opened", n, h0, now_iso(-400), marker))
    send(client, "pull_request", _pr("synchronize", n, h1, now_iso(-100), marker, before=h0))
    send(client, "pull_request", _pr("opened", n, h0, now_iso(-400), marker))  # duplicate, late
    assert _pr_row(owner_db, n) == ("merged", h1)  # the merge webhook never came


def test_a_tsl_close_does_not_undo_a_later_webhook_reopen(
    client: TestClient,
    hook: int,
    token: TokenFactory,
    people: dict[str, Person],
    world: Any,
    migrated: Any,
    owner_db: Engine,
) -> None:
    run_id, n, head = new_run(), next(_NUMS), _sha()
    marker = f"<!-- tsl:run_id={run_id} -->"
    tok = token(people["eng"].oid, people["eng"].roles)
    post(client, tok, [event("run.started", run_started(world.system), run_id)], strict=True)
    project(migrated)
    send(client, "pull_request", _pr("opened", n, head, now_iso(-400), marker))
    send(client, "pull_request", _pr("closed", n, head, now_iso(-300), marker))
    send(client, "pull_request", _pr("reopened", n, head, now_iso(-200), marker))
    post(
        client,
        tok,
        [
            event(
                "pr.closed",
                {"repo": world.repo, "number": n, "merged": False, "closed_at": now_iso(-300)},
                run_id,
            )
        ],
        strict=True,
    )
    project(migrated)
    assert _pr_row(owner_db, n)[0] == "open"


def _tsl_close(client: TestClient, tok: str, world: Any, run_id: str, n: int, at: str) -> None:
    post(
        client,
        tok,
        [
            event(
                "pr.closed",
                {"repo": world.repo, "number": n, "merged": False, "closed_at": at},
                run_id,
            )
        ],
        strict=True,
    )


def test_a_delayed_push_does_not_reopen_a_pr_tsl_closed(
    client: TestClient,
    hook: int,
    token: TokenFactory,
    people: dict[str, Person],
    world: Any,
    migrated: Any,
    owner_db: Engine,
) -> None:
    """tsl pr-sync's close takes part in the order: a push from before it changes nothing."""
    run_id, n, (h0, h1) = new_run(), next(_NUMS), (_sha(), _sha())
    marker = f"<!-- tsl:run_id={run_id} -->"
    tok = token(people["eng"].oid, people["eng"].roles)
    post(client, tok, [event("run.started", run_started(world.system), run_id)], strict=True)
    project(migrated)
    send(client, "pull_request", _pr("opened", n, h0, now_iso(-400), marker))
    _tsl_close(client, tok, world, run_id, n, now_iso(-100))
    project(migrated)
    send(client, "pull_request", _pr("synchronize", n, h1, now_iso(-200), marker, before=h0))
    assert _pr_row(owner_db, n)[0] == "closed"
    send(client, "pull_request", _pr("closed", n, h1, now_iso(-100), marker))  # its webhook
    assert _pr_row(owner_db, n)[0] == "closed"


def test_a_tsl_close_older_than_a_push_keeps_the_pr_open(
    client: TestClient,
    hook: int,
    token: TokenFactory,
    people: dict[str, Person],
    world: Any,
    migrated: Any,
    owner_db: Engine,
) -> None:
    """A push newer than the close means the PR was reopened after it (implied reopen)."""
    run_id, n, (h0, h1) = new_run(), next(_NUMS), (_sha(), _sha())
    marker = f"<!-- tsl:run_id={run_id} -->"
    tok = token(people["eng"].oid, people["eng"].roles)
    post(client, tok, [event("run.started", run_started(world.system), run_id)], strict=True)
    project(migrated)
    send(client, "pull_request", _pr("opened", n, h0, now_iso(-400), marker))
    send(client, "pull_request", _pr("synchronize", n, h1, now_iso(-100), marker, before=h0))
    _tsl_close(client, tok, world, run_id, n, now_iso(-300))
    project(migrated)
    assert _pr_row(owner_db, n) == ("open", h1)
    with owner_db.connect() as c:
        assert c.execute(
            text("SELECT closed_at IS NOT NULL FROM pull_requests WHERE number = :n"), {"n": n}
        ).scalar_one()  # the close is recorded, as it would be in delivery order


def test_waiting_pushes_are_dropped_when_the_pr_closes(
    client: TestClient, hook: int, owner_db: Engine
) -> None:
    n, marker, (h0, h1, h2) = next(_NUMS), _marker(), (_sha(), _sha(), _sha())
    at = now_iso(-60)
    send(client, "pull_request", _pr("opened", n, h0, at, marker))
    send(client, "pull_request", _pr("synchronize", n, h2, at, marker, before=h1))  # waits
    send(client, "pull_request", _pr("closed", n, h0, now_iso(-30), marker, merged=True))
    with owner_db.connect() as c:
        assert (
            c.execute(
                text("SELECT pr_tie_pushes FROM pull_requests WHERE number = :n"), {"n": n}
            ).scalar_one()
            == {}
        )


def test_a_harness_check_before_the_pr_row_is_stored_for_every_repo(
    client: TestClient, hook: int, owner_db: Engine
) -> None:
    head = _sha()
    send(client, "check_run", _harness(head, "success"))
    with owner_db.connect() as c:
        stored, repos = c.execute(
            text(
                "SELECT (SELECT count(*) FROM ci_checks WHERE head_sha = :h), "
                "(SELECT count(*) FROM system_repos WHERE github_full_name = :g)"
            ),
            {"h": head, "g": "example-org/orders-api"},
        ).one()
    assert stored == repos >= 1


def test_a_harness_copy_goes_once_a_pr_takes_the_head(
    client: TestClient, hook: int, world: Any, owner_db: Engine
) -> None:
    """Two systems share a GitHub repo: the copy without the PR is not counted as verified."""
    full = f"example-org/shared-{random.getrandbits(32):08x}"
    with owner_db.begin() as c:
        for sid in (world.system_id, world.other_system_id):
            c.execute(
                text(
                    "INSERT INTO system_repos (system_id, name, github_full_name, kind) "
                    "VALUES (CAST(:s AS uuid), :nm, :g, 'product')"
                ),
                {"s": sid, "nm": full.split("/")[1], "g": full},
            )
    head, n = _sha(), next(_NUMS)
    check = _harness(head, "success")
    check["repository"] = {"full_name": full}
    send(client, "check_run", check)
    pr = _pr("opened", n, head, now_iso(-60), _marker())
    pr["repository"] = {"full_name": full}
    assert send(client, "pull_request", pr).status_code == 200
    with owner_db.connect() as c:
        rows = (
            c.execute(
                text(
                    "SELECT c.repo_id = p.repo_id FROM ci_checks c JOIN pull_requests p "
                    "ON p.number = :n WHERE c.head_sha = :h"
                ),
                {"n": n, "h": head},
            )
            .scalars()
            .all()
        )
    assert rows == [True]


def test_a_tsl_close_in_the_second_of_a_reopen_keeps_the_pr_open(
    client: TestClient,
    hook: int,
    token: TokenFactory,
    people: dict[str, Person],
    world: Any,
    migrated: Any,
    owner_db: Engine,
) -> None:
    run_id, n, head = new_run(), next(_NUMS), _sha()
    marker = f"<!-- tsl:run_id={run_id} -->"
    tok = token(people["eng"].oid, people["eng"].roles)
    post(client, tok, [event("run.started", run_started(world.system), run_id)], strict=True)
    project(migrated)
    at = now_iso(-100)
    send(client, "pull_request", _pr("opened", n, head, now_iso(-400), marker))
    send(client, "pull_request", _pr("reopened", n, head, at, marker))
    _tsl_close(client, tok, world, run_id, n, at.replace("Z", ".400Z"))  # same second
    project(migrated)
    assert _pr_row(owner_db, n)[0] == "open"


def test_a_close_is_recorded_in_any_delivery_order(
    client: TestClient, hook: int, owner_db: Engine
) -> None:
    """closed_at, like opened_at, doesn't depend on the delivery order (PR counts read it)."""
    make = [
        lambda n, h, m: _pr("opened", n, h[0], now_iso(-400), m),
        lambda n, h, m: _pr("closed", n, h[0], now_iso(-300), m),
        lambda n, h, m: _pr("reopened", n, h[0], now_iso(-200), m),
    ]
    for order in itertools.permutations(range(len(make))):
        n, marker, heads = next(_NUMS), _marker(), [_sha()]
        for i in order:
            assert send(client, "pull_request", make[i](n, heads, marker)).status_code == 200
        with owner_db.connect() as c:
            row = c.execute(
                text(
                    "SELECT state, opened_at IS NOT NULL AS o, closed_at IS NOT NULL AS cl "
                    "FROM pull_requests WHERE number = :n"
                ),
                {"n": n},
            ).one()
        assert (row.state, row.o, row.cl) == ("open", True, True), order


def test_a_late_harness_result_never_replaces_a_newer_one(
    client: TestClient, hook: int, owner_db: Engine
) -> None:
    head = _sha()
    n = _open_pr(client, head)
    new = _harness(head, "success")
    new["check_run"]["completed_at"] = now_iso(-60)
    old = _harness(head, "failure")
    old["check_run"]["completed_at"] = now_iso(-600)
    send(client, "check_run", new)
    send(client, "check_run", old)  # a re-run's failure delivered late
    assert _ci(owner_db, n) == "pass"
    tie = _harness(head, "failure")
    tie["check_run"]["completed_at"] = now_iso(-60)
    send(client, "check_run", tie)  # same second: a failure wins
    assert _ci(owner_db, n) == "fail"


def test_a_newer_push_reopens_a_closed_pr_in_any_order(
    client: TestClient, hook: int, owner_db: Engine
) -> None:
    """GitHub only sends pushes to open PRs: a push newer than the close means it was reopened,
    also when the push arrives before the `reopened` delivery."""
    make = [
        lambda n, h, m: _pr("opened", n, h[0], now_iso(-400), m),
        lambda n, h, m: _pr("closed", n, h[0], now_iso(-300), m),
        lambda n, h, m: _pr("reopened", n, h[0], now_iso(-200), m),
        lambda n, h, m: _pr("synchronize", n, h[1], now_iso(-100), m, before=h[0]),
    ]
    _pr_in_every_order(client, owner_db, make, ("open", 1))


def test_ignored_and_unknown_repo(client: TestClient, hook: int) -> None:
    assert (
        send(
            client,
            "issues",
            {"action": "opened", "repository": {"full_name": "example-org/orders-api"}},
        ).status_code
        == 204
    )
    assert (
        send(client, "pull_request", pr_payload("opened", 5, repo="other-org/unknown")).status_code
        == 204
    )
    assert (
        send(
            client,
            "release",
            {"action": "published", "repository": {"full_name": "example-org/skill-library"}},
        ).status_code
        == 200
    )
