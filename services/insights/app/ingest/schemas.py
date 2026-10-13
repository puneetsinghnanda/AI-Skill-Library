"""JSON Schemas loaded through ``schemas/index.json`` (registry §6, Doc 5 R-09).

The service accepts schema version N and N-1 of each event type; any other version is E-ING-02.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.protocols import Validator


@dataclass
class SchemaSet:
    root: Path
    envelope: Validator
    events: dict[tuple[str, int], Validator] = field(default_factory=dict)
    files: dict[str, Validator] = field(default_factory=dict)
    latest: dict[str, int] = field(default_factory=dict)

    def accepted_versions(self, type_: str) -> set[int]:
        n = self.latest.get(type_)
        return {n, n - 1} & {v for (t, v) in self.events if t == type_} if n else set()

    def body_validator(self, type_: str, version: int) -> Validator | None:
        if version not in self.accepted_versions(type_):
            return None
        return self.events.get((type_, version))

    def file_validator(self, schema_id: str) -> Validator:
        return self.files[schema_id]


def _validator(path: Path) -> Validator:
    schema: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    v: Validator = Draft202012Validator(schema, format_checker=FormatChecker())
    return v


@lru_cache(maxsize=4)
def load(root: Path) -> SchemaSet:
    index = json.loads((root / "index.json").read_text(encoding="utf-8"))
    envelope: Validator | None = None
    events: dict[tuple[str, int], Validator] = {}
    files: dict[str, Validator] = {}
    latest: dict[str, int] = {}
    for item in index["schemas"]:
        kind = item.get("kind")
        path = root / item["file"]
        if kind == "event-envelope" and item["version"] == 1:
            envelope = _validator(path)
        elif kind == "event":
            t, v = str(item["event_type"]), int(item["version"])
            events[(t, v)] = _validator(path)
            latest[t] = max(latest.get(t, 0), v)
        elif kind == "file" and item["id"] in ("skill-metadata.v1", "workflow.v1", "pod.v1"):
            files[item["id"]] = _validator(path)
    if envelope is None:
        raise RuntimeError("schemas/index.json has no event-envelope.v1")
    return SchemaSet(root, envelope, events, files, latest)


def first_error(v: Validator, instance: Any) -> str | None:
    errs = sorted(v.iter_errors(instance), key=lambda e: list(e.absolute_path))
    if not errs:
        return None
    e = errs[0]
    ptr = "/" + "/".join(str(p) for p in e.absolute_path)
    return f"{ptr}: {e.message}"[:200]
