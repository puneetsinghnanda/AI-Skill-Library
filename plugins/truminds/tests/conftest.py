"""Shared loaders for the plugin tests. Paths are resolved from this file, so tests run from any directory."""

from __future__ import annotations

import json
import re
from functools import cache
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator

TESTS = Path(__file__).resolve().parent
PLUGIN = TESTS.parent
ROOT = PLUGIN.parent.parent
SCHEMAS = ROOT / "schemas"
SKILLS = PLUGIN / "skills"
WORKFLOWS = PLUGIN / "workflows"
PODS = ROOT / "pods"
DOCS = ROOT / "docs"
REGISTRY = DOCS / "architecture" / "registry.md"
SDD01 = DOCS / "design" / "SDD-01-skill-authoring.md"
SDD02 = DOCS / "design" / "SDD-02-workflow-orchestration.md"

STATUS_RANK = {"draft": 0, "pilot": 1, "production": 2}


def front_matter(path: Path) -> dict[str, Any] | None:
    """YAML front matter of a markdown file, or None when the file has none."""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---\n", 4)
    if end < 0:
        return None
    data = yaml.safe_load(text[4:end])
    return data if isinstance(data, dict) else None


def body(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        return text[end + 5 :]
    return text


def load(path: Path) -> Any:
    if path.suffix == ".md":
        return front_matter(path)
    text = path.read_text(encoding="utf-8")
    if path.suffix in (".yaml", ".yml"):
        return yaml.safe_load(text)
    return json.loads(text)


@cache
def schema_index() -> dict[str, Path]:
    index = json.loads((SCHEMAS / "index.json").read_text(encoding="utf-8"))
    return {e["id"]: SCHEMAS / e["file"] for e in index["schemas"]}


@cache
def validator(schema_id: str) -> Draft202012Validator:
    schema = json.loads(schema_index()[schema_id].read_text(encoding="utf-8"))
    return Draft202012Validator(schema, format_checker=Draft202012Validator.FORMAT_CHECKER)


def errors(schema_id: str, doc: Any) -> list[str]:
    return [f"{'/'.join(map(str, e.absolute_path))}: {e.message}" for e in validator(schema_id).iter_errors(doc)]


def sdlc_skill_dirs() -> list[Path]:
    return sorted(p.parent for p in SKILLS.glob("*/skill.yaml"))


@cache
def skill_meta() -> dict[str, dict[str, Any]]:
    return {d.name: yaml.safe_load((d / "skill.yaml").read_text(encoding="utf-8")) for d in sdlc_skill_dirs()}


@cache
def workflows() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for p in sorted(WORKFLOWS.glob("*.workflow.yaml")):
        out[p.name.removesuffix(".workflow.yaml")] = yaml.safe_load(p.read_text(encoding="utf-8"))
    return out


@cache
def pods() -> dict[str, dict[str, Any]]:
    return {p.parent.name: yaml.safe_load(p.read_text(encoding="utf-8")) for p in sorted(PODS.glob("*/pod.yaml"))}


@cache
def registry_command_skills() -> dict[str, str]:
    """Registry §3.2: slash command -> skill folder."""
    rows = re.findall(r"^\| `/truminds:([a-z-]+)` \| `skills/([a-z-]+)` \|", REGISTRY.read_text(encoding="utf-8"), re.M)
    return dict(rows)


@cache
def sdd01_catalogue() -> list[dict[str, str]]:
    """SDD-01 §12 table rows."""
    rows = []
    pat = re.compile(
        r"^\| (\d+) \| `([a-z-]+)` \| ([A-Z]{2,3}) \| ([^|]+) \| ([^|]+) \| ([^|]+) \| "
        r"[^|]+ \| [^|]+ \| ([A-Za-z]+) \|$",
        re.M,
    )
    for m in pat.finditer(SDD01.read_text(encoding="utf-8")):
        rows.append(
            {
                "id": m.group(2),
                "code": m.group(3),
                "title": m.group(4).strip(),
                "role": m.group(5).strip(),
                "phase": m.group(6).strip().lower(),
                "target": m.group(7).strip().lower(),
            }
        )
    return rows


def parse_semver(v: str) -> tuple[int, int, int]:
    a, b, c = (int(x) for x in v.split("."))
    return a, b, c


def satisfies(version: str, rng: str) -> bool:
    """SemVer range check for the forms used in workflow.v1 and pod.v1: ^x[.y[.z]], ~x[.y[.z]], x[.y[.z]]."""
    v = parse_semver(version)
    op = rng[0] if rng[0] in "^~" else ""
    parts = [int(x) for x in rng.lstrip("^~").split(".")]
    lo = tuple(parts + [0] * (3 - len(parts)))
    if v < lo:
        return False
    if op == "^":
        if lo[0] > 0:
            return v[0] == lo[0]
        if lo[1] > 0:
            return v[0] == 0 and v[1] == lo[1]
        return v[:3] == lo
    if op == "~":
        return v[0] == lo[0] and (len(parts) == 1 or v[1] == lo[1])
    return v[: len(parts)] == tuple(parts)


def split_ref(ref: str) -> tuple[str, str]:
    name, _, rng = ref.partition("@")
    return name, rng
