"""tsl.yaml (tsl-config.v1) loading, org defaults and the tighten-only rule (SDD-04 §7.2)."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from tsl.core.errors import TslError
from tsl.core.jsonio import read_yaml

# Org defaults (DEF-03, DEF-05, R-01, R-02, Doc 3 §5.3). Systems may only tighten them.
ORG_DEFAULTS: dict[str, Any] = {
    "context": {
        "max_age_days": 30,
        "drift_files": 50,
        "max_commits_behind": 50,
        "critical_paths": [],
    },
    "change_limits": {
        "lines": 400,
        "files": 15,
        "sensitive_paths": ["**/auth/**", "**/migrations/**", ".github/**"],
    },
    "retry": {"checks": 2, "review": 2, "verifier": 3},
    "max_rework": 2,
    "gates": {"self_approval": False, "lock_timeout_hours": 24},
    "pr": {"branch_prefix": "tsl/", "labels": []},
    "bands": {
        "high": {"S1_min": 0.90, "S2_min": 1.00, "S3_min": 4.0, "S6_max_ratio": 1.0},
        "medium": {"S1_min": 0.75, "S2_min": 0.90, "S3_min": 3.0, "S6_max_ratio": 2.0},
    },
    "ci": {"non_code_globs": ["**/*.md", "docs/**"]},
}


class SystemCodes(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str
    project: str
    client: str


class ProductRepo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    url: str
    path: str = "."
    default_branch: str = "main"
    verifier_profile: str
    pr: dict[str, Any] | None = None


class Gates(BaseModel):
    model_config = ConfigDict(extra="forbid")
    self_approval: bool = False
    lock_timeout_hours: int = 24


class TslConfig(BaseModel):
    """Typed view of tsl-config.v1. The JSON Schema is checked first; this model must agree."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    schema_: str = Field(alias="schema")
    system: SystemCodes
    companion: dict[str, Any]
    product_repos: list[ProductRepo]
    read_only_repos: list[dict[str, Any]] = []
    context: dict[str, Any] = {}
    change_limits: dict[str, Any] = {}
    policy: str = "policy.yaml"
    gates: Gates = Gates()
    pr: dict[str, Any] = {}
    telemetry: dict[str, Any] = {}
    harness: dict[str, Any] = {}
    h4_allow: list[str] = []
    ci: dict[str, Any] = {}

    def repo(self, name: str) -> ProductRepo | None:
        return next((r for r in self.product_repos if r.name == name), None)

    @property
    def companion_branch(self) -> str:
        return str(self.companion.get("default_branch", "main"))

    @property
    def companion_repo(self) -> str:
        c = self.companion
        return str(c["repo"]) if "repo" in c else f"{c['org']}/{c['name']}"

    def ctx(self, key: str) -> Any:
        return self.context.get(key, ORG_DEFAULTS["context"][key])

    def limits(self) -> dict[str, Any]:
        base = copy.deepcopy(ORG_DEFAULTS["change_limits"])
        own = self.change_limits
        base["lines"] = min(base["lines"], own.get("lines", base["lines"]))
        base["files"] = min(base["files"], own.get("files", base["files"]))
        base["sensitive_paths"] = list(
            dict.fromkeys([*base["sensitive_paths"], *own.get("sensitive_paths", [])])
        )
        return dict(base)

    @property
    def telemetry_enabled(self) -> bool:
        return bool(self.telemetry.get("enabled", True))

    @property
    def branch_prefix(self) -> str:
        return str(self.pr.get("branch_prefix", ORG_DEFAULTS["pr"]["branch_prefix"]))


def tighten_errors(cfg: dict[str, Any]) -> list[tuple[str, str]]:
    """Values looser than the org default (E-CFG-01). Ranges are also in the schema."""
    errs: list[tuple[str, str]] = []
    for skill, bands in (cfg.get("harness", {}).get("bands") or {}).items():
        for level in ("high", "medium"):
            got = (bands or {}).get(level) or {}
            org = ORG_DEFAULTS["bands"][level]
            for k in ("S1_min", "S2_min", "S3_min"):
                if k in got and got[k] < org[k]:
                    errs.append(
                        (f"/harness/bands/{skill}/{level}/{k}", f"looser than org {org[k]}")
                    )
            if "S6_max_ratio" in got and got["S6_max_ratio"] > org["S6_max_ratio"]:
                errs.append(
                    (
                        f"/harness/bands/{skill}/{level}/S6_max_ratio",
                        f"looser than org {org['S6_max_ratio']}",
                    )
                )
    if "endpoint" in (cfg.get("telemetry") or {}):
        pass  # deprecated, ignored with a warning (SDD-04 §7.2)
    return errs


def load_config(path: Path) -> tuple[TslConfig, list[dict[str, str]]]:
    from tsl.schemas.registry import require_valid

    try:
        data = read_yaml(path)
    except Exception as exc:
        raise TslError(
            "E-CFG-01", file=str(path.name), pointer="/", reason=type(exc).__name__
        ) from exc
    if not isinstance(data, dict):
        raise TslError("E-CFG-01", file=path.name, pointer="/", reason="not a mapping")
    require_valid("tsl-config.v1", data, path.name)
    errs = tighten_errors(data)
    if errs:
        raise TslError("E-CFG-01", file=path.name, pointer=errs[0][0], reason=errs[0][1])
    warnings: list[dict[str, str]] = []
    if "endpoint" in (data.get("telemetry") or {}):
        warnings.append(
            {"code": "E-DEP-01", "message": "tsl.yaml telemetry.endpoint is deprecated and ignored"}
        )
    return TslConfig.model_validate(data), warnings


def effective_bands(
    skill_bands: dict[str, Any] | None, system_bands: dict[str, Any] | None
) -> dict[str, dict[str, float]]:
    """Defaults < skill < system; each level may only tighten (SDD-03 §10.2)."""
    out = copy.deepcopy(ORG_DEFAULTS["bands"])
    for layer in (skill_bands or {}, system_bands or {}):
        for level in ("high", "medium"):
            for k, v in (layer.get(level) or {}).items():
                if k == "S6_max_ratio":
                    out[level][k] = min(out[level][k], float(v))
                else:
                    out[level][k] = max(out[level][k], float(v))
    return {k: dict(v) for k, v in out.items()}
