"""OTLP/HTTP receiver: ``POST /otel/v1/metrics`` and ``/otel/v1/logs`` (SDD-08 §5).

Protobuf and JSON are both accepted; gzip request bodies are accepted. Traces are not accepted
(no route, so 404). OTel carries no run id: points are attributed through ``run_sessions`` (§5.4).
"""

from __future__ import annotations

import gzip
import json
import zlib
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request, Response
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import Connection, text
from sqlalchemy.exc import DBAPIError

from app.auth.principal import authenticate
from app.config import Settings
from app.db import tx
from app.errors import ServiceError
from app.obs import metrics
from app.otel.decode import (
    Allowlist,
    DecodeError,
    Row,
    empty_response,
    load_allowlist,
    logs_rows,
    metrics_rows,
    parse,
)

router = APIRouter(tags=["otel"])
USAGE_FIELDS = {"tokens_in", "tokens_out", "cost_usd", "active_s"}


@lru_cache(maxsize=4)
def _allowlist(path: Path) -> Allowlist:
    return load_allowlist(path)


def _attribute(conn: Connection, session_id: str | None, ts: Any) -> str | None:
    if not session_id:
        return None
    ids = (
        conn.execute(
            text(
                "SELECT run_id FROM run_sessions WHERE session_id = :s AND :ts BETWEEN "
                "first_seen_at "
                "AND last_seen_at + interval '10 minutes' LIMIT 2"
            ),
            {"s": session_id, "ts": ts},
        )
        .scalars()
        .all()
    )
    return ids[0] if len(ids) == 1 else None


INSERT = text(
    "INSERT INTO otel_events (signal, name, ts, session_id, run_id, value, attributes) "
    "VALUES (:signal, :name, :ts, :sid, :run, :value, CAST(:attrs AS jsonb))"
)


def store(conn: Connection, rows: list[Row]) -> None:
    params = []
    for r in rows:
        run = _attribute(conn, r.session_id, r.ts)
        params.append(
            {
                "signal": r.signal,
                "name": r.name,
                "ts": r.ts,
                "sid": r.session_id,
                "run": run,
                "value": r.value,
                "attrs": json.dumps(r.attributes, separators=(",", ":")),
            }
        )
        for f in r.usage:
            if run and f in USAGE_FIELDS and r.value is not None:
                conn.execute(
                    text(
                        f"INSERT INTO run_usage (run_id, {f}) VALUES (:r, :v) "
                        f"ON CONFLICT (run_id) DO UPDATE SET {f} = run_usage.{f} + EXCLUDED.{f}"
                    ),
                    {"r": run, "v": r.value},
                )
    if not params:
        return
    sp = conn.begin_nested()
    try:
        conn.execute(INSERT, params)
        sp.commit()
    except DBAPIError as exc:
        sp.rollback()
        if "no partition" not in str(exc.orig):
            raise
        conn.execute(text("SELECT insights_ensure_partition('otel_events', CAST(now() AS date))"))
        conn.execute(INSERT, params)


async def _receive(request: Request, signal: str) -> Response:
    s: Settings = request.app.state.settings
    authenticate(request, route="otel", scopes=set(), allow={"otel"})
    raw = await request.body()
    if len(raw) > s.max_otel_body_bytes:
        raise ServiceError("E-ING-06", "OTLP body too large", status=413)
    if request.headers.get("content-encoding", "").lower() == "gzip":
        try:
            raw = gzip.decompress(raw)
        except (OSError, EOFError, zlib.error):
            metrics.OTEL_DROPPED.labels(reason="decode").inc()
            raise ServiceError("E-ING-06", "Body is not gzip") from None
    ctype = request.headers.get("content-type", "application/x-protobuf")
    try:
        data = parse(raw, ctype, signal)
    except DecodeError:
        metrics.OTEL_DROPPED.labels(reason="decode").inc()
        raise ServiceError("E-ING-06", "Undecodable OTLP body") from None
    al = _allowlist(s.otel_allowlist_file)
    dec = metrics_rows(data, al) if signal == "metric" else logs_rows(data, al)
    for reason, n in dec.dropped.items():
        metrics.OTEL_DROPPED.labels(reason=reason).inc(n)

    def work() -> None:
        with tx("app", s) as conn:
            store(conn, dec.rows)

    if dec.rows:
        await run_in_threadpool(work)
        metrics.OTEL_KEPT.labels(signal=signal).inc(len(dec.rows))
    if ctype.split(";")[0].strip().lower() == "application/json":
        return Response(b"{}", media_type="application/json")
    return Response(empty_response(signal), media_type="application/x-protobuf")


@router.post("/otel/v1/metrics")
async def otel_metrics(request: Request) -> Response:
    return await _receive(request, "metric")


@router.post("/otel/v1/logs")
async def otel_logs(request: Request) -> Response:
    return await _receive(request, "log")
