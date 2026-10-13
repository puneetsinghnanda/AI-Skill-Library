"""Local SQLite outbox and flush (SDD-04 §8, Doc 5 R-04). Events are metadata only (NFR-10)."""

from __future__ import annotations

import json
import sqlite3
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from tsl.core.clock import Clock, iso, parse_iso
from tsl.core.errors import TslError
from tsl.core.ids import IdFactory
from tsl.insights.client import HttpResult, InsightsUnavailable

DDL = """
PRAGMA journal_mode = WAL;
CREATE TABLE IF NOT EXISTS event (
  event_id        TEXT PRIMARY KEY,
  type            TEXT NOT NULL,
  schema_version  INTEGER NOT NULL,
  run_id          TEXT,
  occurred_at     TEXT NOT NULL,
  body            TEXT NOT NULL,
  status          TEXT NOT NULL CHECK (status IN ('pending','sending','sent','dead')),
  attempts        INTEGER NOT NULL DEFAULT 0,
  next_attempt_at TEXT NOT NULL,
  lease_until     TEXT,
  last_error      TEXT,
  created_at      TEXT NOT NULL,
  sent_at         TEXT
);
CREATE INDEX IF NOT EXISTS event_due ON event (status, next_attempt_at);
PRAGMA user_version = 1;
"""

BATCH = 500
LEASE = timedelta(seconds=60)
MAX_BACKOFF = 300


class InvalidEvent(ValueError):
    pass


@dataclass
class FlushResult:
    sent: int = 0
    duplicates: int = 0
    rejected: int = 0
    pending: int = 0
    dead: int = 0
    oldest_pending_at: str | None = None
    auth_failed: bool = False
    offline: bool = False

    def data(self) -> dict[str, Any]:
        return {
            "sent": self.sent,
            "duplicates": self.duplicates,
            "rejected": self.rejected,
            "pending": self.pending,
            "dead": self.dead,
            "oldest_pending_at": self.oldest_pending_at,
        }


def validate_event(event: dict[str, Any]) -> None:
    from tsl.schemas.registry import errors, event_schema_id, index

    env_err = errors("event-envelope.v1", event)
    if env_err:
        raise InvalidEvent(f"envelope {env_err[0].pointer}: {env_err[0].message}")
    sid = event_schema_id(event["type"], event["schema_version"])
    if sid not in index():
        raise InvalidEvent(f"no schema for {sid}")
    body_err = errors(sid, event["body"])
    if body_err:
        raise InvalidEvent(f"body {body_err[0].pointer}: {body_err[0].message}")


class Outbox:
    def __init__(
        self,
        path: Path,
        clock: Clock,
        ids: IdFactory,
        strict: bool = False,
        retain_sent_days: int = 7,
    ) -> None:
        self.path = path
        self.clock = clock
        self.ids = ids
        self.strict = strict
        self.retain = timedelta(days=retain_sent_days)

    def _conn(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        c = sqlite3.connect(str(self.path), timeout=2.0, isolation_level=None)
        c.execute("PRAGMA busy_timeout = 2000")
        c.executescript(DDL)
        return c

    def enqueue(
        self, type_: str, body: dict[str, Any], run_id: str | None = None, schema_version: int = 1
    ) -> str | None:
        now = iso(self.clock())
        event: dict[str, Any] = {
            "event_id": self.ids.new("evt"),
            "type": type_,
            "schema_version": schema_version,
            "occurred_at": now,
            "body": body,
        }
        if run_id:
            event["run_id"] = run_id
        try:
            validate_event(event)
        except InvalidEvent as exc:
            if self.strict:
                raise TslError(
                    "E-INT-01", f"invalid event {type_}: {exc}", log_id="outbox"
                ) from exc
            return None  # never send bad data; dropping one metric is the lesser harm (SDD-04 §8.3)
        c = self._conn()
        try:
            c.execute(
                "INSERT INTO event (event_id, type, schema_version, run_id, occurred_at, body,"
                " status,"
                " attempts, next_attempt_at, created_at) VALUES (?,?,?,?,?,?, 'pending', 0, ?, ?)",
                (
                    event["event_id"],
                    type_,
                    schema_version,
                    run_id,
                    now,
                    json.dumps(body, sort_keys=True),
                    now,
                    now,
                ),
            )
        finally:
            c.close()
        return str(event["event_id"])

    def enqueue_trusted(self, type_: str, body: dict[str, Any], run_id: str | None = None) -> str:
        """Hook fast path: the body is valid by construction (tests check it)."""
        now = iso(self.clock())
        eid = self.ids.new("evt")
        c = self._conn()
        try:
            c.execute(
                "INSERT INTO event (event_id, type, schema_version, run_id, occurred_at, body,"
                " status,"
                " attempts, next_attempt_at, created_at) VALUES (?,?,1,?,?,?, 'pending', 0, ?, ?)",
                (eid, type_, run_id, now, json.dumps(body, sort_keys=True), now, now),
            )
        finally:
            c.close()
        return eid

    def stats(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"pending": 0, "dead": 0, "oldest_pending_at": None, "sent": 0}
        c = self._conn()
        try:
            rows = dict(c.execute("SELECT status, COUNT(*) FROM event GROUP BY status").fetchall())
            oldest = c.execute(
                "SELECT MIN(created_at) FROM event WHERE status IN ('pending','sending')"
            ).fetchone()[0]
        finally:
            c.close()
        return {
            "pending": int(rows.get("pending", 0)) + int(rows.get("sending", 0)),
            "dead": int(rows.get("dead", 0)),
            "sent": int(rows.get("sent", 0)),
            "oldest_pending_at": oldest,
        }

    def events(self, status: str | None = None) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        c = self._conn()
        try:
            q = (
                "SELECT event_id, type, schema_version, run_id, occurred_at, body, status "
                "FROM event"
            )
            rows = c.execute(
                q + (" WHERE status = ?" if status else "") + " ORDER BY created_at, rowid",
                (status,) if status else (),
            ).fetchall()
        finally:
            c.close()
        return [
            {
                "event_id": r[0],
                "type": r[1],
                "schema_version": r[2],
                "run_id": r[3],
                "occurred_at": r[4],
                "body": json.loads(r[5]),
                "status": r[6],
            }
            for r in rows
        ]

    def retry_dead(self) -> int:
        c = self._conn()
        try:
            cur = c.execute(
                "UPDATE event SET status='pending', attempts=0, next_attempt_at=? "
                "WHERE status='dead'",
                (iso(self.clock()),),
            )
            return int(cur.rowcount)
        finally:
            c.close()

    def _lease(self, c: sqlite3.Connection) -> list[tuple[Any, ...]]:
        now = self.clock()
        c.execute("BEGIN IMMEDIATE")
        try:
            rows = c.execute(
                "SELECT event_id, type, schema_version, run_id, occurred_at, body FROM event "
                "WHERE (status='pending' AND next_attempt_at <= ?) "
                "OR (status='sending' AND lease_until < ?) "
                "ORDER BY created_at LIMIT ?",
                (iso(now), iso(now), BATCH),
            ).fetchall()
            for r in rows:
                c.execute(
                    "UPDATE event SET status='sending', lease_until=? WHERE event_id=?",
                    (iso(now + LEASE), r[0]),
                )
            c.execute("COMMIT")
        except BaseException:
            c.execute("ROLLBACK")
            raise
        return rows

    def _release(
        self,
        c: sqlite3.Connection,
        ids: list[str],
        error: str | None,
        backoff: bool,
        retry_after: float | None = None,
    ) -> None:
        now = self.clock()
        for eid in ids:
            if backoff:
                attempts = (
                    int(
                        c.execute("SELECT attempts FROM event WHERE event_id=?", (eid,)).fetchone()[
                            0
                        ]
                    )
                    + 1
                )
                delay = retry_after if retry_after is not None else min(2**attempts, MAX_BACKOFF)
                c.execute(
                    "UPDATE event SET status='pending', attempts=?, next_attempt_at=?, "
                    "lease_until=NULL, last_error=? WHERE event_id=?",
                    (attempts, iso(now + timedelta(seconds=delay)), error, eid),
                )
            else:
                c.execute(
                    "UPDATE event SET status='pending', lease_until=NULL WHERE event_id=?", (eid,)
                )

    def flush(
        self,
        token: Callable[[bool], str],
        post: Callable[[str, list[dict[str, Any]]], HttpResult],
        max_seconds: float = 30.0,
    ) -> FlushResult:
        """SDD-04 §8.3. `token(force_refresh)` raises TslError E-AUTH-01 when it cannot refresh."""
        res = FlushResult()
        deadline = time.monotonic() + max_seconds
        c = self._conn()
        try:
            while time.monotonic() < deadline:
                rows = self._lease(c)
                if not rows:
                    break
                batch = [
                    {
                        "event_id": r[0],
                        "type": r[1],
                        "schema_version": r[2],
                        "occurred_at": r[4],
                        "body": json.loads(r[5]),
                        **({"run_id": r[3]} if r[3] else {}),
                    }
                    for r in rows
                ]
                if not self._send(c, batch, token, post, res):
                    break
            self.housekeep(c)
        finally:
            c.close()
        s = self.stats()
        res.pending, res.dead, res.oldest_pending_at = (
            s["pending"],
            s["dead"],
            s["oldest_pending_at"],
        )
        return res

    def _send(
        self,
        c: sqlite3.Connection,
        batch: list[dict[str, Any]],
        token: Callable[[bool], str],
        post: Callable[[str, list[dict[str, Any]]], HttpResult],
        res: FlushResult,
    ) -> bool:
        ids = [e["event_id"] for e in batch]
        try:
            tok = token(False)
        except TslError:
            self._release(c, ids, None, backoff=False)
            res.auth_failed = True
            return False
        try:
            r = post(tok, batch)
            if r.status == 401:
                try:
                    tok = token(True)
                except TslError:
                    self._release(c, ids, None, backoff=False)
                    res.auth_failed = True
                    return False
                r = post(tok, batch)
                if r.status == 401:
                    self._release(c, ids, None, backoff=False)
                    res.auth_failed = True
                    return False
        except InsightsUnavailable:
            self._release(c, ids, "NET", backoff=True)
            res.offline = True
            return False
        if r.status == 413 and len(batch) > 1:
            self._release(c, ids, None, backoff=False)
            half = len(batch) // 2
            return self._send(c, self._relock(c, batch[:half]), token, post, res) and self._send(
                c, self._relock(c, batch[half:]), token, post, res
            )
        if r.status == 202 and isinstance(r.body, dict):
            now = iso(self.clock())
            rejected = {
                str(x.get("event_id")): str(x.get("code", "E-ING"))
                for x in r.body.get("rejected", [])
                if isinstance(x, dict)
            }
            dups = {str(x) for x in r.body.get("duplicates", [])}
            for eid in ids:
                if eid in rejected:
                    c.execute(
                        "UPDATE event SET status='dead', last_error=?, lease_until=NULL "
                        "WHERE event_id=?",
                        (rejected[eid][:40], eid),
                    )
                    res.rejected += 1
                else:
                    c.execute(
                        "UPDATE event SET status='sent', sent_at=?, lease_until=NULL "
                        "WHERE event_id=?",
                        (now, eid),
                    )
                    if eid in dups:
                        res.duplicates += 1
                    else:
                        res.sent += 1
            return True
        retry_after = None
        if r.status == 429:
            try:
                retry_after = float(r.headers.get("Retry-After", r.headers.get("retry-after", "")))
            except ValueError:
                retry_after = None
        self._release(c, ids, f"HTTP-{r.status}", backoff=True, retry_after=retry_after)
        res.offline = True
        return False

    def _relock(self, c: sqlite3.Connection, batch: list[dict[str, Any]]) -> list[dict[str, Any]]:
        lease = iso(self.clock() + LEASE)
        for e in batch:
            c.execute(
                "UPDATE event SET status='sending', lease_until=? WHERE event_id=?",
                (lease, e["event_id"]),
            )
        return batch

    def housekeep(self, c: sqlite3.Connection) -> None:
        """Delete sent rows older than retain_sent_days. Pending rows are never deleted."""
        cutoff = iso(self.clock() - self.retain)
        c.execute("DELETE FROM event WHERE status='sent' AND sent_at < ?", (cutoff,))

    def oldest_pending_age(self) -> timedelta | None:
        s = self.stats()
        if not s["oldest_pending_at"]:
            return None
        return self.clock() - parse_iso(str(s["oldest_pending_at"]))


def now_utc(clock: Clock) -> datetime:
    return clock()
