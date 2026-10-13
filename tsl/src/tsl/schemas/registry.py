"""Schema registry: name -> current version, cached validators (SDD-04 §10).

Schemas are loaded through index.json. In a wheel they sit in
tsl/schemas/bundled/ (copied at build time by hatch_build.py). In a source
checkout tsl falls back to the repository's schemas/ folder. There is no third
location and no environment override.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import cache, lru_cache
from pathlib import Path
from typing import Any

from tsl.core.errors import TslError

SCHEMA_REF = re.compile(r"^(?P<name>[a-z][a-z0-9.-]*?)\.v(?P<version>[0-9]+)$")


def schemas_root() -> Path:
    here = Path(__file__).resolve().parent
    bundled = here / "bundled"
    if (bundled / "index.json").is_file():
        return bundled
    for parent in here.parents:
        cand = parent / "schemas" / "index.json"
        if cand.is_file():
            return cand.parent
    raise RuntimeError("JSON Schemas not found (neither bundled nor in the source tree)")


@dataclass(frozen=True)
class Entry:
    id: str
    name: str
    version: int
    file: str
    kind: str
    event_type: str | None


@lru_cache(maxsize=1)
def index() -> dict[str, Entry]:
    root = schemas_root()
    data = json.loads((root / "index.json").read_text(encoding="utf-8"))
    out: dict[str, Entry] = {}
    for e in data["schemas"]:
        out[e["id"]] = Entry(
            e["id"], e["name"], int(e["version"]), e["file"], e["kind"], e.get("event_type")
        )
    return out


@lru_cache(maxsize=1)
def current_versions() -> dict[str, int]:
    cur: dict[str, int] = {}
    for e in index().values():
        if e.kind == "event":
            continue
        cur[e.name] = max(cur.get(e.name, 0), e.version)
    return cur


def split_ref(schema_id: str) -> tuple[str, int] | None:
    m = SCHEMA_REF.match(schema_id)
    if not m:
        return None
    return m.group("name"), int(m.group("version"))


@cache
def load(schema_id: str) -> dict[str, Any]:
    e = index().get(schema_id)
    if e is None:
        raise KeyError(schema_id)
    data: dict[str, Any] = json.loads((schemas_root() / e.file).read_text(encoding="utf-8"))
    return data


def event_schema_id(event_type: str, version: int) -> str:
    return f"{event_type}.v{version}"


@cache
def _validator(schema_id: str) -> Any:
    from jsonschema import Draft202012Validator

    return Draft202012Validator(load(schema_id), format_checker=Draft202012Validator.FORMAT_CHECKER)


@dataclass(frozen=True)
class SchemaError:
    pointer: str
    message: str
    keyword: str


def _ptr(path: Any) -> str:
    return "".join("/" + str(p).replace("~", "~0").replace("/", "~1") for p in path)


def errors(schema_id: str, obj: Any) -> list[SchemaError]:
    v = _validator(schema_id)
    out = [
        SchemaError(_ptr(e.absolute_path), e.message[:300], str(e.validator))
        for e in v.iter_errors(obj)
    ]
    return sorted(out, key=lambda e: (e.pointer, e.keyword))


def is_valid(schema_id: str, obj: Any) -> bool:
    return not errors(schema_id, obj)


def require_valid(schema_id: str, obj: Any, file: str) -> None:
    errs = errors(schema_id, obj)
    if errs:
        e = errs[0]
        raise TslError("E-CFG-01", file=file, pointer=e.pointer or "/", reason=e.message)


def readable(schema_id: str, path: str = "") -> str:
    """Return the schema id to validate against, applying the N/N-1 rule (R-09).

    Raises E-SCH-01 for a known name at a version older than N-1 or newer than N.
    Returns '' for an unknown schema name.
    """
    ref = split_ref(schema_id)
    if ref is None:
        return ""
    name, ver = ref
    cur = current_versions().get(name)
    if cur is None:
        return ""
    if ver == cur:
        return schema_id
    if ver == cur - 1 and f"{name}.v{ver}" in index():
        return f"{name}.v{ver}"  # N-1: compat upgrade happens in memory (none defined yet)
    raise TslError("E-SCH-01", path=path or schema_id, version=schema_id)


def body_hints(schema_id: str) -> dict[str, Any]:
    s = load(schema_id)
    return {k: v for k, v in s.items() if k.startswith("x-")}
