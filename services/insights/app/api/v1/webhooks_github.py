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


def _pr_applies(cur: Any, action: str, state: str, u: Any, before: str | None) -> bool:
    """Whether a pull_request event changes the stored row (GitHub does not order deliveries).

    A merge is final: a merge always applies and nothing changes a merged PR. Otherwise the
    newer `pull_request.updated_at` wins. GitHub stamps whole seconds, so on a tie: a push
    applies only when it continues the stored head (`before` is the stored head; one that comes
    before its predecessor is kept in pr_tie_pushes and followed once that one applies, so pushes
    in one second end on the last); a reopen applies (on a PR already open it only records that a
    reopen happened in that second); a close applies unless
    the stored state came from a reopen in that second (GitHub only reopens a closed PR, so that
    close came first); a tied `opened` came late and does not apply; any other event applies but
    keeps the stored head, the stored reopen marker and a cleared draft flag.
    """
    if cur.state == "merged":
        return False
    if state == "merged" or u is None or cur.pr_updated_at is None or u > cur.pr_updated_at:
        return True
    if u < cur.pr_updated_at:
        return False
    if action == "synchronize":
        return before is not None and before == cur.head_sha
    if action == "reopened":
        return True  # the close it follows came first; on an open PR it only sets the marker
    if action == "closed":
        return bool(cur.pr_last_action != "reopened")
    return action != "opened"  # opened is always the first event: a tie means it came late


def _pull_request(
    conn: Connection,
    action: str,
    payload: dict[str, Any],
    full_name: str,
    repos: Sequence[Any],
) -> str:
    pr = payload["pull_request"]
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
    u = _ts(pr["updated_at"]) if pr.get("updated_at") else None
    key = {"p": repo_id, "n": number}
    vals = {**key, "r": run_id, "st": state, "d": bool(pr.get("draft")), "h": head, "u": u}
    inserted = conn.execute(
        text(
            "INSERT INTO pull_requests (repo_id, number, run_id, state, draft, head_sha, "
            "pr_updated_at, pr_last_action) VALUES (CAST(:p AS uuid), :n, :r, :st, :d, :h, :u, "
            ":a) ON CONFLICT (repo_id, number) DO NOTHING RETURNING 1"
        ),
        {**vals, "a": action},
    ).first()
    applies = inserted is not None
    if not applies:
        # Deliveries may be handled at once: the row stays locked while the rule is checked.
        cur = conn.execute(
            text(
                "SELECT state, head_sha, pr_updated_at, pr_last_action, pr_tie_pushes "
                "FROM pull_requests WHERE repo_id = CAST(:p AS uuid) AND number = :n FOR UPDATE"
            ),
            key,
        ).one()
        before = payload.get("before") if action == "synchronize" else None
        tie = u is not None and u == cur.pr_updated_at
        pushes: dict[str, str] = dict(cur.pr_tie_pushes or {})
        applies = _pr_applies(cur, action, state, u, before)
        if applies:
            if u is not None and (cur.pr_updated_at is None or u > cur.pr_updated_at):
                pushes = {}  # pushes kept from an older second can no longer apply
            # On a tie only a push or a close moves the head: a closed PR gets no more pushes,
            # so its head is the last; an open, reopen or ready event may predate a push.
            keep = tie and action not in ("synchronize", "closed")
            new_head = cur.head_sha if keep or not head else head
            while new_head in pushes:  # a same-second push that arrived before this one
                new_head = pushes.pop(new_head)
            new_state = state
            # GitHub sends pushes and ready_for_review only for open PRs, so a newer one means
            # the PR was reopened (its `reopened` delivery may come later, and is then older).
            implied_reopen = (
                action in ("synchronize", "ready_for_review")
                and u is not None
                and cur.pr_updated_at is not None
                and u > cur.pr_updated_at
            )
            reopens = action == "reopened" or implied_reopen
            if state == "open" and cur.state == "closed" and not reopens:
                new_state = "closed"  # only a (real or implied) reopen opens a closed PR
            if new_state != "open":
                pushes = {}  # a closed or merged PR gets no more pushes
            conn.execute(
                text(
                    "UPDATE pull_requests SET run_id = coalesce(run_id, :r), state = :st, "
                    # On a tie, draft only clears (ready_for_review); a payload snapshotted
                    # before it in that second must not set it again.
                    "draft = CASE WHEN :tie THEN draft AND :d ELSE :d END, head_sha = :h, "
                    "pr_updated_at = greatest(pr_updated_at, CAST(:u AS timestamptz)), "
                    # On a tie only a state change replaces the marker the close rule reads.
                    "pr_last_action = CASE WHEN :keep_la THEN pr_last_action ELSE :a END, "
                    "pr_tie_pushes = CAST(:tp AS jsonb) "
                    "WHERE repo_id = CAST(:p AS uuid) AND number = :n"
                ),
                {
                    **vals,
                    "st": new_state,
                    "h": new_head,
                    "a": action,
                    "tie": tie,
                    "keep_la": tie and action not in ("closed", "reopened"),
                    "tp": json.dumps(pushes),
                },
            )
        else:
            if tie and action == "synchronize" and before and head and cur.state == "open":
                # Not the successor of the stored head yet: keep it until its predecessor comes.
                pushes[str(before)] = str(head)
            elif cur.state != "open":
                pushes = {}
            # The event changes nothing, but a merge tsl pr-sync recorded first (the projector
            # carries no head) still gets a head: the webhook merge's own head is the PR's last
            # and is final; until it arrives, the newest other event's head stands in.
            new_head, new_u, la = cur.head_sha, None, cur.pr_last_action
            if cur.state == "merged" and head:
                if state == "merged":
                    new_head, new_u, la = head, u, "closed"
                elif cur.pr_last_action != "closed" and (
                    cur.head_sha is None
                    or (u is not None and (cur.pr_updated_at is None or u > cur.pr_updated_at))
                ):
                    new_head, new_u = head, u
            elif cur.head_sha is None:
                new_head = head
            conn.execute(
                text(
                    "UPDATE pull_requests SET run_id = coalesce(run_id, :r), head_sha = :h, "
                    "pr_updated_at = greatest(pr_updated_at, CAST(:u AS timestamptz)), "
                    "pr_last_action = :a, pr_tie_pushes = CAST(:tp AS jsonb) "
                    "WHERE repo_id = CAST(:p AS uuid) AND number = :n"
                ),
                {
                    **key,
                    "r": run_id,
                    "h": new_head,
                    "u": new_u,
                    "a": la,
                    "tp": json.dumps(pushes),
                },
            )
            if state == "merged":
                conn.execute(
                    text(
                        "UPDATE pull_requests SET merged_at = coalesce(merged_at, :t) "
                        "WHERE repo_id = CAST(:p AS uuid) AND number = :n"
                    ),
                    {**key, "t": t},
                )
    if applies or state == "open":
        # A superseded close is not recorded; opened_at (coalesce, from created_at) always is.
        conn.execute(
            text(
                f"UPDATE pull_requests SET {cols} WHERE repo_id = CAST(:p AS uuid) AND number = :n"
            ),
            {**key, "t": t},
        )
    # A harness result that came before the PR row was stored under every system repo with this
    # GitHub name; now that this PR has the head, the copies where no PR has it go, so other
    # systems sharing the repo don't count it as verified.
    others = [r.id for r in repos if r.id != repo_id]
    if others:
        conn.execute(
            text(
                "DELETE FROM ci_checks c USING pull_requests p "
                "WHERE p.repo_id = CAST(:p AS uuid) AND p.number = :n AND p.head_sha IS NOT NULL "
                "AND c.source = 'webhook' AND c.head_sha = p.head_sha "
                "AND c.repo_id = ANY(CAST(:o AS uuid[])) AND NOT EXISTS (SELECT 1 FROM "
                "pull_requests q WHERE q.repo_id = c.repo_id AND q.head_sha = c.head_sha)"
            ),
            {**key, "o": others},
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


# Conclusions that are not a result: the run was skipped, cancelled or never ran. A completed
# run without a conclusion is treated the same way. insights_pr_ci_result() (migration 0008)
# repeats this list for product checks; test_no_result_lists_match keeps them equal.
NO_RESULT = ("skipped", "neutral", "cancelled", "stale", "action_required")


def _harness_result(action: str, cr: dict[str, Any]) -> bool:
    """The harness check carries a result: it finished, with a conclusion that is one."""
    finished = action == "completed" or cr.get("status") == "completed"
    return finished and bool(cr.get("conclusion")) and cr.get("conclusion") not in NO_RESULT


def wanted_check_run(payload: dict[str, Any], patterns: list[str]) -> bool:
    """A check run this service reads: a finished harness check with a result, or a product
    check in CI_CHECK_NAMES. Everything else is answered 204 before any repo lookup."""
    cr = payload.get("check_run") or {}
    name = str(cr.get("name") or "")
    if name == "tsl-ci-verify":
        return _harness_result(str(payload.get("action") or ""), cr)
    return any(fnmatch.fnmatchcase(name, p) for p in patterns)


def _product_check(
    conn: Connection, action: str, cr: dict[str, Any], name: str, repos: Sequence[Any]
) -> str:
    """One product_ci_runs row per GitHub check run, under every system repo with that name.

    A check run only moves forward: `created` adds it as pending and never overwrites; a
    `completed` sets the conclusion, whatever arrived first. A re-run is a new check run, so
    delivery order never matters. insights_pr_ci_result() reads the newest run of each check
    (app, check suite, name): one job of one workflow run.
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
        # A workflow run is one check suite; the app tells GitHub Actions from other CI apps.
        "su": int((cr.get("check_suite") or {}).get("id") or 0),
        "ap": int((cr.get("app") or {}).get("id") or 0),
    }
    if action == "created":
        if params["s"] is None:
            return "ignored"  # no start time: it could not be ordered or aged out
        conn.execute(
            text(
                "INSERT INTO product_ci_runs (repo_id, check_run_id, head_sha, check_name, "
                "suite_id, app_id, status, started_at) SELECT r, :id, :h, :c, :su, :ap, "
                "'pending', :s "
                "FROM unnest(CAST(:ids AS uuid[])) AS r ON CONFLICT DO NOTHING"
            ),
            params,
        )
        return "stored"
    conn.execute(
        text(
            "INSERT INTO product_ci_runs (repo_id, check_run_id, head_sha, check_name, "
            "suite_id, app_id, status, conclusion, started_at, completed_at) "
            "SELECT r, :id, :h, :c, :su, :ap, 'completed', :con, :s, :t "
            "FROM unnest(CAST(:ids AS uuid[])) AS r "
            "ON CONFLICT (repo_id, check_run_id) DO UPDATE SET status = 'completed', "
            "conclusion = EXCLUDED.conclusion, completed_at = EXCLUDED.completed_at, "
            "started_at = coalesce(product_ci_runs.started_at, EXCLUDED.started_at), "
            "suite_id = greatest(product_ci_runs.suite_id, EXCLUDED.suite_id), "
            "app_id = greatest(product_ci_runs.app_id, EXCLUDED.app_id)"
        ),
        {
            **params,
            "con": str(cr["conclusion"])[:40] if cr.get("conclusion") else None,  # NULL: none
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
    # The harness check is read once finished with a result, also when `created` already
    # reports that; skipped, cancelled and the like record nothing (wanted_check_run).
    if not _harness_result(action, cr):
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
    # Under the PR's repo; before the PR row exists, under every system repo with that GitHub
    # name (as product checks are), so no system's PR misses it.
    conn.execute(
        text(
            "INSERT INTO ci_checks (repo_id, head_sha, number, result, codes, source, "
            "checked_at) "
            "SELECT r, :h, :n, :res, '{}', 'webhook', :t FROM unnest(CAST(:ids AS uuid[])) AS r "
            "ON CONFLICT (repo_id, head_sha, source) DO UPDATE "
            "SET result = EXCLUDED.result, number = coalesce(EXCLUDED.number, ci_checks.number), "
            "checked_at = EXCLUDED.checked_at"
        ),
        {
            "ids": [pr] if pr else ids,
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
                    _pull_request(conn, action, payload, full_name, repos),
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
