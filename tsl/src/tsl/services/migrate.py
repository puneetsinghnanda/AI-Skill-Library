"""tsl migrate --to v<N> [--dry-run] (SDD-04 §6.19, R-09). Signed records are never rewritten."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tsl.core.errors import TslError
from tsl.core.repo import Companion
from tsl.schemas.registry import current_versions, split_ref

SIGNED = {"verification", "approval-signature", "pack-signature", "eval-result", "audit"}


def plan(comp: Companion, to: str, dry_run: bool) -> dict[str, Any]:
    if not to.startswith("v") or not to[1:].isdigit():
        raise TslError("E-USE-01", detail="--to must look like v2", cmd="migrate")
    target = int(to[1:])
    pending: list[dict[str, Any]] = []
    for p in sorted(comp.root.rglob("*")):
        if (
            not p.is_file()
            or ".git" in p.parts
            or p.suffix not in (".json", ".yaml", ".yml", ".md")
        ):
            continue
        sid = _schema_of(p)
        ref = split_ref(sid) if sid else None
        if not ref:
            continue
        name, ver = ref
        if ver < target and name not in SIGNED and current_versions().get(name, 0) >= target:
            pending.append({"path": comp.rel(p), "schema": sid, "to": f"{name}.v{target}"})
    if pending and not dry_run:
        raise TslError(
            "E-USE-01",
            detail="no upgrade function exists yet for these schemas; run with --dry-run",
            cmd="migrate",
        )
    return {"to": to, "files": pending, "dry_run": dry_run}


def _schema_of(p: Path) -> str:
    try:
        text = p.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""
    for line in text.splitlines()[:8]:
        s = line.strip().strip(",")
        if s.startswith(('"schema"', "schema:")):
            return s.split(":", 1)[1].strip().strip('"').strip("'")
    return ""
