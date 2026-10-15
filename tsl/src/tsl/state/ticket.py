"""Ticket snapshot from an engineer's file (SDD-01 §5.1, O-07).

Written to artifacts/<ticket>/<run_id>/ticket.md. The file is read before the lock is taken, so a
bad file never leaves a run behind. Front matter in the file is optional: tsl owns schema, run_id,
ticket, source, fetched_at and source_sha256, and keeps only title and issue_type from it.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from tsl.core.errors import TslError
from tsl.core.jsonio import dump_yaml
from tsl.core.paths import artifact_dir

MAX_BYTES = 256 * 1024
KEPT = ("title", "issue_type")
HEADING = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)


@dataclass
class TicketFile:
    body: str
    sha256: str
    kept: dict[str, Any]


def _bad(detail: str) -> TslError:
    return TslError("E-USE-01", detail=f"--ticket-file: {detail}", cmd="state start")


def load(path: str, ticket: str, deny: frozenset[str] = frozenset()) -> TicketFile:
    p = Path(path)
    try:
        raw = p.read_bytes()
    except OSError:
        raise _bad(f"cannot read {path}") from None
    if len(raw) > MAX_BYTES:
        raise _bad(f"{path} is over {MAX_BYTES // 1024} KiB")
    if b"\0" in raw:
        raise _bad(f"{path} is not a text file")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise _bad(f"{path} is not UTF-8") from None
    text = text.replace("\r\n", "\n")
    front: dict[str, Any] = {}
    body = text
    if text.startswith("---\n"):
        head, sep, rest = text[4:].partition("\n---\n")
        if not sep:
            raise _bad("front matter has no closing ---")
        try:
            parsed = yaml.safe_load(head) or {}
        except yaml.YAMLError:
            raise _bad("front matter is not valid YAML") from None
        if not isinstance(parsed, dict):
            raise _bad("front matter is not a mapping")
        front, body = parsed, rest.lstrip("\n")
    named = front.get("ticket")
    if named is not None and str(named) != ticket:
        raise _bad(f"the file is for {named}, not {ticket}")
    if not body.strip():
        raise _bad("the ticket text is empty")
    from tsl.harness import detectors

    offset = text.count("\n", 0, len(text) - len(body))
    for h in detectors.scan(body, deny_term_hashes=deny):
        if h.kind in ("secret", "pii", "term"):
            # file and line only: the matched value is never echoed (SDD-11 §7.3)
            raise _bad(f"line {h.line + offset}: {h.kind} rule {h.rule_id}; remove it and retry")
    kept = {k: str(front[k]) for k in KEPT if front.get(k) is not None}
    if "title" not in kept and (m := HEADING.search(body)):
        kept["title"] = m.group(1)
    if len(kept.get("title", "")) > 300 or len(kept.get("issue_type", "")) > 40:
        raise _bad("title or issue_type is too long")
    return TicketFile(body, hashlib.sha256(raw).hexdigest(), kept)


def snapshot_rel(ticket: str, run_id: str) -> str:
    return f"{artifact_dir(ticket, run_id)}/ticket.md"


def render(tf: TicketFile, ticket: str, run_id: str, fetched_at: str) -> str:
    fm: dict[str, Any] = {
        "schema": "ticket-snapshot.v1",
        "run_id": run_id,
        "ticket": ticket,
        "source": "file",
        "fetched_at": fetched_at,
        **tf.kept,
        "source_sha256": tf.sha256,
    }
    from tsl.schemas.registry import errors

    errs = errors("ticket-snapshot.v1", fm)
    if errs:
        raise _bad(f"{errs[0].pointer} {errs[0].message}")
    return f"---\n{dump_yaml(fm)}---\n{tf.body}"
