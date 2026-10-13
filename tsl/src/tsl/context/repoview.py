"""Read-only view of one product repo at one commit (SDD-06 §5.1). Never the working tree."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from tsl.core.globs import any_match, match
from tsl.gitops.git import Git

EXCLUDE = [
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
    "**/*dump*.sql",
    "**/*.sqlite*",
    "**/*.db",
    "**/fixtures/**/*.csv",
    "**/seed*/**",
    "**/*.har",
    "**/*.log",
    "**/node_modules/**",
]
MAX_READ = 1_048_576


def excluded(path: str, extra: list[str]) -> bool:
    return any_match(path, [*EXCLUDE, *extra])


@dataclass
class RepoView:
    repo: str
    commit: str
    scope: str
    clone: Path
    extra_exclude: list[str] = field(default_factory=list)
    excluded_count: int = 0
    _files: list[str] | None = None

    def list_files(self, pattern: str = "**") -> list[str]:
        if self._files is None:
            allf = Git(self.clone).ls_tree(self.commit, self.scope)
            keep = [f for f in allf if not excluded(f, self.extra_exclude)]
            self.excluded_count = len(allf) - len(keep)
            self._files = keep
        if pattern == "**":
            return list(self._files)
        return [f for f in self._files if match(f, pattern)]

    def read_text(self, path: str, max_bytes: int = MAX_READ) -> str | None:
        if excluded(path, self.extra_exclude):
            return None
        data = Git(self.clone).show(self.commit, path)
        if data is None or len(data) > max_bytes or b"\0" in data[:8000]:
            return None
        return data.decode("utf-8", errors="replace")
