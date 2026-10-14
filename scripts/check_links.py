#!/usr/bin/env python3
"""Check that every relative link in the repository's markdown files resolves.

A link resolves when its target file or folder exists and, if it has a `#fragment`, the target
markdown file has a heading with that GitHub slug or an explicit `<a id="...">` anchor.
External links (http, https, mailto) are not fetched: CI has no business calling out.

Usage: python3 scripts/check_links.py [paths...]   (default: every tracked *.md; exit 1 on a break)
"""

from __future__ import annotations

import re
import subprocess
import sys
import unicodedata
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LINK = re.compile(r"(?<!!)\[(?:[^\[\]]|\[[^\]]*\])*\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
IMAGE = re.compile(r"!\[[^\]]*\]\(\s*<?([^)\s>]+)>?\s*\)")
HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
ANCHOR = re.compile(r"<a\s+(?:id|name)=\"([^\"]+)\"")
FENCE = re.compile(r"^\s*(```|~~~)")
SKIP_PARTS = {"node_modules", ".venv", "dist", "dist-demo", "test-results", "archive"}


def slug(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = text.replace("`", "").strip().lower()
    out = []
    for ch in text:
        cat = unicodedata.category(ch)
        if ch in " -_" or cat[0] in "LN":
            out.append(ch)
    return "".join(out).replace(" ", "-")


def strip_code(lines: list[str]) -> list[str]:
    keep, fenced = [], False
    for line in lines:
        if FENCE.match(line):
            fenced = not fenced
            keep.append("")
            continue
        keep.append("" if fenced else re.sub(r"`[^`]*`", "", line))
    return keep


@lru_cache(maxsize=None)
def anchors(path: Path) -> frozenset[str]:
    seen: dict[str, int] = {}
    out: set[str] = set()
    lines = path.read_text(encoding="utf-8").splitlines()
    for raw, line in zip(lines, strip_code(lines), strict=True):
        m = HEADING.match(line) if line else None
        if m:
            base = slug(m.group(2) if "`" not in raw else HEADING.match(raw).group(2))  # type: ignore[union-attr]
            n = seen.get(base, 0)
            seen[base] = n + 1
            out.add(base if n == 0 else f"{base}-{n}")
        out |= set(ANCHOR.findall(raw))
    return frozenset(out)


def markdown_files(args: list[str]) -> list[Path]:
    if args:
        return [Path(a).resolve() for a in args]
    out = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "*.md"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    files = [ROOT / f for f in out.splitlines() if f]
    return [f for f in files if f.is_file() and not SKIP_PARTS.intersection(f.relative_to(ROOT).parts)]


def check(md: Path) -> list[str]:
    errs: list[str] = []
    lines = strip_code(md.read_text(encoding="utf-8").splitlines())
    for no, line in enumerate(lines, 1):
        for target in [*LINK.findall(line), *IMAGE.findall(line)]:
            if re.match(r"^[a-z][a-z0-9+.-]*:", target, re.I) or target.startswith("//"):
                continue  # external or mailto; not fetched
            path_part, _, frag = target.partition("#")
            dest = md if not path_part else (md.parent / path_part).resolve()
            rel = md.relative_to(ROOT)
            if not dest.exists():
                errs.append(f"{rel}:{no}: missing target {target}")
                continue
            if frag and dest.is_file() and dest.suffix == ".md" and frag.lower() not in anchors(dest):
                errs.append(f"{rel}:{no}: no anchor #{frag} in {dest.relative_to(ROOT)}")
    return errs


def main(argv: list[str]) -> int:
    files = markdown_files(argv)
    errs = [e for f in files for e in check(f)]
    for e in errs:
        print(e)
    print(f"link check: {len(files)} markdown files, {len(errs)} broken link(s)")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
