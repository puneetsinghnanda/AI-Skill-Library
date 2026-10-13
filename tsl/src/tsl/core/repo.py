"""Companion repo discovery and access (SDD-04 §3.1 --repo, SDD-12)."""

from __future__ import annotations

from functools import cached_property
from pathlib import Path
from typing import Any

from tsl.core.config import TslConfig, load_config
from tsl.core.errors import TslError
from tsl.core.jsonio import read_yaml
from tsl.gitops.git import Git


def find_root(start: Path) -> Path | None:
    cur = start.resolve()
    for p in (cur, *cur.parents):
        if (p / "tsl.yaml").is_file():
            return p
    return None


class Companion:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.warnings: list[dict[str, str]] = []

    @classmethod
    def discover(cls, repo: Path | None, cwd: Path | None = None) -> Companion:
        if repo is not None:
            if not (repo / "tsl.yaml").is_file():
                raise TslError("E-REPO-01")
            return cls(repo.resolve())
        root = find_root(cwd or Path.cwd())
        if root is None:
            raise TslError("E-REPO-01")
        return cls(root)

    @cached_property
    def config(self) -> TslConfig:
        cfg, warnings = load_config(self.root / "tsl.yaml")
        self.warnings.extend(warnings)
        return cfg

    @cached_property
    def git(self) -> Git:
        return Git(self.root)

    def path(self, rel: str) -> Path:
        return self.root / rel

    def rel(self, p: Path) -> str:
        return p.resolve().relative_to(self.root).as_posix()

    def local_paths(self) -> dict[str, Path]:
        """.tsl/local.yaml (tsl-local.v1): product repo name -> clone path on this laptop."""
        p = self.root / ".tsl" / "local.yaml"
        if not p.exists():
            return {}
        from tsl.schemas.registry import require_valid

        data = read_yaml(p)
        require_valid("tsl-local.v1", data, ".tsl/local.yaml")
        out: dict[str, Path] = {}
        for name, path in data["product_repos"].items():
            q = Path(path)
            out[name] = q if q.is_absolute() else (self.root / q).resolve()
        return out

    def product_clone(self, name: str) -> Path | None:
        p = self.local_paths().get(name)
        return p if p and p.exists() else None

    def system_policy(self) -> dict[str, Any] | None:
        p = self.root / self.config.policy
        if not p.exists():
            return None
        from tsl.schemas.registry import require_valid

        data = read_yaml(p)
        require_valid("policy.v2", data, self.config.policy)
        return data if isinstance(data, dict) else None
