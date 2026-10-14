"""Checks for ops/monitoring (OPS-02 §11-§12). Run with the insights venv: ``pytest ops/monitoring/tests``.

promtool checks run when ``PROMTOOL`` or ``promtool`` on PATH is available.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

MON = Path(__file__).resolve().parent.parent
ROOT = MON.parent.parent
METRICS_PY = ROOT / "services" / "insights" / "app" / "obs" / "metrics.py"
REGISTRY = ROOT / "docs" / "architecture" / "registry.md"
# Metrics that come from outside the insights service (OPS-02 §2, §5.2 last rows, OPS-01).
EXTERNAL = {
    "up",
    "probe_success",
    "probe_http_status_code",
    "ALERTS",
    "insights_tls_cert_expiry_seconds",
}
EXTERNAL_PREFIXES = ("node_filesystem_", "pgbackrest_")
DSH_TITLES = {
    "DSH-1": "Service overview",
    "DSH-2": "Ingest pipeline",
    "DSH-3": "Read API and portal",
    "DSH-4": "Database",
    "DSH-5": "Fleet and outbox",
    "DSH-6": "Security signals",
}


def _alerts() -> list[dict[str, Any]]:
    doc = yaml.safe_load((MON / "alerts.yaml").read_text(encoding="utf-8"))
    return [r for g in doc["groups"] for r in g["rules"]]


def _recorded() -> set[str]:
    doc = yaml.safe_load((MON / "recording.yaml").read_text(encoding="utf-8"))
    return {r["record"] for g in doc["groups"] for r in g["rules"]}


def _exported() -> set[str]:
    return set(re.findall(r'"(insights_[a-z_]+)"', METRICS_PY.read_text(encoding="utf-8")))


def _metric_names(expr: str) -> set[str]:
    expr = re.sub(r"\{[^}]*\}|\[[^\]]*\]", "", expr)
    expr = re.sub(r'"[^"]*"', "", expr)
    words = set(re.findall(r"[a-zA-Z_:][a-zA-Z0-9_:]*", expr))
    return {
        w
        for w in words
        if w.startswith(("insights_", "node_", "probe_", "pgbackrest_"))
        or w in {"up", "ALERTS"}
        or ":" in w
    }


def test_alert_ids_match_registry() -> None:
    reg = REGISTRY.read_text(encoding="utf-8")
    m = re.search(r"`AL-01`–`AL-(\d+)`", reg)
    assert m, "registry lists the AL-nn series"
    expected = {f"AL-{i:02d}" for i in range(1, int(m.group(1)) + 1)}
    ids = [r["labels"]["alert_id"] for r in _alerts()]
    assert set(ids) == expected
    for r in _alerts():
        assert r["alert"].startswith(r["labels"]["alert_id"] + "_"), r["alert"]
    # AL-26 has a fast (P1) and a slow (P2) rule; every other id exactly one rule
    assert sorted(i for i in ids if ids.count(i) > 1) == ["AL-26", "AL-26"]


def test_every_alert_has_severity_dashboard_and_runbook() -> None:
    dashboards = {p.stem for p in (MON / "dashboards").glob("DSH-*.json")}
    for r in _alerts():
        assert r["labels"]["severity"] in {"P1", "P2", "P3"}, r["alert"]
        dsh = r["annotations"]["dashboard"].split()[0]
        assert dsh in dashboards, r["alert"]
        anchor = r["labels"]["alert_id"].lower()
        assert r["annotations"]["runbook"].endswith(f"#{anchor}"), r["alert"]


def test_runbook_anchors_exist_in_ops_04() -> None:
    """Every alert's runbook link resolves to an anchor in OPS-04 §4.13 (OPS-02 §13)."""
    runbook = ROOT / "docs" / "operations" / "OPS-04-failure-runbook.md"
    anchors = set(re.findall(r'<a id="([a-z0-9-]+)"></a>', runbook.read_text(encoding="utf-8")))
    for r in _alerts():
        path, _, anchor = r["annotations"]["runbook"].partition("#")
        assert (ROOT / path).resolve() == runbook.resolve(), r["alert"]
        assert anchor in anchors, r["alert"]
    assert {f"al-{n:02d}" for n in range(1, 27)} <= anchors


def test_alert_text_has_no_identifiers() -> None:
    for r in _alerts():
        text = json.dumps(r["annotations"])
        for label in ("run_id", "system", "pseudonym", "repo", "user", "device"):
            assert f"$labels.{label}" not in text, (r["alert"], label)


def test_rules_reference_only_known_metrics() -> None:
    known = _exported() | _recorded() | EXTERNAL
    exprs = [r["expr"] for r in _alerts()]
    rec = yaml.safe_load((MON / "recording.yaml").read_text(encoding="utf-8"))
    exprs += [r["expr"] for g in rec["groups"] for r in g["rules"]]
    for d in (MON / "dashboards").glob("DSH-*.json"):
        exprs += [
            t["expr"] for p in json.loads(d.read_text())["panels"] for t in p.get("targets", [])
        ]
    for e in exprs:
        for name in _metric_names(e):
            base = re.sub(r"_(bucket|count|sum)$", "", name)
            assert name in known or base in known or name.startswith(EXTERNAL_PREFIXES), (
                f"unknown metric {name} in {e!r}"
            )


def test_dashboards_dsh_1_to_6() -> None:
    files = sorted(p.stem for p in (MON / "dashboards").glob("*.json"))
    assert files == sorted(DSH_TITLES)
    for did, title in DSH_TITLES.items():
        d = json.loads((MON / "dashboards" / f"{did}.json").read_text(encoding="utf-8"))
        assert d["title"] == f"{did} {title}" and d["uid"] == did.lower()
        assert d["panels"], did
        ids = [p["id"] for p in d["panels"]]
        assert len(ids) == len(set(ids)), did


def _promtool() -> str:
    tool = os.environ.get("PROMTOOL") or shutil.which("promtool")
    if not tool:
        pytest.skip("promtool not available")
    return tool


def test_promtool_check_rules() -> None:
    r = subprocess.run(
        [_promtool(), "check", "rules", "recording.yaml", "alerts.yaml"],
        cwd=MON,
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stdout + r.stderr


@pytest.mark.skipif(not os.environ.get("PROMTOOL_UNIT"), reason="set PROMTOOL_UNIT=1 (about 2 min)")
def test_promtool_unit_tests() -> None:
    r = subprocess.run(
        [_promtool(), "test", "rules", "alerts.test.yaml"],
        cwd=MON,
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stdout + r.stderr
