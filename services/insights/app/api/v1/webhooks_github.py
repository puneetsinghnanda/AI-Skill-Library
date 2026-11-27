"""``POST /v1/webhooks/github`` (SDD-08 §6.1, Doc 5 §6.1).

1. HMAC check with the secret of the hook named by ``X-GitHub-Hook-ID``; 2. idempotency on
``X-GitHub-Delivery``; 3. event filter; 4. repo lookup; 5. ``tsl:run_id`` join (the PR body is
never stored); 6. upsert in the same transaction.
"""

from __future__ import annotations

import fnmatch
import json
import re
import time
from collections.abc import Sequence
from typing import Any

from fastapi import APIRouter, Request, Response
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import Connection, text

from app.auth.github_hmac import verify
from app.config import Settings
from app.crypto import decrypt
from app.db import tx
from app.errors import ServiceError
from app.obs import metrics
from app.projector.handlers import ensure_run
from app.timeutil import parse_iso, utcnow

router = APIRouter(tags=["ingest"])
MARKER = re.compile(r"<!--\s*tsl:run_id=(run_[0-9A-HJKMNP-TV-Z]{26})\s*-->")
KEEP = {
    # synchronize: a push to the PR's branch moves its head; CI results are read by that head.
    "pull_request": {"opened", "reopened", "ready_for_review", "synchronize", "closed"},
    "pull_request_review": {"submitted"},
    "pull_request_review_comment": {"created"},
    "check_run": {"created", "completed"},
    "release": {"published"},
}


def _ts(v: Any) -> Any:
    return parse_iso(str(v)) if v else utcnow()


def _repos(conn: Connection, full_name: str) -> Sequence[Any]:
    return conn.execute(
        text(
            "SELECT id::text AS id, system_id::text AS system_id FROM system_repos "
            "WHERE github_full_name = :g ORDER BY id"
        ),
        {"g": full_name},
    ).all()


def _pull_request(
    conn: Connection, action: str, pr: dict[str, Any], full_name: str, repos: Sequence[Any]
) -> str:
    number = int(pr["number"])
    m = MARKER.search(str(pr.get("body") or ""))
    run_id = m.group(1) if m else None
    existing = conn.execute(
        text(
            "SELECT id::text AS id, repo_id::text AS repo_id "
            "FROM pull_requests WHERE repo_id = ANY(CAST(:ids AS uuid[])) AND number = :n"
        ),
        {"ids": [r.id for r in repos], "n": number},
    ).first()
    if run_id is None and existing is None:
        if action == "opened":
            conn.execute(
                text(
                    "INSERT INTO pr_unlinked_daily (day, github_full_name, opened) VALUES (:d, "
                    ":g, "
                    "1) "
                    "ON CONFLICT (day, github_full_name) DO UPDATE SET opened = "
                    "pr_unlinked_daily.opened + 1"
                ),
                {"d": _ts(pr.get("created_at")).date(), "g": full_name},
            )
        return "unlinked"
    if existing is not None:
        repo_id = existing.repo_id
    else:
        assert run_id is not None  # noqa: S101
        run = ensure_run(conn, run_id, utcnow())
        repo_id = next((r.id for r in repos if r.system_id == run.system_id), repos[0].id)
    head = (pr.get("head") or {}).get("sha")
    if action == "closed":
        merged = bool(pr.get("merged"))
        state = "merged" if merged else "closed"
        cols = "merged_at = :t" if merged else "closed_at = :t"
        t = _ts(pr.get("merged_at") if merged else pr.get("closed_at"))
    else:
        state, cols, t = (
            "open",
            "opened_at = coalesce(pull_requests.opened_at, :t)",
            _ts(pr.get("created_at")),
        )
    # GitHub does not order deliveries, and two may be processed at once, so the order rule is
    # part of the upsert (the row is locked while it is checked). A merge is final: a merge event
    # always applies and nothing changes a merged PR. Any other event applies only when its
    # pull_request.updated_at is newer than the newest applied; on a tie only a close does, and
    # the head stays as stored. An event with no updated_at (older payloads) always applies.
    applied = conn.execute(
        text(
            "INSERT INTO pull_requests (repo_id, number, run_id, state, draft, head_sha, "
            "pr_updated_at) "
            "VALUES (CAST(:p AS uuid), :n, :r, :st, :d, :h, :u) ON CONFLICT (repo_id, number) DO "
            "UPDATE SET "
            "run_id = coalesce(pull_requests.run_id, EXCLUDED.run_id), "
            "state = CASE WHEN EXCLUDED.state = 'open' AND pull_requests.state = 'closed' "
            "AND NOT :reopen THEN pull_requests.state ELSE EXCLUDED.state END, "
            "draft = EXCLUDED.draft, "
            "head_sha = coalesce(EXCLUDED.head_sha, pull_requests.head_sha), "
            "pr_updated_at = greatest(pull_requests.pr_updated_at, EXCLUDED.pr_updated_at) "
            "WHERE pull_requests.state <> 'merged' AND (EXCLUDED.state = 'merged' "
            "OR EXCLUDED.pr_updated_at IS NULL OR pull_requests.pr_updated_at IS NULL "
            "OR EXCLUDED.pr_updated_at > pull_requests.pr_updated_at "
            "OR (EXCLUDED.pr_updated_at = pull_requests.pr_updated_at "
            "AND EXCLUDED.state <> 'open')) "
            "RETURNING 1"
        ),
        {
            "p": repo_id,
            "n": number,
            "r": run_id,
            "st": state,
            "d": bool(pr.get("draft")),
            "h": head,
            "u": _ts(pr["updated_at"]) if pr.get("updated_at") else None,
            "reopen": action == "reopened",
        },
    ).first()
    if applied is not None or state == "open":
        # A superseded close is not recorded; opened_at (coalesce, from created_at) always is.
        conn.execute(
            text(
                f"UPDATE pull_requests SET {cols} WHERE repo_id = CAST(:p AS uuid) AND number = :n"
            ),
            {"p": repo_id, "n": number, "t": t},
        )
    return "stored"


def _review(conn: Connection, event: str, payload: dict[str, Any], repos: Sequence[Any]) -> str:
    number = int((payload.get("pull_request") or {}).get("number", 0))
    ids = [r.id for r in repos]
    if event == "pull_request_review":
        review = payload.get("review") or {}
        changes = str(review.get("state", "")).lower() == "changes_requested"
        n = conn.execute(
            text(
                "UPDATE pull_requests SET review_count = review_count + 1, "
                "first_review_at = coalesce(first_review_at, :t), changes_requested = "
                "changes_requested OR :c "
                "WHERE repo_id = ANY(CAST(:ids AS uuid[])) AND number = :n"
            ),
            {"t": _ts(review.get("submitted_at")), "c": changes, "ids": ids, "n": number},
        ).rowcount
    else:
        n = conn.execute(
            text(
                "UPDATE pull_requests SET review_comments = review_comments + 1 "
                "WHERE repo_id = ANY(CAST(:ids AS uuid[])) AND number = :n"
            ),
            {"ids": ids, "n": number},
        ).rowcount
    return "stored" if n else "ignored"


def ci_check_patterns(s: Settings) -> list[str]:
    return [n.strip() for n in s.ci_check_names.split(",") if n.strip()]


def wanted_check_run(payload: dict[str, Any], patterns: list[str]) -> bool:
    """A check run this service reads: the harness check, or a product check in CI_CHECK_NAMES."""
    name = str((payload.get("check_run") or {}).get("name") or "")
    return name == "tsl-ci-verify" or any(fnmatch.fnmatchcase(name, p) for p in patterns)


def _product_check(
    conn: Connection, action: str, cr: dict[str, Any], name: str, repos: Sequence[Any]
) -> str:
    """One product_ci_runs row per GitHub check run, under every system repo with that name.

    A check run only moves forward: `created` adds it as pending and never overwrites; a
    `completed` sets the conclusion, whatever arrived first. A re-run is a new check run, so
    delivery order never matters; insights_pr_ci_result() reads the newest run per name.
    """
    run_id, head = cr.get("id"), str(cr.get("head_sha") or "")
    if not run_id or not head:
        return "ignored"
    if action == "created" and cr.get("status") == "completed":
        action = "completed"  # already finished when created (a fast failure)
    params = {
        "ids": [r.id for r in repos],
        "id": int(run_id),
        "h": head,
        "c": name[:200],
        "s": _ts(cr["started_at"]) if cr.get("started_at") else None,
    }
    if action == "created":
        if params["s"] is None:
            return "ignored"  # no start time: it could not be ordered or aged out
        conn.execute(
            text(
                "INSERT INTO product_ci_runs (repo_id, check_run_id, head_sha, check_name, status, "
                "started_at) SELECT r, :id, :h, :c, 'pending', :s "
                "FROM unnest(CAST(:ids AS uuid[])) AS r ON CONFLICT DO NOTHING"
            ),
            params,
        )
        return "stored"
    conn.execute(
        text(
            "INSERT INTO product_ci_runs (repo_id, check_run_id, head_sha, check_name, status, "
            "conclusion, started_at, completed_at) "
            "SELECT r, :id, :h, :c, 'completed', :con, :s, :t "
            "FROM unnest(CAST(:ids AS uuid[])) AS r "
            "ON CONFLICT (repo_id, check_run_id) DO UPDATE SET status = 'completed', "
            "conclusion = EXCLUDED.conclusion, completed_at = EXCLUDED.completed_at, "
            "started_at = coalesce(product_ci_runs.started_at, EXCLUDED.started_at)"
        ),
        {
            **params,
            "con": str(cr.get("conclusion") or "")[:40],
            "t": _ts(cr.get("completed_at")),
        },
    )
    return "stored"


def _check_run(
    conn: Connection, payload: dict[str, Any], repos: Sequence[Any], patterns: list[str]
) -> str:
    cr = payload.get("check_run") or {}
    name = str(cr.get("name") or "")
    action = str(payload.get("action") or "")
    if name != "tsl-ci-verify":
        if any(fnmatch.fnmatchcase(name, p) for p in patterns):
            return _product_check(conn, action, cr, name, repos)
        return "ignored"
    # The harness check is read once finished, also when `created` already reports that.
    if action != "completed" and cr.get("status") != "completed":
        return "ignored"
    head = str(cr.get("head_sha") or "")
    prs = cr.get("pull_requests") or []
    number = int(prs[0]["number"]) if prs and prs[0].get("number") else None
    ids = [r.id for r in repos]
    pr = conn.execute(
        text(
            "SELECT repo_id::text FROM pull_requests WHERE repo_id = ANY(CAST(:ids AS uuid[])) "
            "AND head_sha = :h LIMIT 1"
        ),
        {"ids": ids, "h": head},
    ).scalar()
    conn.execute(
        text(
            "INSERT INTO ci_checks (repo_id, head_sha, number, result, codes, source, "
            "checked_at) "
            "VALUES (CAST(:p AS uuid), :h, :n, :res, '{}', 'webhook', :t) ON CONFLICT (repo_id, "
            "head_sha, source) DO UPDATE "
            "SET result = EXCLUDED.result, number = coalesce(EXCLUDED.number, ci_checks.number), "
            ""
            "checked_at = EXCLUDED.checked_at"
        ),
        {
            "p": pr or ids[0],
            "h": head,
            "n": number,
            "res": "pass" if cr.get("conclusion") == "success" else "fail",
            "t": _ts(cr.get("completed_at")),
        },
    )
    return "stored"


def handle(
    s: Settings, hook_id: str, delivery: str, event: str, sig: str | None, raw: bytes
) -> tuple[int, str]:
    with tx("app", s) as conn:
        try:
            hook = conn.execute(
                text(
                    "SELECT secret_enc, enc_key_id FROM github_hooks WHERE hook_id = :h "
                    "AND revoked_at IS NULL"
                ),
                {"h": int(hook_id)},
            ).first()
        except ValueError:
            hook = None
        if hook is None or not verify(
            decrypt(s, bytes(hook.secret_enc), hook.enc_key_id).encode(), raw, sig
        ):
            metrics.WEBHOOK_SIG_FAILURES.inc()
            metrics.AUTH_FAILURES.labels(kind="hmac", reason="signature").inc()
            raise ServiceError("E-ING-07", "Signature does not match or hook unknown")
        try:
            payload = json.loads(raw)
        except ValueError:
            raise ServiceError("E-ING-06", "Payload is not JSON") from None
        action = str(payload.get("action") or "")
        full_name = str((payload.get("repository") or {}).get("full_name") or "")
        if not delivery:
            raise ServiceError("E-ING-06", "X-GitHub-Delivery missing")
        new = conn.execute(
            text(
                "INSERT INTO webhook_deliveries (delivery_id, event, action, repo_full_name, "
                "result) "
                "VALUES (:d, :e, :a, NULL, 'pending') ON CONFLICT DO NOTHING RETURNING "
                "delivery_id"
            ),
            {"d": delivery[:80], "e": event[:40], "a": action[:40]},
        ).scalar()
        if new is None:
            return 200, "duplicate"
        if action not in KEEP.get(event, set()):
            result, status = "ignored", 204
        elif event == "check_run" and not wanted_check_run(payload, ci_check_patterns(s)):
            result, status = "ignored", 204  # filtered by name before any repo lookup
        elif event == "release":
            ok = bool(s.marketplace_repo) and full_name == s.marketplace_repo
            result, status = ("release_pending", 200) if ok else ("ignored", 204)
            if ok:
                metrics.CATALOGUE_UNSYNCED.set(1)
        else:
            repos = _repos(conn, full_name)
            if not repos:
                result, status = "unknown_repo", 204
            elif event == "pull_request":
                result, status = (
                    _pull_request(conn, action, payload["pull_request"], full_name, repos),
                    200,
                )
            elif event in ("pull_request_review", "pull_request_review_comment"):
                result, status = _review(conn, event, payload, repos), 200
            else:
                result, status = _check_run(conn, payload, repos, ci_check_patterns(s)), 200
        conn.execute(
            text(
                "UPDATE webhook_deliveries SET result = :r, repo_full_name = :g WHERE "
                "delivery_id = "
                ""
                ":d"
            ),
            {
                "r": result,
                "g": full_name if result not in ("unknown_repo", "ignored") else None,
                "d": delivery[:80],
            },
        )
        return status, result


@router.post(
    "/v1/webhooks/github",
    summary="GitHub webhook (HMAC)",
    responses={
        200: {"description": "Stored or duplicate"},
        204: {"description": "Ignored"},
        401: {"description": "Bad signature or unknown hook"},
    },
)
async def github_webhook(request: Request) -> Response:
    s: Settings = request.app.state.settings
    t0 = time.perf_counter()
    raw = await request.body()
    h = request.headers
    event = h.get("x-github-event", "")
    try:
        status, result = await run_in_threadpool(
            handle,
            s,
            h.get("x-github-hook-id", ""),
            h.get("x-github-delivery", ""),
            event,
            h.get("x-hub-signature-256"),
            raw,
        )
    finally:
        metrics.WEBHOOK_DURATION.observe(time.perf_counter() - t0)
    request.state.caller = "github"
    metrics.WEBHOOK_DELIVERIES.labels(
        event=event if event in KEEP else "other", result=result
    ).inc()
    return Response(status_code=status)
