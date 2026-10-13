"""Installed skills in the plugin (SDD-01 §2, §4): metadata, rubric, outputs, version ranges."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import Any

from tsl.core.errors import TslError
from tsl.core.frontmatter import FrontMatterError, split
from tsl.core.jsonio import read_yaml

SEMVER = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


def parse_semver(v: str) -> tuple[int, int, int]:
    m = SEMVER.match(v)
    if not m:
        raise ValueError(f"not semver: {v}")
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def range_matches(version: str, rng: str) -> bool:
    """`^1.2` >=1.2.0 <2.0.0; `~1.2` >=1.2.0 <1.3.0; `1.2.3` exact; `1.2` / `1` prefix."""
    v = parse_semver(version)
    op = rng[0] if rng[:1] in "^~" else ""
    parts = [int(x) for x in rng.lstrip("^~").split(".")]
    lo = tuple(parts + [0] * (3 - len(parts)))
    if op == "^":
        return v >= lo and v[0] == lo[0] if lo[0] > 0 else v >= lo and v[:2] == lo[:2]
    if op == "~":
        return v >= lo and v[:2] == lo[:2]
    return v[: len(parts)] == tuple(parts)


@dataclass
class Skill:
    dir: Path
    meta: dict[str, Any]

    @property
    def id(self) -> str:
        return str(self.meta["id"])

    @property
    def version(self) -> str:
        return str(self.meta["version"])

    @property
    def ref(self) -> str:
        return f"{self.id}@{self.version}"

    @property
    def artifact_output(self) -> dict[str, Any]:
        for o in self.meta["outputs"]:
            if o.get("kind", "artifact") == "artifact":
                return dict(o)
        raise TslError(
            "E-CFG-01",
            file=f"{self.id}/skill.yaml",
            pointer="/outputs",
            reason="no artifact output",
        )

    @property
    def is_code(self) -> bool:
        return any(o.get("kind") == "code" for o in self.meta["outputs"])

    @property
    def allowed_tools(self) -> list[str]:
        return list(self.meta.get("allowed_tools", []))

    @property
    def harness(self) -> dict[str, Any]:
        return dict(self.meta.get("harness") or {})

    @property
    def trace_required(self) -> bool:
        return bool(self.harness.get("trace_required", True))

    @cached_property
    def rubric(self) -> dict[str, Any]:
        p = self.dir / str(self.meta["rubric"])
        try:
            doc = split(p.read_text(encoding="utf-8"))
        except (OSError, FrontMatterError) as exc:
            raise TslError("E-CFG-01", file=str(p.name), pointer="/", reason=str(exc)) from exc
        return doc.front

    @property
    def rubric_path(self) -> Path:
        return self.dir / str(self.meta["rubric"])

    @cached_property
    def checks(self) -> dict[str, Any] | None:
        name = self.meta.get("checks") or self.harness.get("checks")
        if not name:
            return None
        p = self.dir / str(name)
        if not p.exists():
            return None
        data = read_yaml(p)
        return data if isinstance(data, dict) else None


def load_skill(d: Path) -> Skill:
    from tsl.schemas.registry import require_valid

    p = d / "skill.yaml"
    data = read_yaml(p)
    require_valid("skill-metadata.v1", data, f"{d.name}/skill.yaml")
    return Skill(d, data)


def installed(plugin_root: Path) -> dict[str, Skill]:
    out: dict[str, Skill] = {}
    base = plugin_root / "skills"
    if not base.is_dir():
        return out
    for d in sorted(base.iterdir()):
        if (d / "skill.yaml").is_file():
            s = load_skill(d)
            out[s.id] = s
    return out
