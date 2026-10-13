"""Prometheus metrics (OPS-02 §5). Labels come only from fixed enums (§5.1).

The registry is the default ``prometheus_client`` registry. Under ``uvicorn --workers 2`` the
entrypoint sets ``PROMETHEUS_MULTIPROC_DIR`` and serves a multiprocess collector on the internal
port; ``/metrics`` is never mounted on the public app (OPS-02 §11).
"""

from __future__ import annotations

import os
import time
from collections.abc import Awaitable, Callable
from typing import Any

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from prometheus_client import multiprocess as _mp

BUCKETS = (0.05, 0.1, 0.25, 0.5, 0.8, 1, 2, 5, 10)
DELAY_BUCKETS = (1, 10, 60, 300, 3600, 21600, 86400, 259200, 604800)
_GAUGE_MODE: Any = (
    {"multiprocess_mode": "livemax"} if os.environ.get("PROMETHEUS_MULTIPROC_DIR") else {}
)

HTTP_REQUESTS = Counter(
    "insights_http_requests_total",
    "Every response",
    ["route", "route_group", "method", "status_class"],
)
HTTP_DURATION = Histogram(
    "insights_http_request_duration_seconds",
    "Time to response",
    ["route", "route_group", "method"],
    buckets=BUCKETS,
)
EVENTS_RECEIVED = Counter("insights_events_received_total", "Events accepted", ["type", "source"])
EVENTS_DUPLICATE = Counter("insights_events_duplicate_total", "Duplicate events", ["source"])
EVENTS_REJECTED = Counter("insights_events_rejected_total", "Per-event rejects", ["code"])
DELIVERY_DELAY = Histogram(
    "insights_event_delivery_delay_seconds",
    "received_at - occurred_at",
    ["source"],
    buckets=DELAY_BUCKETS,
)
BATCH_EVENTS = Histogram(
    "insights_batch_events", "Events per batch", buckets=(1, 10, 50, 100, 250, 500)
)
RATE_LIMITED = Counter("insights_rate_limited_total", "429 responses", ["route_group"])
AUTH_FAILURES = Counter("insights_auth_failures_total", "401 causes", ["kind", "reason"])
OTEL_KEPT = Counter("insights_otel_datapoints_total", "OTLP points kept", ["signal"])
OTEL_DROPPED = Counter("insights_otel_dropped_total", "OTLP points dropped", ["reason"])
WEBHOOK_DELIVERIES = Counter(
    "insights_webhook_deliveries_total", "GitHub deliveries", ["event", "result"]
)
WEBHOOK_SIG_FAILURES = Counter(
    "insights_webhook_signature_failures_total", "Bad HMAC or unknown hook"
)
WEBHOOK_DURATION = Histogram(
    "insights_webhook_duration_seconds", "Webhook handling time", buckets=BUCKETS
)
READ_SCOPE_DENIED = Counter(
    "insights_read_scope_denied_total", "Role or scope refusals", ["route", "code"]
)
NAME_REVEALS = Counter("insights_name_reveals_total", "Requests that returned names", ["route"])
ANCHOR_MISMATCH = Counter(
    "insights_anchor_mismatch_total", "Anchors ignored: key not the event user's"
)
DB_POOL_IN_USE = Gauge("insights_db_pool_in_use", "Connections in use", ["process"], **_GAUGE_MODE)
DB_POOL_SIZE = Gauge("insights_db_pool_size", "Pool size", ["process"], **_GAUGE_MODE)
# worker
PROJECTION_BACKLOG = Gauge("insights_projection_backlog_events", "Unprojected rows")
PROJECTION_LAG = Gauge("insights_projection_lag_seconds", "Projection lag")
PROJECTION_PARKED = Gauge("insights_projection_parked_events", "Parked rows", ["code"])
PROJECTED = Counter("insights_projected_total", "Events projected", ["type"])
PROJECTION_ERRORS = Counter(
    "insights_projection_errors_total", "Handler failures", ["type", "code"]
)
VIEW_AGE = Gauge("insights_view_refresh_age_seconds", "Age of each view", ["view"])
VIEW_DURATION = Gauge("insights_view_refresh_duration_seconds", "Last refresh time", ["view"])
VIEW_FAILURES = Counter("insights_view_refresh_failures_total", "Failed refreshes", ["view"])
JOB_LAST_SUCCESS = Gauge("insights_job_last_success_timestamp", "Last success", ["job"])
JOB_FAILURES = Counter("insights_job_failures_total", "Failed job runs", ["job"])
WORKER_LEADER = Gauge("insights_worker_leader", "1 when this worker holds the lock")
WORKER_HEARTBEAT = Gauge("insights_worker_heartbeat_timestamp", "Main loop tick")
PARTITIONS_AHEAD = Gauge("insights_partitions_ahead", "Future monthly partitions", ["table"])
CATALOGUE_SKIPPED = Counter(
    "insights_catalogue_items_skipped_total", "Invalid catalogue files", ["kind"]
)
CATALOGUE_LAST_SYNC = Gauge("insights_catalogue_last_sync_timestamp", "Last successful sync")
CATALOGUE_UNSYNCED = Gauge("insights_catalogue_unsynced_release", "Latest tag not synced")
DB_SIZE = Gauge("insights_db_size_bytes", "Database size")
DB_TABLE_BYTES = Gauge("insights_db_table_bytes", "Largest tables", ["table"])
DEVICES_SEEN = Gauge("insights_devices_seen", "Devices seen", ["window"])
DEVICES_OUTBOX_NONEMPTY = Gauge("insights_devices_outbox_nonempty", "Devices with queued events")
DEVICES_OUTBOX_EVENTS = Gauge("insights_devices_outbox_events", "Queued events on devices")
DEVICES_OUTBOX_STALE = Gauge("insights_devices_outbox_stale", "Stale outboxes", ["age"])
DEVICES_OUTBOX_OLDEST = Gauge("insights_devices_outbox_oldest_age_seconds", "Oldest outbox age")
INGEST_TOKEN_AGE = Gauge(
    "insights_ingest_token_last_used_age_seconds", "Token last-used age", ["kind"]
)

ALLOWED_LABELS = {
    "route",
    "route_group",
    "method",
    "status_class",
    "type",
    "source",
    "code",
    "view",
    "job",
    "table",
    "reason",
    "kind",
    "signal",
    "event",
    "result",
    "window",
    "age",
    "process",
}

READ_PREFIXES = (
    "/v1/me",
    "/v1/status",
    "/v1/catalogue",
    "/v1/pods",
    "/v1/capability-map",
    "/v1/insights",
    "/v1/runs",
    "/v1/improvement",
)
INGEST_PREFIXES = ("/v1/events", "/otel/", "/v1/webhooks/github")


def route_group(path_template: str) -> str:
    if path_template.startswith(INGEST_PREFIXES):
        return "ingest"
    if path_template.startswith("/v1/health"):
        return "health"
    if path_template.startswith(READ_PREFIXES):
        return "read"
    if path_template.startswith("/v1/"):
        return "write"
    return "static"


def observe(route: str, method: str, status: int, seconds: float) -> None:
    group = route_group(route)
    HTTP_REQUESTS.labels(
        route=route,
        route_group=group,
        method=method,
        status_class="429" if status == 429 else f"{status // 100}xx",
    ).inc()
    HTTP_DURATION.labels(route=route, route_group=group, method=method).observe(seconds)


def exposition() -> tuple[bytes, str]:
    if os.environ.get("PROMETHEUS_MULTIPROC_DIR"):
        reg = CollectorRegistry()
        _mp.MultiProcessCollector(reg)  # type: ignore[no-untyped-call]
        return generate_latest(reg), CONTENT_TYPE_LATEST
    return generate_latest(), CONTENT_TYPE_LATEST


ASGIApp = Callable[
    [
        dict[str, Any],
        Callable[[], Awaitable[dict[str, Any]]],
        Callable[[dict[str, Any]], Awaitable[None]],
    ],
    Awaitable[None],
]


def metrics_app(health: Callable[[], bool] | None = None) -> ASGIApp:
    """ASGI app for the internal port: ``/metrics`` and (worker) ``/healthz``."""

    async def app(
        scope: dict[str, Any],
        receive: Callable[[], Awaitable[dict[str, Any]]],
        send: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> None:
        if scope["type"] != "http":
            return
        path = scope.get("path", "")
        if path == "/metrics":
            body, ctype = exposition()
            status = 200
        elif path == "/healthz" and health is not None:
            ok = health()
            body, ctype, status = (
                b'{"status":"ok"}' if ok else b'{"status":"fail"}',
                "application/json",
                200 if ok else 503,
            )
        else:
            body, ctype, status = b"not found", "text/plain", 404
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [(b"content-type", ctype.encode())],
            }
        )
        await send({"type": "http.response.body", "body": body})

    return app


def now() -> float:
    return time.time()
