"""OTLP/HTTP receiver (SDD-08 §5): JSON and protobuf, gzip, allowlist, content drop, session join."""

from __future__ import annotations

import gzip
import json
import time
from typing import Any

from fastapi.testclient import TestClient
from opentelemetry.proto.collector.metrics.v1.metrics_service_pb2 import ExportMetricsServiceRequest
from opentelemetry.proto.common.v1.common_pb2 import AnyValue, KeyValue
from opentelemetry.proto.metrics.v1.metrics_pb2 import (
    Metric,
    NumberDataPoint,
    ResourceMetrics,
    ScopeMetrics,
    Sum,
)
from sqlalchemy import text
from sqlalchemy.engine import Engine

from tests.conftest import Person, TokenFactory, bearer, event, new_run, post, project, run_started


def _attr(k: str, v: Any) -> dict[str, Any]:
    return {"key": k, "value": {"stringValue": v}}


def metrics_json(
    session: str, value: float, name: str = "test.token.usage", **attrs: str
) -> dict[str, Any]:
    ns = str(time.time_ns())
    return {
        "resourceMetrics": [
            {
                "resource": {"attributes": [_attr("session.id", session)]},
                "scopeMetrics": [
                    {
                        "metrics": [
                            {
                                "name": name,
                                "sum": {
                                    "dataPoints": [
                                        {
                                            "asDouble": value,
                                            "timeUnixNano": ns,
                                            "attributes": [
                                                _attr(k.replace("_", "."), v)
                                                for k, v in attrs.items()
                                            ]
                                            + [
                                                _attr("prompt", "secret text"),
                                                _attr("user.email", "x"),
                                            ],
                                        }
                                    ]
                                },
                            },
                            {
                                "name": "not.allowed.metric",
                                "gauge": {"dataPoints": [{"asInt": "3", "timeUnixNano": ns}]},
                            },
                        ]
                    }
                ],
            }
        ]
    }


def test_json_metrics_kept_dropped_and_attributed(
    client: TestClient,
    otel_token: str,
    token: TokenFactory,
    people: dict[str, Person],
    world: Any,
    migrated: Any,
    owner_db: Engine,
) -> None:
    run_id, sess = new_run(), "sess-otel-1"
    post(
        client,
        token(people["eng"].oid, people["eng"].roles),
        [event("run.started", run_started(world.system, session=sess), run_id)],
        strict=True,
    )
    project(migrated)
    body = metrics_json(sess, 1500, token_type="input")
    r = client.post("/otel/v1/metrics", json=body, headers=bearer(otel_token))
    assert r.status_code == 200 and r.json() == {}
    with owner_db.connect() as c:
        rows = c.execute(
            text("SELECT name, run_id, attributes FROM otel_events WHERE session_id = :s"),
            {"s": sess},
        ).all()
        usage = c.execute(
            text("SELECT tokens_in FROM run_usage WHERE run_id = :r"), {"r": run_id}
        ).scalar_one()
    assert [x.name for x in rows] == ["test.token.usage"]
    assert rows[0].run_id == run_id
    assert "prompt" not in rows[0].attributes and "user.email" not in rows[0].attributes
    assert rows[0].attributes["token.type"] == "input"
    assert usage == 1500


def test_protobuf_and_gzip(client: TestClient, otel_token: str, owner_db: Engine) -> None:
    dp = NumberDataPoint(
        as_double=2.5,
        time_unix_nano=time.time_ns(),
        attributes=[KeyValue(key="session.id", value=AnyValue(string_value="sess-pb-1"))],
    )
    req = ExportMetricsServiceRequest(
        resource_metrics=[
            ResourceMetrics(
                scope_metrics=[
                    ScopeMetrics(
                        metrics=[Metric(name="test.cost.usage", sum=Sum(data_points=[dp]))]
                    )
                ]
            )
        ]
    )
    raw = gzip.compress(req.SerializeToString())
    r = client.post(
        "/otel/v1/metrics",
        content=raw,
        headers={
            **bearer(otel_token),
            "Content-Encoding": "gzip",
            "Content-Type": "application/x-protobuf",
        },
    )
    assert r.status_code == 200 and r.headers["content-type"] == "application/x-protobuf"
    with owner_db.connect() as c:
        assert (
            c.execute(
                text("SELECT value FROM otel_events WHERE session_id = 'sess-pb-1'")
            ).scalar_one()
            == 2.5
        )


def test_logs_and_errors(
    client: TestClient,
    otel_token: str,
    token: TokenFactory,
    people: dict[str, Person],
    owner_db: Engine,
) -> None:
    body = {
        "resourceLogs": [
            {
                "scopeLogs": [
                    {
                        "logRecords": [
                            {
                                "timeUnixNano": str(time.time_ns()),
                                "body": {"stringValue": "user prompt text"},
                                "attributes": [
                                    _attr("event.name", "test.tool_decision"),
                                    _attr("session.id", "sess-log-1"),
                                    _attr("tool_name", "Write"),
                                    _attr("decision", "accept"),
                                    _attr("tool_input", "rm -rf"),
                                ],
                            },
                            {
                                "timeUnixNano": str(time.time_ns()),
                                "attributes": [_attr("event.name", "user_prompt")],
                            },
                        ]
                    }
                ]
            }
        ]
    }
    assert client.post("/otel/v1/logs", json=body, headers=bearer(otel_token)).status_code == 200
    with owner_db.connect() as c:
        attrs = c.execute(
            text("SELECT attributes FROM otel_events WHERE session_id = 'sess-log-1'")
        ).scalar_one()
    assert attrs == {"session.id": "sess-log-1", "tool_name": "Write", "decision": "accept"}
    r = client.post(
        "/otel/v1/metrics",
        content=b"\x00garbage",
        headers={**bearer(otel_token), "Content-Type": "application/x-protobuf"},
    )
    assert r.status_code == 400
    r = client.post(
        "/otel/v1/metrics",
        content=json.dumps({}).encode(),
        headers={"Authorization": "Bearer tsi_otel_wrong", "Content-Type": "application/json"},
    )
    assert r.status_code == 401
    eng = token(people["eng"].oid, people["eng"].roles)
    assert client.post("/otel/v1/metrics", json={}, headers=bearer(eng)).status_code == 401
    assert client.post("/otel/v1/traces", json={}, headers=bearer(otel_token)).status_code == 404
