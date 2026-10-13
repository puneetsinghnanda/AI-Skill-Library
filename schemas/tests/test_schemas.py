"""Contract tests for schemas/ (TST-01 §2.2; TC-SCH-001, TC-SCH-002, TC-SCH-003).

- every schema is a valid draft 2020-12 schema with $id, title and description;
- every valid fixture passes; every invalid fixture fails at the pointer and keyword in its .expect.json sidecar;
- every schema listed in the registry (docs/architecture/registry.md §5 and §6) exists as a file;
- index.json lists exactly the schema files on disk.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import yaml
from jsonschema import Draft202012Validator, ValidationError

SCHEMAS = Path(__file__).resolve().parent.parent
ROOT = SCHEMAS.parent
REGISTRY = ROOT / "docs" / "architecture" / "registry.md"
ID_BASE = "https://schemas.truminds.internal/"
FORMAT_CHECKER = Draft202012Validator.FORMAT_CHECKER


def load(path: Path) -> Any:
    text = path.read_text(encoding="utf-8")
    if path.suffix in (".yaml", ".yml"):
        return yaml.safe_load(text)
    return json.loads(text)


def schema_files() -> list[Path]:
    return sorted([*SCHEMAS.glob("*.json"), *(SCHEMAS / "events").glob("*.json")])


SCHEMA_FILES = [p for p in schema_files() if p.name != "index.json"]
INDEX = load(SCHEMAS / "index.json")


def fixture_dir(rel: str) -> Path:
    return SCHEMAS / "fixtures" / rel.removesuffix(".json")


def fixtures(kind: str) -> Iterator[tuple[str, Path]]:
    for entry in INDEX["schemas"]:
        folder = fixture_dir(entry["file"]) / kind
        for f in sorted(folder.glob("*")):
            if f.name.endswith(".expect.json"):
                continue
            yield entry["file"], f


def validator(rel: str) -> Draft202012Validator:
    return Draft202012Validator(load(SCHEMAS / rel), format_checker=FORMAT_CHECKER)


def all_errors(errors: list[ValidationError]) -> Iterator[ValidationError]:
    for e in errors:
        yield e
        yield from all_errors(list(e.context or []))


def pointer(e: ValidationError) -> str:
    return "".join("/" + str(p).replace("~", "~0").replace("/", "~1") for p in e.absolute_path)


# ------------------------------------------------------------------ schemas themselves
@pytest.mark.parametrize("path", SCHEMA_FILES, ids=lambda p: str(p.relative_to(SCHEMAS)))
def test_schema_is_valid_2020_12(path: Path) -> None:
    schema = load(path)
    Draft202012Validator.check_schema(schema)
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["$id"] == ID_BASE + str(path.relative_to(SCHEMAS)).replace("\\", "/")
    assert schema.get("title") and schema.get("description")
    assert schema.get("x-owner"), "owner doc missing"


def test_index_matches_files() -> None:
    on_disk = {str(p.relative_to(SCHEMAS)).replace("\\", "/") for p in SCHEMA_FILES}
    listed = [e["file"] for e in INDEX["schemas"]]
    assert len(listed) == len(set(listed)), "duplicate index entries"
    assert set(listed) == on_disk
    for e in INDEX["schemas"]:
        schema = load(SCHEMAS / e["file"])
        assert e["$id"] == schema["$id"]
        assert e["id"] == f"{e['name']}.v{e['version']}"
        assert e["owner"] == schema["x-owner"]


def registry_schema_files() -> set[str]:
    text = REGISTRY.read_text(encoding="utf-8")
    sec6 = text.split("## 6. JSON schema IDs", 1)[1].split("## 7.", 1)[0]
    files = set(re.findall(r"`schemas/([a-z0-9.-]+\.v\d+\.json)`", sec6))
    m = re.search(r"Artifact body schemas: (.+?)\|", sec6)
    assert m, "artifact body row not found in registry §6"
    files |= {f"{n}.json" for n in re.findall(r"`([a-z0-9-]+\.v\d+)`", m.group(1))}
    sec5 = text.split("## 5. Event types", 1)[1].split("## 6.", 1)[0]
    types = re.findall(r"^\| `([a-z]+\.[a-z_]+)` \|", sec5, flags=re.M)
    assert len(types) >= 21
    files |= {f"events/{t}.v1.json" for t in types}
    return files


def test_every_registry_schema_exists() -> None:
    expected = registry_schema_files()
    missing = sorted(f for f in expected if not (SCHEMAS / f).is_file())
    assert not missing, f"registry schemas without a file: {missing}"


def test_every_schema_file_is_in_registry() -> None:
    text = REGISTRY.read_text(encoding="utf-8")
    for p in SCHEMA_FILES:
        rel = str(p.relative_to(SCHEMAS)).replace("\\", "/")
        name = p.name.removesuffix(".json")
        assert rel in registry_schema_files() or f"`{name}`" in text, f"{rel} is not listed in the registry"


@pytest.mark.parametrize("entry", INDEX["schemas"], ids=lambda e: e["file"])
def test_fixture_counts(entry: dict[str, Any]) -> None:
    folder = fixture_dir(entry["file"])
    valid = [f for f in (folder / "valid").glob("*")]
    invalid = [f for f in (folder / "invalid").glob("*") if not f.name.endswith(".expect.json")]
    assert len(valid) >= 2, "need at least 2 valid fixtures"
    assert len(invalid) >= 3, "need at least 3 invalid fixtures"
    for f in invalid:
        assert f.with_name(f.stem + ".expect.json").is_file(), f"{f.name} has no .expect.json sidecar"


# ------------------------------------------------------------------ fixtures
@pytest.mark.parametrize(("rel", "path"), list(fixtures("valid")), ids=lambda x: x if isinstance(x, str) else x.name)
def test_valid_fixture_passes(rel: str, path: Path) -> None:
    errors = sorted(validator(rel).iter_errors(load(path)), key=lambda e: list(e.absolute_path))
    assert not errors, "\n".join(f"{pointer(e)}: {e.message}" for e in errors)


@pytest.mark.parametrize(("rel", "path"), list(fixtures("invalid")), ids=lambda x: x if isinstance(x, str) else x.name)
def test_invalid_fixture_fails_for_the_stated_reason(rel: str, path: Path) -> None:
    expect = load(path.with_name(path.stem + ".expect.json"))
    errors = list(validator(rel).iter_errors(load(path)))
    assert errors, "fixture unexpectedly valid"
    found = [(pointer(e), e.validator) for e in all_errors(errors)]
    assert (expect["pointer"], expect["keyword"]) in found, f"expected {expect}, got {found}"


# ------------------------------------------------------------------ TC-SCH-003: event strings are capped
def _strings_uncapped(node: Any, path: str = "") -> Iterator[str]:
    if isinstance(node, dict):
        types = node.get("type")
        is_string = types == "string" or (isinstance(types, list) and "string" in types)
        if is_string and not any(k in node for k in ("maxLength", "enum", "const")):
            yield path
        if is_string and node.get("maxLength", 0) > 200:
            yield path + " (maxLength > 200)"
        for k, v in node.items():
            yield from _strings_uncapped(v, f"{path}/{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _strings_uncapped(v, f"{path}/{i}")


@pytest.mark.parametrize("path", sorted((SCHEMAS / "events").glob("*.json")), ids=lambda p: p.name)
def test_event_body_strings_capped_and_closed(path: Path) -> None:
    schema = load(path)
    assert schema["additionalProperties"] is False
    bad = [p for p in _strings_uncapped(schema) if "pattern" not in _node(schema, p)]
    assert not bad, f"uncapped strings: {bad}"


def _node(schema: dict[str, Any], p: str) -> dict[str, Any]:
    cur: Any = schema
    for part in [x for x in p.split(" ")[0].split("/") if x]:
        cur = cur[int(part)] if isinstance(cur, list) else cur[part]
    return cur
