#!/usr/bin/env python3
"""Fail when code uses an error code or spike id that the registry does not list.

Registry REG-01 §12: "A CI check fails a pull request that adds an `E-*` code, a `/v1/` path, an
event type or an `S-nn` spike id not listed here." Paths and event types are checked by the
component suites (insights `test_openapi_covers_registry_and_is_committed`, schemas
`test_every_registry_schema_exists`); this script covers error codes and spike ids across the
whole tree. Gate codes `E-H<n>-nn` are catalogued in SDD-03 §14.1, which the registry points to.

Usage: python3 scripts/check_registry.py   (from anywhere; exit 0 clean, 1 with findings)
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "docs" / "architecture" / "registry.md"
SDD03 = ROOT / "docs" / "design" / "SDD-03-harness.md"
CODE = re.compile(r"\bE-[A-Z0-9]+-\d{2}\b")
SPIKE = re.compile(r"\bS-\d{2}\b")
RANGE = re.compile(r"\bS-(\d{2})`?\s*[–-]+\s*`?S-(\d{2})\b")
SKIP_SUFFIXES = (".pdf", ".pptx", ".png", ".jpg", ".svg", ".lock", ".woff", ".woff2", ".ico")
# Docs are checked by review (they define the names); tests may use invented codes on purpose
SKIP_PARTS = {"docs", "tests", "test", "__tests__", "node_modules", "e2e"}


def known() -> tuple[set[str], set[str]]:
    reg = REGISTRY.read_text(encoding="utf-8")
    codes = set(CODE.findall(reg)) | set(CODE.findall(SDD03.read_text(encoding="utf-8")))
    spikes = set(SPIKE.findall(reg))
    for a, b in RANGE.findall(reg):
        spikes |= {f"S-{i:02d}" for i in range(int(a), int(b) + 1)}
    return codes, spikes


def tracked() -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return [ROOT / f for f in out.splitlines() if f]


def main() -> int:
    codes, spikes = known()
    findings: list[str] = []
    for path in tracked():
        rel = path.relative_to(ROOT)
        if rel.suffix in SKIP_SUFFIXES or SKIP_PARTS.intersection(rel.parts[:-1]):
            continue
        if rel.name == "package-lock.json" or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for c in sorted(set(CODE.findall(text)) - codes):
            findings.append(f"{rel}: error code {c} is not in registry §2 or SDD-03 §14.1")
        for s in sorted(set(SPIKE.findall(text)) - spikes):
            findings.append(f"{rel}: spike id {s} is not in registry §9")
    for f in findings:
        print(f)
    print(f"registry check: {len(codes)} codes, {len(spikes)} spikes known; {len(findings)} finding(s)")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
