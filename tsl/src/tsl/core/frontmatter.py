"""Markdown with YAML front matter: split, headings, sections (SDD-03 §4.3, §4.4)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from tsl.core.jsonio import load_yaml


class FrontMatterError(ValueError):
    pass


@dataclass
class Document:
    front: dict[str, Any]
    body: str
    body_start_line: int  # 1-based line number of the first body line


def split(text: str) -> Document:
    lines = text.replace("\r\n", "\n").split("\n")
    if not lines or lines[0].strip() != "---":
        raise FrontMatterError("no front matter")
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            raw = "\n".join(lines[1:i])
            try:
                front = load_yaml(raw)
            except Exception as exc:
                raise FrontMatterError(
                    f"front matter is not valid YAML: {type(exc).__name__}"
                ) from exc
            if not isinstance(front, dict):
                raise FrontMatterError("front matter is not a mapping")
            return Document(front, "\n".join(lines[i + 1 :]), i + 2)
    raise FrontMatterError("front matter not closed")


HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
ANCHOR = re.compile(r"\s*\{#([a-z0-9-]{1,64})\}\s*$")


@dataclass
class Heading:
    level: int
    title: str
    anchor: str | None
    line: int  # 0-based index in the text lines


def headings(text: str) -> list[Heading]:
    out: list[Heading] = []
    fence = False
    for i, line in enumerate(text.split("\n")):
        if line.lstrip().startswith(("```", "~~~")):
            fence = not fence
            continue
        if fence:
            continue
        m = HEADING.match(line)
        if m:
            title = m.group(2)
            am = ANCHOR.search(title)
            anchor = am.group(1) if am else None
            if am:
                title = title[: am.start()]
            out.append(Heading(len(m.group(1)), title.strip(), anchor, i))
    return out


def norm_title(t: str) -> str:
    return re.sub(r"\s+", " ", t.strip().lower()).rstrip(":").strip()


def section_text(text: str, h: Heading, all_h: list[Heading]) -> str:
    """Text from the heading to the next heading of the same or higher level, minus sub-headings."""
    lines = text.split("\n")
    end = len(lines)
    for other in all_h:
        if other.line > h.line and other.level <= h.level:
            end = other.line
            break
    body = []
    for idx in range(h.line + 1, end):
        if HEADING.match(lines[idx]):
            continue
        body.append(lines[idx])
    return "\n".join(body)


def github_slug(title: str) -> str:
    s = title.strip().lower()
    s = re.sub(r"[^\w\- ]", "", s)
    return s.replace(" ", "-")
