"""answers.logged as design 1.6.0 uses it (DS-C02): answers decide components (CO-n),
endpoints (EP-n) or claims through `decides`. Components and endpoints without an id, as in
design.v1 artifacts written before 1.6.0, are skipped rather than raising."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tsl.approvals import ide_answers
from tsl.core.jsonio import read_yaml
from tsl.harness.skillchecks import CheckEnv, run_declared

ROOT = Path(__file__).resolve().parents[2]
CHECKS = ROOT / "plugins" / "truminds" / "skills" / "design" / "checks.yaml"
RUN = "run_01JA0B3C4D5E6F7G8H9JKMNPQR"
LOG = f"runs/{RUN}/ide-answers.md"
STORIES = f"artifacts/T-1/{RUN}/stories.md"
API = "context/generated/api-inventory.json#http:GET:/api/orders"
MOD = "context/generated/module-map.json#module:orders-api:src/orders"

Q01 = "Q-01: Which field name and format should GET /api/orders return?"
C1 = "C1: I assumed the order row type is declared in api/src/types.ts. Is that right?"


def _log(root: Path, entries: list[dict[str, Any]], attempt: int = 1) -> None:
    ide_answers.append(
        root / LOG, RUN, "design", attempt, "t", "Jane <jane@example.com>", "toolu_1", entries
    )


def _world(tmp_path: Path, *, assumption: bool = False) -> Path:
    (tmp_path / STORIES).parent.mkdir(parents=True)
    (tmp_path / STORIES).write_text("---\nschema: stories.v1\n---\n", encoding="utf-8")
    entries = [
        {"question": Q01, "options": ["last_shipped_on, YYYY-MM-DD"], "answer": "As proposed"}
    ]
    if assumption:
        entries.append(
            {"question": C1, "options": ["Yes, confirm"], "answer": "No, api/src/orders/types.ts"}
        )
    _log(tmp_path, entries)
    return tmp_path


def _front(**over: Any) -> dict[str, Any]:
    f: dict[str, Any] = {
        "schema": "design.v1",
        "run_id": RUN,
        "step": "design",
        "attempt": 1,
        "claims": [],
        "questions": [],
        "components": [
            {
                "id": "CO-1",
                "name": "Order list",
                "module": "module:orders-api:src/orders",
                "change": "changed",
                "cites": [MOD],
            }
        ],
        "endpoints": [
            {
                "id": "EP-1",
                "method": "GET",
                "path": "/api/orders",
                "change": "changed",
                "cites": [API, f"{LOG}#a-01"],
            }
        ],
        "answers": [
            {
                "id": "A-01",
                "kind": "question",
                "about": "Q-01",
                "answer": "As proposed",
                "decides": ["EP-1"],
            }
        ],
    }
    f.update(over)
    return f


def _run(root: Path, front: dict[str, Any]) -> tuple[str, str]:
    doc = dict(read_yaml(CHECKS))
    doc["checks"] = [c for c in doc["checks"] if c["id"] == "DS-C02"]
    assert doc["checks"], "DS-C02 not declared"
    env = CheckEnv(front, "", root, [STORIES], {}, {"stories": STORIES})
    [out] = run_declared(env, doc)
    assert out.gate == "H4"
    return out.status, out.detail


def test_endpoint_decided_by_a_recorded_answer_passes(tmp_path: Path) -> None:
    assert _run(_world(tmp_path), _front()) == ("pass", "")


def test_endpoint_that_does_not_cite_its_answer_fails(tmp_path: Path) -> None:
    f = _front()
    f["endpoints"][0]["cites"] = [API]
    status, detail = _run(_world(tmp_path), f)
    assert status == "fail"
    assert f"EP-1 does not cite {LOG}#a-01" in detail


def test_answer_naming_an_unknown_item_fails(tmp_path: Path) -> None:
    f = _front()
    f["answers"][0]["decides"] = ["EP-9"]
    status, detail = _run(_world(tmp_path), f)
    assert status == "fail"
    assert "names EP-9, which is not an item" in detail


def test_logged_answer_left_out_of_answers_fails(tmp_path: Path) -> None:
    f = _front(answers=[])
    f["endpoints"][0]["cites"] = [API]
    status, detail = _run(_world(tmp_path), f)
    assert status == "fail"
    assert "A-01 was answered by the user but is not in answers" in detail


def test_corrected_type_location_assumption_decides_its_claim(tmp_path: Path) -> None:
    claim = {
        "id": "C1",
        "text": "The order row type is declared in `api/src/orders/types.ts`",
        "cites": [MOD, f"{LOG}#a-02"],
    }
    answer = {
        "id": "A-02",
        "kind": "assumption",
        "about": "C1",
        "answer": "No, api/src/orders/types.ts",
        "decides": ["C1"],
        "mismatch": {"text": "Draft said api/src/types.ts", "cites": [MOD]},
    }
    f = _front(claims=[claim])
    f["answers"].append(answer)
    assert _run(_world(tmp_path, assumption=True), f) == ("pass", "")


def test_design_without_ids_or_answers_passes(tmp_path: Path) -> None:
    # A 1.5.0-shaped artifact: no ids, no cites, no answers, no IDE log.
    f = _front(answers=[])
    f["components"] = [
        {"name": "Order list", "module": "module:orders-api:src/orders", "change": "changed"}
    ]
    f["endpoints"] = [{"method": "GET", "path": "/api/orders", "change": "existing"}]
    assert _run(tmp_path, f) == ("pass", "")
