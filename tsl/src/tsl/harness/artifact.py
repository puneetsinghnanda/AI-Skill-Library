"""Load an artifact: front matter envelope + body schema + body text (Doc 5 §3.6)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tsl.core.frontmatter import Document, FrontMatterError, split
from tsl.core.hashing import sha256_file
from tsl.core.paths import ARTIFACT_RE


@dataclass
class Artifact:
    rel: str
    path: Path
    text: str
    sha256: str
    doc: Document | None
    parse_error: str | None = None
    ticket: str | None = None
    run_id: str | None = None
    step: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def front(self) -> dict[str, Any]:
        return self.doc.front if self.doc else {}

    @property
    def schema(self) -> str:
        return str(self.front.get("schema", ""))


def load(root: Path, rel: str) -> Artifact:
    p = root / rel
    text = p.read_text(encoding="utf-8")
    sha = sha256_file(p)
    m = ARTIFACT_RE.match(rel)
    try:
        doc: Document | None = split(text)
        err = None
    except FrontMatterError as exc:
        doc, err = None, str(exc)
    return Artifact(
        rel,
        p,
        text,
        sha,
        doc,
        err,
        m.group("ticket") if m else None,
        m.group("run_id") if m else None,
        m.group("step") if m else None,
    )
