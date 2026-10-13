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
