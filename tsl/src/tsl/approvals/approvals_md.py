"""approvals.md: parse into approvals.v1, append entries and signature blocks.

Doc 4 §4.2, SDD-07 §6.4.

tsl reads only the defined fields. Other text is ignored and never treated as instructions.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from tsl.core.errors import TslError
from tsl.core.frontmatter import FrontMatterError, split
from tsl.core.hashing import sha256_text
from tsl.core.jsonio import atomic_write, dump_yaml

HEAD = re.compile(r"^## (?P<id>G-[a-z0-9-]+|W-[0-9]+) · required role: (?P<role>[a-z_]+)\s*$")
ART = re.compile(r"^Artifact: (?P<path>\S+) \(sha256 (?P<sha>[0-9a-f]{64})\)\s*$")
FIELD = re.compile(r"^(?P<k>decision|comment|kind|Reason for gate|Action):\s?(?P<v>.*)$")
SIG_BEGIN = "<!-- tsl:signature-begin {id} -->"
SIG_END = "<!-- tsl:signature-end {id} -->"
SIG_NOTE = "<!-- signature block written by `tsl approve` - do not edit -->"


def comment_sha256(comment: str | None) -> str:
    text = "\n".join(line.rstrip() for line in (comment or "").replace("\r\n", "\n").split("\n"))
    return sha256_text(text.strip())


def _value(v: str) -> str | None:
    v = re.sub(r"\s+#.*$", "", v).strip()
    return v or None


def parse(text: str) -> dict[str, Any]:
    try:
        doc = split(text)
    except FrontMatterError as exc:
        raise TslError("E-CFG-01", file="approvals.md", pointer="/", reason=str(exc)) from exc
    obj: dict[str, Any] = {
        "schema": doc.front.get("schema"),
        "run_id": doc.front.get("run_id"),
        "entries": [],
    }
    cur: dict[str, Any] | None = None
    in_comment = False
    sig_lines: list[str] | None = None
    for line in doc.body.split("\n"):
        m = HEAD.match(line)
        if m:
            cur = {
                "id": m.group("id"),
                "kind": "workflow_gate",
                "role": m.group("role"),
                "artifacts": [],
                "reason": None,
                "action": None,
                "decision": None,
                "comment": None,
                "signature": None,
            }
            if cur["id"].startswith("W-"):
                cur["kind"] = "external_write"
            elif cur["id"].startswith("G-escalate-"):
                cur["kind"] = "escalation"
            obj["entries"].append(cur)
            in_comment = False
            continue
        if cur is None:
            continue
        if sig_lines is not None:
            if line.strip() == SIG_END.format(id=cur["id"]):
                body = "\n".join(x for x in sig_lines if not x.strip().startswith("```"))
                try:
                    cur["signature"] = json.loads(body)
                except ValueError:
                    cur["signature"] = {"invalid": True}
                sig_lines = None
            else:
                sig_lines.append(line)
            continue
        if line.strip() == SIG_BEGIN.format(id=cur["id"]):
            sig_lines = []
            in_comment = False
            continue
        if line.strip().startswith("<!--"):
            in_comment = False
            continue
        am = ART.match(line)
        if am:
            cur["artifacts"].append({"path": am.group("path"), "sha256": am.group("sha")})
            continue
        fm = FIELD.match(line)
        if fm:
            k, v = fm.group("k"), fm.group("v")
            in_comment = False
            if k == "decision":
                cur["decision"] = _value(v)
            elif k == "comment":
                cur["comment"] = v.strip() or None
                in_comment = True
            elif k == "kind":
                cur["kind"] = v.strip()
            elif k == "Reason for gate":
                cur["reason"] = v.strip()[:500] or None
            elif k == "Action":
                parts = dict(p.split("=", 1) for p in v.split() if "=" in p)
                cur["action"] = {"tool": parts.get("tool", ""), "target": parts.get("target", "")}
            continue
        if in_comment and line.strip():
            cur["comment"] = ((cur["comment"] or "") + "\n" + line.strip()).strip()
    return obj


def load(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"schema": "approvals.v1", "entries": []}
    obj = parse(path.read_text(encoding="utf-8"))
    from tsl.schemas.registry import errors

    errs = errors("approvals.v1", obj)
    if errs:
        raise TslError(
            "E-CFG-01", file="approvals.md", pointer=errs[0].pointer, reason=errs[0].message
        )
    return obj


def entry(obj: dict[str, Any], gate: str) -> dict[str, Any] | None:
    found = [e for e in obj.get("entries", []) if e["id"] == gate]
    return found[-1] if found else None


def append_entry(
    path: Path,
    run_id: str,
    gate: str,
    role: str,
    kind: str,
    artifacts: list[dict[str, str]],
    reason: str,
    action: dict[str, str] | None = None,
) -> None:
    if path.is_file():
        text = path.read_text(encoding="utf-8").rstrip("\n") + "\n"
    else:
        text = "---\n" + dump_yaml({"schema": "approvals.v1", "run_id": run_id}) + "---\n"
    lines = ["", f"## {gate} · required role: {role}", f"kind: {kind}"]
    lines += [f"Artifact: {a['path']} (sha256 {a['sha256']})" for a in artifacts]
    if action:
        lines.append(f"Action: tool={action['tool']} target={action['target']}")
    lines += [
        f"Reason for gate: {reason}",
        "decision:          # approve | reject | changes | abort",
        "comment:",
        SIG_NOTE,
        "",
    ]
    atomic_write(path, text + "\n".join(lines))


def append_signature(path: Path, gate: str, block: dict[str, Any]) -> None:
    lines = path.read_text(encoding="utf-8").split("\n")
    start = None
    for i, line in enumerate(lines):
        m = HEAD.match(line)
        if m and m.group("id") == gate:
            start = i
    if start is None:
        raise TslError(
            "E-RUN-05",
            status="unknown",
            command="approve",
            needed="a gate entry",
            hint=f"no entry {gate} in approvals.md",
        )
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if HEAD.match(lines[j]):
            end = j
            break
    while end > start and not lines[end - 1].strip():
        end -= 1
    pretty = json.dumps(block, indent=2, sort_keys=True, ensure_ascii=False).split("\n")
    sig = [SIG_BEGIN.format(id=gate), "```json", *pretty, "```", SIG_END.format(id=gate)]
    atomic_write(path, "\n".join([*lines[:end], *sig, *lines[end:]]).rstrip("\n") + "\n")
