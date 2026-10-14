#!/usr/bin/env python3
"""Build docs/planning/backlog.csv from the PLN-01 §7 backlog map (epics and stories).

PLN-01 stays the source. The CSV is an importable copy (Jira's CSV importer reads "Issue ID" and
"Parent ID"). Nothing here calls Jira: tickets are created only after Puneet's go-ahead (PLN-01 §1.2).

Usage: python3 scripts/build_backlog.py          write the CSV
       python3 scripts/build_backlog.py --check  exit 1 when the CSV is out of date with PLN-01
"""

from __future__ import annotations

import csv
import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLN = ROOT / "docs" / "planning" / "PLN-01-delivery-plan.md"
OUT = ROOT / "docs" / "planning" / "backlog.csv"
HEADER = [
    "Issue ID",
    "Issue Type",
    "Parent ID",
    "Summary",
    "Area",
    "Owner",
    "Depends on",
    "Phase",
    "Source",
    "Acceptance criteria",
    "Done criteria",
    "Labels",
]
DONE = "Code merged by PR; tests green; schema and docs updated; SDD done-criteria line ticked (PLN-01 §7.3)"


def rows(section: str) -> list[list[str]]:
    out = []
    for line in section.splitlines():
        if not line.startswith("| ") or line.startswith("| ---"):
            continue
        out.append([c.strip() for c in line.strip().strip("|").split("|")])
    return out[1:]  # drop the header row


def section(text: str, start: str, end: str) -> str:
    a = text.index(start)
    return text[a : text.index(end, a)]


def plain(cell: str) -> str:
    return re.sub(r"\*\*|`", "", cell).strip()


def build() -> str:
    text = PLN.read_text(encoding="utf-8")
    owners = {plain(r[0]): plain(r[2]) for r in rows(section(text, "### 1.4 Team areas", "## 2. Phases"))}

    def owner(area: str) -> str:
        codes = [a.strip() for a in plain(area).split(",")]
        names = [owners[c] for c in codes if c in owners]
        return "; ".join(names) if names else plain(area)

    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(HEADER)
    sources: dict[str, str] = {}
    for epic, title, source, area, phase in rows(section(text, "### 7.1 Epics", "### 7.2 Stories")):
        sources[epic] = plain(source)
        w.writerow([epic, "Epic", "", f"{epic} {plain(title)}", plain(area), owner(area), "", phase,
                    f"PLN-01 §7.1; {plain(source)}", f"Every story below is done; {plain(source)} done criteria met",
                    DONE, "truminds-skill-library"])
    parent = ""
    for story, what, area, deps, phase in rows(section(text, "### 7.2 Stories", "### 7.3 Story template")):
        if story.startswith("**EP-"):
            parent = plain(story)
            continue
        dep = "" if deps.strip() in ("—", "-") else plain(deps).replace(", ", ";")
        w.writerow([story, "Story", parent, f"{story} {plain(what)}", plain(area), owner(area), dep, phase,
                    f"PLN-01 §7.2; {sources[parent]}", f"Given/When/Then copied from the test plan of {sources[parent]}",
                    DONE, "truminds-skill-library"])
    return buf.getvalue()


def main() -> int:
    want = build()
    if "--check" in sys.argv:
        have = OUT.read_text(encoding="utf-8") if OUT.is_file() else ""
        if have != want:
            print("backlog check: docs/planning/backlog.csv is out of date; run python3 scripts/build_backlog.py")
            return 1
        print(f"backlog check: {want.count(chr(10)) - 1} rows match PLN-01 §7")
        return 0
    OUT.write_text(want, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} ({want.count(chr(10)) - 1} rows)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
