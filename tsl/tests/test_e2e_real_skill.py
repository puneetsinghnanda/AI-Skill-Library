"""E2E with the real requirement-review skill from plugins/truminds as the fixture:
simulated run on a temp companion repo (invented order-tracking data), then decide."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from e2e_steps import do_req_step, start_run
from helpers import World
from tsl.identity.signing import b64url_decode, signature_ok
from tsl.schemas.registry import errors

ROOT = Path(__file__).resolve().parents[2]
REAL = ROOT / "plugins" / "truminds" / "skills" / "requirement-review"


@pytest.fixture
def real(world: World) -> World:
    dst = world.plugin / "skills" / "requirement-review"
    shutil.rmtree(dst)
    shutil.copytree(REAL, dst)
    return world


def test_real_skill_run_then_decide(real: World) -> None:
    run_id = start_run(real)
    res = do_req_step(real, run_id)
    env = res["env"]
    assert res["code"] == 0 and env["code"] == "OK", env
    d = env["data"]
    assert (d["outcome"], d["band"], d["action"]) == ("PASS", "High", "continue")
    art = real.companion / res["artifact"]
    checks = json.loads(art.with_name(art.stem + ".checks.json").read_text())
    review = json.loads(art.with_name(art.stem + ".review.json").read_text())
    rec = json.loads((real.companion / d["verification_path"]).read_text())
    assert errors("checks.v1", checks) == [] and errors("review.v1", review) == []
    assert errors("verification.v1", rec) == []
    assert rec["skill"].startswith("requirement-review@")
    facts = real.insights.facts(rec["key_id"])
    assert facts and signature_ok(rec, b64url_decode(facts["public_key"]))
    decided = [e for e in real.rt().outbox().events() if e["type"] == "step.decided"]
    assert decided and decided[-1]["body"]["outcome"] == "PASS"


def test_real_skill_dropped_finding_lowers_s1(real: World) -> None:
    run_id = start_run(real)
    fabricated = {
        "id": "F-1",
        "severity": "minor",
        "category": "completeness",
        "text": "History endpoint reads the archive table",
        "cites": [
            {
                "ref": "sample-orders:api/src/routes/history.js#L10",
                "quote": "SELECT * FROM order_archive",
            }
        ],
    }
    res = do_req_step(real, run_id, findings=[fabricated])
    d = res["env"]["data"]
    assert d["findings_dropped"] == ["F-1"]
    assert d["signals"]["S1"] < 1.0
    rec = json.loads((real.companion / d["verification_path"]).read_text())
    assert rec["findings_dropped"][0]["id"] == "F-1"
