"""DS-C01 contract-stated (contract.stated): new and changed endpoints state their fields."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tsl.core.jsonio import read_yaml
from tsl.harness.skillchecks import CheckEnv, run_declared, validate_declared
from tsl.schemas.registry import errors as schema_errors

ROOT = Path(__file__).resolve().parents[2]
CHECKS = ROOT / "plugins" / "truminds" / "skills" / "design" / "checks.yaml"
CHECK_ID = "DS-C01"  # contract-stated


def _outcome(front: dict[str, Any]) -> Any:
    doc = dict(read_yaml(CHECKS))
    doc["checks"] = [c for c in doc["checks"] if c["id"] == CHECK_ID]
    assert doc["checks"], f"{CHECK_ID} not declared"
    [out] = run_declared(CheckEnv(front, "", ROOT, [], {}, {}), doc)
    return out


def _front(*endpoints: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "design.v1",
        "components": [{"name": "List", "module": "module:r:api/src", "change": "changed"}],
        "endpoints": list(endpoints),
    }


FIELD = {
    "name": "last_visit",
    "type": "string",
    "nullable": True,
    "format": "YYYY-MM-DD in HOSPITAL_TZ",
    "example": "2026-10-31",
    "status": "known",
}


def test_checks_yaml_declares_contract_stated_validly() -> None:
    assert validate_declared(dict(read_yaml(CHECKS))) == []


def test_passes_when_a_changed_endpoint_states_its_fields() -> None:
    front = _front(
        {"method": "GET", "path": "/api/patients", "change": "changed", "fields": [FIELD]}
    )
    out = _outcome(front)
    assert (out.gate, out.status) == ("H4", "pass"), out.detail


def test_fails_when_a_changed_endpoint_has_no_fields() -> None:
    out = _outcome(_front({"method": "GET", "path": "/api/patients", "change": "changed"}))
    assert (out.gate, out.status) == ("H4", "fail")
    assert "GET /api/patients is changed but states no fields" in out.detail


def test_fails_when_a_new_endpoint_has_an_empty_fields_list() -> None:
    out = _outcome(_front({"method": "POST", "path": "/api/visits", "change": "new", "fields": []}))
    assert out.status == "fail"
    assert "POST /api/visits is new" in out.detail


def test_passes_for_existing_and_removed_endpoints_without_fields() -> None:
    front = _front(
        {"method": "GET", "path": "/api/patients/:id", "change": "existing"},
        {"method": "DELETE", "path": "/api/patients/:id", "change": "removed"},
    )
    assert _outcome(front).status == "pass"


def test_passes_when_there_are_no_endpoints() -> None:
    front = _front()
    del front["endpoints"]
    assert _outcome(front).status == "pass"


def test_fields_are_optional_in_design_v1() -> None:
    # Backward compatible: an artifact without fields stays schema-valid; the check, not the
    # schema, asks for them.
    base = {
        "schema": "design.v1",
        "run_id": "run_01JA0B3C4D5E6F7G8H9JKMNPQR",
        "step": "design",
        "attempt": 1,
        "skill": "design@1.5.0",
        "inputs": [],
        "pack_sha": {},
    }
    old = {**base, **_front({"method": "GET", "path": "/api/patients", "change": "changed"})}
    new = {
        **base,
        **_front(
            {"method": "GET", "path": "/api/patients", "change": "changed", "fields": [FIELD]}
        ),
    }
    assert schema_errors("design.v1", old) == []
    assert schema_errors("design.v1", new) == []
