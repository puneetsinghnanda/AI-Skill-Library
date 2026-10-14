"""Health, readiness, metrics, logs, OpenAPI (OPS-02 §4-§6, §12; registry §4)."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from tests.conftest import ROOT, SERVICE, Person, TokenFactory, bearer


def test_health_and_ready(client: TestClient) -> None:
    r = client.get("/v1/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"
    r = client.get("/v1/health/ready")
    assert r.status_code == 200 and r.json()["checks"] == {
        "db": "ok",
        "migration": "ok",
        "secrets": "ok",
        "jwks": "ok",
    }
    assert "X-Request-ID" in r.headers


def test_ready_fails_when_db_down(migrated: Any) -> None:
    from app.config import Settings
    from app.obs.probe import readiness

    bad = Settings(**{**migrated.model_dump(), "database_port": 1})
    ok, checks = readiness(bad, None)
    assert ok is False and checks["db"] == "fail" and checks["jwks"] == "fail"


def test_metrics_exposition_and_labels(client: TestClient) -> None:
    from prometheus_client import REGISTRY

    from app.obs import metrics
    from app.obs.metrics import metrics_app

    client.get("/v1/health")
    mc = TestClient(metrics_app())  # type: ignore[arg-type]
    body = mc.get("/metrics").text
    for name in (
        "insights_http_requests_total",
        "insights_events_received_total",
        "insights_projection_lag_seconds",
        "insights_view_refresh_age_seconds",
        "insights_webhook_signature_failures_total",
    ):
        assert name in body
    assert mc.get("/nothing").status_code == 404
    for fam in REGISTRY.collect():
        if fam.name.startswith("insights_"):
            for s in fam.samples:
                assert set(s.labels) - {"le", "quantile"} <= metrics.ALLOWED_LABELS, (
                    fam.name,
                    s.labels,
                )


def test_logs_never_hold_tokens_or_bodies(
    client: TestClient, token: TokenFactory, people: dict[str, Person], caplog: Any
) -> None:
    from app.obs.logging import JsonFormatter

    tok = token(people["eng"].oid, people["eng"].roles)
    secret_body = "PR body with <!-- tsl:run_id=run_01ABCDEFGHJKMNPQRSTVWXYZ00 --> and words"
    with caplog.at_level(logging.INFO):
        client.post("/v1/events", json={"events": [], "note": secret_body}, headers=bearer(tok))
        client.post(
            "/v1/webhooks/github",
            content=secret_body.encode(),
            headers={"X-Hub-Signature-256": "sha256=00"},
        )
    fmt = JsonFormatter("api")
    lines = [fmt.format(r) for r in caplog.records]
    text_ = "\n".join(lines)
    assert tok not in text_ and "tsl:run_id" not in text_ and "sha256=00" not in text_
    assert any('"route":"/v1/events"' in x for x in lines)
    assert all(json.loads(x)["level"] for x in lines)


def test_openapi_covers_registry_and_is_committed(app: Any) -> None:
    spec = app.openapi()
    paths = set(spec["paths"])
    reg = (ROOT / "docs" / "architecture" / "registry.md").read_text(encoding="utf-8")
    section = reg.split("## 4. HTTP endpoints", 1)[1].split("## 5.", 1)[0]
    expected = set()
    for m in re.finditer(r"^\| (GET|POST|PATCH) \| `([^`]+)`", section, re.M):
        p = m.group(2).split("?")[0]
        if p.startswith("/otel/") or p.startswith("/metrics"):
            assert p not in paths
            continue
        expected.add(re.sub(r"\{[^}]+\}", "{}", p))
    have = {re.sub(r"\{[^}]+\}", "{}", p) for p in paths}
    assert expected - have == set(), expected - have
    assert have - expected == set(), have - expected  # no unlisted routes
    committed = json.loads((SERVICE / "openapi" / "openapi.json").read_text(encoding="utf-8"))
    assert committed == json.loads(json.dumps(spec)), (
        "run: python -m app.openapi_dump > openapi/openapi.json"
    )


def test_entry_rejects_unknown_modes() -> None:
    from app.entry import main

    assert main([]) == 2
    assert main(["debug"]) == 2
    assert main(["api", "--reload"]) == 2


def test_no_secret_files_committed() -> None:
    for p in (SERVICE / ".env.example",):
        assert p.exists()
    ignored = {".venv", ".mypy_cache", ".ruff_cache", ".pytest_cache", "__pycache__"}  # never committed
    for path in Path(SERVICE).rglob("*"):
        if ignored.intersection(path.relative_to(SERVICE).parts):
            continue
        if path.is_file() and path.suffix in {".pem", ".key"}:
            raise AssertionError(path)
