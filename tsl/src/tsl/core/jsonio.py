"""JSON and YAML file helpers: sorted keys, 2-space indent, atomic writes (Doc 5 §1.1)."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

import yaml


class DuplicateKeyError(ValueError):
    pass


def _no_dupes(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in pairs:
        if k in out:
            raise DuplicateKeyError(f"duplicate key {k!r}")
        out[k] = v
    return out


def loads_strict(text: str) -> Any:
    """Parse JSON refusing duplicate keys and NaN/Infinity (SDD-07 §6.2)."""

    def _bad_const(name: str) -> Any:
        raise ValueError(f"non-finite number {name}")

    return json.loads(text, object_pairs_hook=_no_dupes, parse_constant=_bad_const)


def read_json(path: Path) -> Any:
    return loads_strict(path.read_text(encoding="utf-8"))


def dumps(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def atomic_write(path: Path, text: str) -> None:
    """Temp file, fsync, rename (SDD-02 §11.2)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def write_json(path: Path, obj: Any) -> None:
    atomic_write(path, dumps(obj))


class _SafeLoader(yaml.SafeLoader):
    pass


def _construct_mapping(loader: yaml.SafeLoader, node: yaml.MappingNode) -> dict[Any, Any]:
    loader.flatten_mapping(node)
    out: dict[Any, Any] = {}
    for k_node, v_node in node.value:
        key = loader.construct_object(k_node, deep=True)
        if key in out:
            raise yaml.constructor.ConstructorError(
                None, None, f"duplicate key {key!r}", k_node.start_mark
            )
        out[key] = loader.construct_object(v_node, deep=True)
    return out


_SafeLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_mapping)
# Timestamps stay strings: schemas validate them as date-time strings.
_SafeLoader.yaml_implicit_resolvers = {
    k: [(tag, rx) for tag, rx in v if tag != "tag:yaml.org,2002:timestamp"]
    for k, v in yaml.SafeLoader.yaml_implicit_resolvers.items()
}

MAX_YAML_BYTES = 1_048_576


def load_yaml(text: str) -> Any:
    if len(text.encode("utf-8")) > MAX_YAML_BYTES:
        raise ValueError("YAML document larger than 1 MB")
    return yaml.load(text, Loader=_SafeLoader)  # noqa: S506 - custom subclass of SafeLoader


def read_yaml(path: Path) -> Any:
    return load_yaml(path.read_text(encoding="utf-8"))


def dump_yaml(obj: Any) -> str:
    return yaml.safe_dump(obj, sort_keys=False, allow_unicode=True, default_flow_style=False)


def read_any(path: Path) -> Any:
    if path.suffix in (".yaml", ".yml"):
        return read_yaml(path)
    return read_json(path)
