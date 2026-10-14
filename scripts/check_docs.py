#!/usr/bin/env python3
"""docs-lint (GOV-01 §4.2): document control rows and required sections.

Rules:
- Every document under docs/ has a control table with `Status`, `Owner` and `Approver` rows
  (`Owner and approver` counts for both).
- Every detailed document (SDD, SEC, TST, DEV, OPS, PLN, GOV, LEG) has "Done criteria" and
  "Open items" sections. The six top-level documents (Doc 1-6) keep their own structure: their open
  questions live in PRD §8 and their done criteria in the SDDs that refine them.

Exempt, as GOV-01 §4.2 says: docs/archive/, docs/adr/, the readiness tracker; also folder READMEs,
the UX prototype and the presentations folder (generated material).

Usage: python3 scripts/check_docs.py   (exit 1 on a finding)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
EXEMPT_PARTS = {"archive", "adr", "prototype", "presentations"}
EXEMPT_FILES = {"readiness-tracker.md", "README.md"}
DETAILED = re.compile(r"^(SDD|SEC|TST|DEV|OPS|PLN|GOV|LEG)-\d+")


def row(text: str, name: str) -> bool:
    return bool(re.search(rf"^\|\s*(\*\*)?{name}(\*\*)?\s*(and approver\s*)?\|", text, re.M | re.I)) or (
        name.lower() == "approver" and bool(re.search(r"^\|\s*Owner and approver\s*\|", text, re.M | re.I))
    )


def section(text: str, title: str) -> bool:
    return bool(re.search(rf"^#+\s+(\d+(\.\d+)*\.?\s+)?{title}\b", text, re.M | re.I))


def main() -> int:
    findings: list[str] = []
    files = sorted(DOCS.rglob("*.md"))
    checked = 0
    for p in files:
        rel = p.relative_to(ROOT)
        if EXEMPT_PARTS.intersection(rel.parts) or p.name in EXEMPT_FILES:
            continue
        checked += 1
        text = p.read_text(encoding="utf-8")
        for name in ("Status", "Owner", "Approver"):
            if not row(text, name):
                findings.append(f"{rel}: control table has no `{name}` row")
        if DETAILED.match(p.name):
            for title in ("Done criteria", "Open items"):
                if not section(text, title):
                    findings.append(f"{rel}: no '{title}' section")
    for f in findings:
        print(f)
    print(f"docs-lint: {checked} documents checked, {len(findings)} finding(s)")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
