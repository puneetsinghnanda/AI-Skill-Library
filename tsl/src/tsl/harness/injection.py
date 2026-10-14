"""SC-INJ-01 prompt-injection soft check (SEC-01 §6.2 layer L1, §6.5; SDD-03 §9 S2).

`tsl verify` scans the artifact and every declared input it can read for instruction-like
phrases from `plugins/truminds/policy/injection-markers.yaml` (schema `injection-markers.v1`).
The result is one soft entry `{"id": "SC-INJ-01", "pass": ...}` in `checks.json`, so a match
lowers S2 and is listed in the PR body. It never blocks a run on its own: it is a signal,
not a control (SEC-01 §6.5).

Matching is case-insensitive over the whole text. SEC-01 §6.5 makes no exception for fenced
code blocks or inline code, so text inside them is scanned like any other text: a planted
instruction in a code comment is one of the sources SEC-01 §6.1 names.

A hit records the source, line and pattern index only, never the matched text (as H4, TM-09).
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tsl.core.jsonio import read_yaml

CHECK_ID = "SC-INJ-01"
MARKERS_REL = Path("policy") / "injection-markers.yaml"

Markers = tuple[re.Pattern[str], ...]


@dataclass(frozen=True)
class InjectionHit:
    source: str  # companion-relative path of the artifact or input
    line: int
    pattern: int  # index into the patterns list

    def record(self) -> dict[str, Any]:
        return {"source": self.source, "line": self.line, "pattern": self.pattern}


def compile_markers(data: dict[str, Any], label: str = "injection-markers.yaml") -> Markers:
    """Validate an `injection-markers.v1` document and compile its patterns (case-insensitive)."""
    from tsl.schemas.registry import require_valid

    require_valid("injection-markers.v1", data, label)
    return tuple(re.compile(str(p), re.IGNORECASE) for p in data["patterns"])


def load_markers(path: Path) -> Markers:
    return compile_markers(dict(read_yaml(path)), path.name)


def markers_for(plugin_root: Path) -> Markers | None:
    """The plugin's marker list, or None when the plugin ships no file (check is then skipped)."""
    p = plugin_root / MARKERS_REL
    return load_markers(p) if p.is_file() else None


def scan(source: str, text: str, markers: Markers) -> list[InjectionHit]:
    hits: list[InjectionHit] = []
    seen: set[tuple[int, int]] = set()
    for i, rx in enumerate(markers):
        for m in rx.finditer(text):
            line = text.count("\n", 0, m.start()) + 1
            if (line, i) not in seen:
                seen.add((line, i))
                hits.append(InjectionHit(source, line, i))
    return sorted(hits, key=lambda h: (h.line, h.pattern))


def check(
    sources: Iterable[tuple[str, str]], markers: Markers
) -> tuple[dict[str, Any], list[InjectionHit]]:
    """Run SC-INJ-01 over (source, text) pairs. Returns the soft entry and the hits."""
    hits: list[InjectionHit] = []
    for source, text in sources:
        hits.extend(scan(source, text, markers))
    return {"id": CHECK_ID, "pass": not hits}, hits
