"""Citation grammar, resolution and matching (SDD-03 §8, SDD-06 §3.4, DEF-08)."""

from __future__ import annotations

import difflib
import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tsl.core.frontmatter import github_slug, headings, section_text
from tsl.core.globs import any_match
from tsl.core.jsonio import load_yaml
from tsl.gitops.git import Git

LINES = re.compile(r"^L([1-9][0-9]*)(?:-L([1-9][0-9]*))?$")
SLUG = re.compile(r"^[a-z0-9][a-z0-9-]*$")
FACT = re.compile(r"^(module|dep|import|http|ui|call|table|column|index|migration|test|sym):\S+$")
READ_DENY = [
    "**/.env",
    "**/.env.*",
    "**/*.pem",
    "**/*.key",
    "**/*.p12",
    "**/*.pfx",
    "**/id_rsa*",
    "**/id_ed25519*",
    "**/secrets/**",
    "**/*.kdbx",
    ".env",
    ".env.*",
    "secrets/**",
]
MAX_BYTES = 2 * 1024 * 1024
WIDEN = 3
RATIO = 0.92


@dataclass(frozen=True)
class Cite:
    repo: str | None
    path: str
    anchor: str
    raw: str


@dataclass
class CiteResult:
    ok: bool
    reason: str | None = None
    format_only: bool = False


def parse(raw: str, repos: set[str]) -> Cite | None:
    """None when the string does not match the grammar (E-H1-05)."""
    if "#" not in raw or any(c.isspace() for c in raw):
        return None
    left, anchor = raw.split("#", 1)
    repo: str | None = None
    if ":" in left:
        repo, left = left.split(":", 1)
        if repo not in repos:
            return None
    path = left
    if not path or path.startswith("/") or "\\" in path or ".." in path.split("/"):
        return None
    m = LINES.match(anchor)
    if m:
        if m.group(2) and not 0 <= int(m.group(2)) - int(m.group(1)) <= 200:
            return None
    elif not (
        SLUG.match(anchor) or anchor.startswith(("sym:", "key:", "node:")) or FACT.match(anchor)
    ):
        return None
    return Cite(repo, path, anchor, raw)


def normalise(s: str) -> str:
    s = unicodedata.normalize("NFC", s).replace("\t", " ")
    return re.sub(r"\s+", " ", s).strip()


def quote_matches(quote: str, span: str) -> bool:
    q, sp = normalise(quote), normalise(span)
    if not q:
        return False
    if q in sp:
        return True
    n = len(q)
    if n > len(sp):
        return difflib.SequenceMatcher(None, q, sp).ratio() >= RATIO
    best = 0.0
    step = max(1, n // 8)
    for i in range(0, len(sp) - n + 1, step):
        r = difflib.SequenceMatcher(None, q, sp[i : i + n]).ratio()
        if r > best:
            best = r
            if best >= RATIO:
                return True
    return best >= RATIO


def element_matches(elements: list[str], span: str) -> bool:
    return all(re.search(r"(?<![\w])" + re.escape(e) + r"(?![\w])", span) for e in elements)


def elements_of(claim: dict[str, Any]) -> list[str]:
    if claim.get("element"):
        return [str(claim["element"])]
    return re.findall(r"`([^`]+)`", str(claim.get("text", "")))


class Resolver:
    """Reads cited files: companion working tree, product repos at a fixed SHA (git show)."""

    def __init__(self, companion: Path, clones: dict[str, Path], shas: dict[str, str]) -> None:
        self.companion = companion
        self.clones = clones
        self.shas = shas
        self._cache: dict[tuple[str | None, str], str | None] = {}

    def read(self, c: Cite) -> tuple[str | None, str | None]:
        key = (c.repo, c.path)
        if any_match(c.path, READ_DENY):
            return None, "read-denied path"
        if key in self._cache:
            v = self._cache[key]
            return (v, None) if v is not None else (None, "path not found")
        data: bytes | None
        if c.repo is None:
            p = (self.companion / c.path).resolve()
            try:
                p.relative_to(self.companion.resolve())
            except ValueError:
                return None, "path outside repo"
            if not p.is_file():
                self._cache[key] = None
                return None, "path not found"
            if p.stat().st_size > MAX_BYTES:
                return None, "file too large"
            data = p.read_bytes()
        else:
            clone, sha = self.clones.get(c.repo), self.shas.get(c.repo)
            if clone is None or not sha:
                return None, "repo not available"
            data = Git(clone).show(sha, c.path)
            if data is None:
                self._cache[key] = None
                return None, "path not found"
            if len(data) > MAX_BYTES:
                return None, "file too large"
        if b"\0" in data[:8000]:
            return None, "binary file"
        text = data.decode("utf-8", errors="replace")
        self._cache[key] = text
        return text, None


def span_for(
    c: Cite, text: str, generated: dict[str, Any] | None = None
) -> tuple[str | None, str | None]:
    lines = text.split("\n")
    m = LINES.match(c.anchor)
    if m:
        n = int(m.group(1))
        e = int(m.group(2) or n)
        if n > len(lines):
            return None, "line out of range"
        lo, hi = max(1, n - WIDEN), min(len(lines), e + WIDEN)
        return "\n".join(lines[lo - 1 : hi]), None
    if c.anchor.startswith("key:"):
        try:
            data = json.loads(text) if c.path.endswith(".json") else load_yaml(text)
        except Exception:
            return None, "not structured"
        cur: Any = data
        for part in c.anchor[4:].split("."):
            if isinstance(cur, dict) and part in cur:
                cur = cur[part]
            else:
                return None, "key not found"
        return json.dumps(cur, ensure_ascii=False), None
    if FACT.match(c.anchor) and c.path.endswith(".json"):
        try:
            data = json.loads(text)
        except ValueError:
            return None, "not json"
        for f in data.get("facts", []):
            if f.get("id") == c.anchor:
                return json.dumps(f, ensure_ascii=False, sort_keys=True), None
        return None, "fact not found"
    if c.anchor.startswith("sym:"):
        return _symbol_span(c.anchor[4:], c.path, text, generated)
    hs = headings(text)
    for h in hs:
        if h.anchor == c.anchor or github_slug(h.title) == c.anchor:
            return h.title + "\n" + section_text(text, h, hs), None
    return None, "anchor not found"


def _symbol_span(
    name: str, path: str, text: str, generated: dict[str, Any] | None
) -> tuple[str | None, str | None]:
    lines = text.split("\n")
    for f in (generated or {}).get("facts", []):
        if (
            f.get("id", "").startswith("sym:")
            and f.get("name") == name
            and (f.get("source") or {}).get("path") == path
        ):
            s, e = int(f["source"]["line"]), int(f.get("end_line", f["source"]["line"]))
            return "\n".join(lines[s - 1 : e]), None
    if not re.search(r"\.(m|c)?[jt]sx?$", path):
        return None, "symbol lookup unsupported for this language"
    pat = re.compile(
        r"(function\s+%s\b|class\s+%s\b|(const|let|var)\s+%s\s*=|export\s+.*\b%s\b)"
        % ((re.escape(name),) * 4)
    )
    for i, line in enumerate(lines):
        if pat.search(line):
            depth, j = 0, i
            seen = False
            while j < len(lines):
                depth += lines[j].count("{") - lines[j].count("}")
                seen = seen or "{" in lines[j]
                if seen and depth <= 0:
                    break
                j += 1
            return "\n".join(lines[i : j + 1]), None
    return None, "symbol not found"


def verify(
    c: Cite,
    quote: str | None,
    elements: list[str],
    resolver: Resolver,
    generated: dict[str, Any] | None = None,
) -> CiteResult:
    if c.anchor.startswith("node:"):
        return CiteResult(True, None, format_only=True)
    text, why = resolver.read(c)
    if text is None:
        return CiteResult(False, why)
    span, why = span_for(c, text, generated)
    if span is None:
        return CiteResult(False, why)
    if quote is not None:
        return (
            CiteResult(True) if quote_matches(quote, span) else CiteResult(False, "quote not found")
        )
    if not elements:
        return CiteResult(False, "unverifiable: no element")
    return (
        CiteResult(True) if element_matches(elements, span) else CiteResult(False, "element absent")
    )
