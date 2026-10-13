"""``POST /v1/events`` processing (SDD-08 §4.2): validate, de-duplicate, store raw. Never projects.

One transaction per batch. A request is done once the raw rows are committed.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

from sqlalchemy import Connection, text
from sqlalchemy.exc import DBAPIError

from app.config import Settings
from app.ingest import denylist
from app.ingest.schemas import SchemaSet, first_error
from app.obs import metrics
from app.timeutil import parse_iso, utcnow

CI_TYPES = frozenset({"ci.verified"})


@dataclass(frozen=True)
class ClientDenylist:
    version: int = 0
    salt: bytes = b""
    hashes: frozenset[str] = frozenset()


@dataclass
class BatchResult:
    accepted: int = 0
    duplicates: list[str] = field(default_factory=list)
    rejected: list[dict[str, str]] = field(default_factory=list)

    def body(self) -> dict[str, Any]:
        return {"accepted": self.accepted, "duplicates": self.duplicates, "rejected": self.rejected}


def load_client_denylist(conn: Connection) -> ClientDenylist:
    row = conn.execute(
        text("SELECT version, salt, hashes FROM client_denylist ORDER BY version DESC LIMIT 1")
    ).first()
    if row is None:
        return ClientDenylist()
    return ClientDenylist(int(row.version), bytes(row.salt), frozenset(row.hashes))


def check_event(
    ev: Any, schemas: SchemaSet, source: str, deny: ClientDenylist
) -> tuple[str, str] | None:
    """Return (code, reason) for a rejected event, or None when it is acceptable."""
    if not isinstance(ev, dict):
        return "E-ING-01", "event is not an object"
    if denylist.forbidden_key(ev):
        return "E-ING-03", "forbidden field (user, email or name)"
    err = first_error(schemas.envelope, ev)
    if err:
        return "E-ING-01", f"envelope {err}"
    type_, version = str(ev["type"]), int(ev["schema_version"])
    validator = schemas.body_validator(type_, version)
    if validator is None:
        return "E-ING-02", f"unknown schema_version {version} for {type_}"
    err = first_error(validator, ev["body"])
    if err:
        return "E-ING-01", f"body {err}"
    if source == "ci" and type_ not in CI_TYPES:
        return "E-ING-05", f"CI token may not send {type_}"
    rule = denylist.check_body(ev["body"])
    if rule:
        return "E-ING-04", f"deny-list rule {rule}"
    if denylist.client_hit(deny.salt, deny.hashes, ev["body"]):
        return "E-ING-04", "deny-list rule client-name"
    return None


def ingest(
    conn: Connection,
    s: Settings,
    schemas: SchemaSet,
    events: list[Any],
    source: str,
    user_id: str | None,
) -> BatchResult:
    res = BatchResult()
    deny = load_client_denylist(conn)
    now = utcnow()
    good: list[dict[str, Any]] = []
    seen: set[str] = set()
    for ev in events:
        bad = check_event(ev, schemas, source, deny)
        eid = str(ev.get("event_id", "")) if isinstance(ev, dict) else ""
        if bad:
            res.rejected.append({"event_id": eid, "code": bad[0], "reason": bad[1]})
            metrics.EVENTS_REJECTED.labels(code=bad[0]).inc()
            continue
        if eid in seen:
            res.duplicates.append(eid)
            continue
        seen.add(eid)
        good.append(ev)
    if good:
        ids = [str(e["event_id"]) for e in good]
        new = set(
            conn.execute(
                text(
                    "INSERT INTO event_ids (event_id, received_at) "
                    "SELECT unnest(CAST(:ids AS text[])), :now ON CONFLICT DO NOTHING RETURNING "
                    "event_id"
                ),
                {"ids": ids, "now": now},
            ).scalars()
        )
        rows = []
        for e in good:
            eid = str(e["event_id"])
            if eid not in new:
                res.duplicates.append(eid)
                metrics.EVENTS_DUPLICATE.labels(source=source).inc()
                continue
            occurred = parse_iso(str(e["occurred_at"]))
            rows.append(
                {
                    "event_id": eid,
                    "received_at": now,
                    "occurred_at": occurred,
                    "clock_skew": occurred > now + timedelta(seconds=s.clock_skew_s),
                    "type": e["type"],
                    "schema_version": int(e["schema_version"]),
                    "run_id": e.get("run_id"),
                    "user_id": user_id,
                    "source": source,
                    "body": json.dumps(e["body"], separators=(",", ":")),
                }
            )
            metrics.EVENTS_RECEIVED.labels(type=str(e["type"]), source=source).inc()
            metrics.DELIVERY_DELAY.labels(source=source).observe(
                max(0.0, (now - occurred).total_seconds())
            )
        if rows:
            _insert_raw(conn, rows)
        res.accepted = len(rows)
    metrics.BATCH_EVENTS.observe(len(events))
    return res


INSERT_RAW = text(
    "INSERT INTO events_raw (event_id, received_at, occurred_at, clock_skew, type, schema_version, "
    "run_id, "
    "user_id, source, body) VALUES (:event_id, :received_at, :occurred_at, :clock_skew, :type, "
    ":schema_version, :run_id, CAST(:user_id AS uuid), :source, CAST(:body AS jsonb))"
)


def _insert_raw(conn: Connection, rows: list[dict[str, Any]]) -> None:
    sp = conn.begin_nested()
    try:
        conn.execute(INSERT_RAW, rows)
        sp.commit()
    except DBAPIError as exc:
        sp.rollback()
        if "no partition" not in str(exc.orig):
            raise
        # Partition job late (AL-20 fires): create the current month and retry once.
        conn.execute(text("SELECT insights_ensure_partition('events_raw', CAST(now() AS date))"))
        conn.execute(INSERT_RAW, rows)
