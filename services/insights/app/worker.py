"""``python -m app.worker``: projector loop and scheduled jobs (SDD-08 §3.2).

One leader at a time (``pg_try_advisory_lock``). Jobs: view refresh every 5 min, outbox gauges
every 5 min, lag sampler every 15 s, partitions hourly, retention and rollup daily, improvement
report weekly, catalogue sync hourly when ``CATALOGUE_SOURCE_DIR`` is set.
"""

from __future__ import annotations

import logging
import signal
import threading
import time
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from sqlalchemy import Connection, text

from app.config import Settings, get_settings
from app.db import engine
from app.jobs import improvement_report, outbox_watch, partitions, refresh_views, retention
from app.obs import logging as obslog
from app.obs import metrics
from app.projector.loop import project_batch, sample_lag

log = logging.getLogger("insights.worker")
LOCK_KEY = 0x7473_6C49  # "tslI"


class Schedule:
    def __init__(self) -> None:
        self.last: dict[str, float] = {}

    def due(self, name: str, every_s: float, now: float) -> bool:
        if now - self.last.get(name, 0.0) >= every_s:
            self.last[name] = now
            return True
        return False


def run_job(name: str, fn: Callable[[], Any]) -> bool:
    try:
        fn()
        metrics.JOB_LAST_SUCCESS.labels(job=name).set(time.time())
        log.info("job done", extra={"job": name})
        return True
    except Exception:
        metrics.JOB_FAILURES.labels(job=name).inc()
        log.exception("job failed", extra={"job": name})
        return False


def tick(s: Settings, sched: Schedule, now: float) -> int:
    """One iteration of the worker loop. Returns the number of events projected."""
    projected, _parked = project_batch(s)
    if sched.due("lag", 15, now):
        run_job("lag", lambda: sample_lag(s))
    if sched.due("partitions", 3600, now):
        run_job("partitions", lambda: partitions.run(s))
    if sched.due("refresh_views", s.view_refresh_interval_s, now):
        run_job("refresh_views", lambda: refresh_views.run(s))
    if sched.due("outbox_watch", 300, now):
        run_job("outbox_watch", lambda: outbox_watch.run(s))
    if sched.due("retention", 86400, now):
        run_job("retention", lambda: retention.run(s))
        metrics.JOB_LAST_SUCCESS.labels(job="rollup").set(time.time())
    if sched.due("improvement_report", 3600, now) and improvement_report.due(s):
        run_job("improvement_report", lambda: improvement_report.run(s))
    if s.catalogue_source_dir and sched.due("catalogue_sync", 3600, now):
        from app.catalogue.sync import sync

        root = s.catalogue_source_dir
        tag_file = root / ".release-tag"
        if tag_file.exists():
            tag, _, sha = tag_file.read_text(encoding="utf-8").strip().partition(" ")
            run_job("catalogue_sync", lambda: sync(s, root, tag, sha or "unknown"))
    return projected


_heartbeat = {"t": 0.0}


def _health_server(port: int) -> ThreadingHTTPServer:
    class H(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path == "/metrics":
                body, ctype = metrics.exposition()
                code = 200
            elif self.path == "/healthz":
                ok = time.time() - _heartbeat["t"] < 30
                body, ctype, code = (
                    (b'{"status":"ok"}' if ok else b'{"status":"fail"}'),
                    "application/json",
                    (200 if ok else 503),
                )
            else:
                body, ctype, code = b"not found", "text/plain", 404
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args: Any) -> None:
            return

    srv = ThreadingHTTPServer(("0.0.0.0", port), H)  # noqa: S104 - internal network only (OPS-02 §4.1)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def try_lead(conn: Connection) -> bool:
    """Take the worker leader lock on this session if it is free (non-blocking)."""
    leader = bool(conn.execute(text("SELECT pg_try_advisory_lock(:k)"), {"k": LOCK_KEY}).scalar())
    conn.commit()
    return leader


def run_loop(
    s: Settings,
    stop: threading.Event,
    tick_fn: Callable[[Settings, Schedule, float], int] = tick,
    retry_s: float = 10,
) -> None:
    """Wait for the leader lock, then run ``tick_fn`` until ``stop``. One leader at a time.

    The lock lives on a dedicated session, so it is released when this process stops or its
    connection drops (for example when a hosted database scales to zero); another instance then
    takes over.
    """
    sched = Schedule()
    with engine("app", s).connect() as lock_conn:
        while not stop.is_set():
            _heartbeat["t"] = time.time()
            metrics.WORKER_HEARTBEAT.set(time.time())
            leader = try_lead(lock_conn)
            metrics.WORKER_LEADER.set(1 if leader else 0)
            if not leader:
                stop.wait(retry_s)
                continue
            while not stop.is_set():
                _heartbeat["t"] = time.time()
                metrics.WORKER_HEARTBEAT.set(time.time())
                try:
                    n = tick_fn(s, sched, time.monotonic())
                except Exception:
                    log.exception("worker tick failed")
                    n = 0
                stop.wait(1 if n else 5)


def main() -> None:
    obslog.setup("worker")
    s = get_settings()
    _health_server(s.worker_metrics_port)
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    run_loop(s, stop)


if __name__ == "__main__":
    main()
