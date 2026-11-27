"""GitHub webhook (SDD-08 §6.1; TC-INS-005, TC-INS-006; join in both orders)."""

from __future__ import annotations

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


def _sha() -> str:
    return f"{random.getrandbits(160):040x}"


def _open_pr(client: TestClient, head: str) -> int:
    n = random.randint(100_000, 999_999)
    body = f"<!-- tsl:run_id={new_run()} -->"
    assert send(client, "pull_request", pr_payload("opened", n, body, head=head)).status_code == 200
    return n


def _check(
    name: str, head: str, conclusion: str | None, at: str | None = None, action: str = "completed"
) -> dict[str, Any]:
    return {
        "action": action,
        "repository": {"full_name": "example-org/orders-api"},
        "check_run": {
            "name": name,
            "head_sha": head,
            "conclusion": conclusion,
            "started_at": at or now_iso(),
            "completed_at": None if action == "created" else (at or now_iso()),
            "pull_requests": [],
        },
    }


def _ci(owner_db: Engine, n: int, head: str) -> tuple[str | None, int, int]:
    """(the PR's CI status as the run page reads it, product rows, harness rows) for PR n."""
    from app.api.v1.read.runs import CI_RESULT_SQL

    with owner_db.connect() as c:
        ci = c.execute(
            text(f"SELECT {CI_RESULT_SQL} AS ci FROM pull_requests pr WHERE number = :n"),
            {"n": n},
        ).scalar_one()
        prod = c.execute(
            text("SELECT count(*) FROM product_ci_checks WHERE head_sha = :h"), {"h": head}
        ).scalar_one()
        harness = c.execute(
            text("SELECT count(*) FROM ci_checks WHERE head_sha = :h"), {"h": head}
        ).scalar_one()
    return ci, prod, harness


def test_product_checks_set_ci_status_and_any_failure_wins(
    client: TestClient, hook: int, owner_db: Engine
) -> None:
    """Two product checks on one head keep their own rows; a failure is not hidden by a pass."""
    head = _sha()
    n = _open_pr(client, head)
    assert _ci(owner_db, n, head) == (None, 0, 0)  # nothing reported yet: "CI pending"
    send(client, "check_run", _check("build", head, "failure", now_iso(-60)))
    send(client, "check_run", _check("ci / build (3.11)", head, "success"))
    assert _ci(owner_db, n, head) == ("fail", 2, 0)  # never stored as a harness verification
    send(client, "check_run", _check("build", head, "success"))  # the build is re-run and passes
    assert _ci(owner_db, n, head) == ("pass", 2, 0)


def test_older_product_result_never_replaces_a_newer_one(
    client: TestClient, hook: int, owner_db: Engine
) -> None:
    head = _sha()
    n = _open_pr(client, head)
    send(client, "check_run", _check("build", head, "failure"))
    send(client, "check_run", _check("build", head, "success", now_iso(-600)))  # late delivery
    assert _ci(owner_db, n, head) == ("fail", 1, 0)


def test_a_running_check_keeps_ci_pending(client: TestClient, hook: int, owner_db: Engine) -> None:
    """One matrix job passed while another still runs: not "CI passed" yet."""
    head = _sha()
    n = _open_pr(client, head)
    send(client, "check_run", _check("build", head, None, now_iso(-120), action="created"))
    send(client, "check_run", _check("ci / build (3.12)", head, None, action="created"))
    send(client, "check_run", _check("build", head, "success", now_iso(-60)))
    assert _ci(owner_db, n, head) == (None, 2, 0)
    send(client, "check_run", _check("ci / build (3.12)", head, "success"))
    assert _ci(owner_db, n, head) == ("pass", 2, 0)


def test_no_result_conclusions_record_nothing_and_clear_pending(
    client: TestClient, hook: int, owner_db: Engine
) -> None:
    head = _sha()
    n = _open_pr(client, head)
    send(client, "check_run", _check("build", head, None, now_iso(-60), action="created"))
    for conclusion in ("skipped", "neutral", "cancelled", "stale", "action_required"):
        assert send(client, "check_run", _check("build", head, conclusion)).status_code == 200
    send(client, "check_run", _check("lint", head, "failure"))  # not in CI_CHECK_NAMES
    send(client, "check_run", _check("Build", head, "failure"))  # names are case-sensitive
    assert _ci(owner_db, n, head) == (None, 0, 0)


def test_check_that_finishes_before_the_pr_opens_counts(
    client: TestClient, hook: int, owner_db: Engine
) -> None:
    """CI on push can complete before the PR's `opened` webhook; it must not be lost."""
    head = _sha()
    send(client, "check_run", _check("build", head, "failure"))
    n = _open_pr(client, head)
    assert _ci(owner_db, n, head) == ("fail", 1, 0)


def test_a_push_to_the_pr_moves_its_head(client: TestClient, hook: int, owner_db: Engine) -> None:
    """A fix pushed after the PR opened: CI is read by the new head (synchronize)."""
    first, fixed = _sha(), _sha()
    n = _open_pr(client, first)
    send(client, "check_run", _check("build", first, "failure"))
    assert _ci(owner_db, n, first)[0] == "fail"
    body = "<!-- unchanged -->"
    r = send(client, "pull_request", pr_payload("synchronize", n, body, head=fixed))
    assert r.status_code == 200
    send(client, "check_run", _check("build", fixed, "success"))
    assert _ci(owner_db, n, fixed) == ("pass", 1, 0)


def test_any_failure_wins_between_harness_and_product_checks(
    client: TestClient, hook: int, owner_db: Engine
) -> None:
    head = _sha()
    n = _open_pr(client, head)
    send(client, "check_run", _check("build", head, "success"))
    send(client, "check_run", _check("tsl-ci-verify", head, "failure"))
    assert _ci(owner_db, n, head) == ("fail", 1, 1)
    other = _sha()
    m = _open_pr(client, other)
    send(client, "check_run", _check("tsl-ci-verify", other, "success"))
    send(client, "check_run", _check("build", other, "failure"))
    assert _ci(owner_db, m, other) == ("fail", 1, 1)  # a harness pass does not hide it


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
