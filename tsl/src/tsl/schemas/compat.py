"""Pure upgrade functions vN-1 -> vN (SDD-04 §10).

Every schema is at v1 today, so no upgrade exists. When a schema moves to v2,
add `UPGRADES["<name>"] = fn` here; readers call `upgrade()` before validation.
Signed records are never upgraded for verification (SDD-07 §6.2).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

UPGRADES: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {}


def upgrade(name: str, obj: dict[str, Any]) -> dict[str, Any]:
    fn = UPGRADES.get(name)
    return fn(obj) if fn else obj
