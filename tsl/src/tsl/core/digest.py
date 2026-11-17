"""Digests of file trees, pinned in run state to warn when installed files change.

The digest covers each file's relative path, size and modification time, not its bytes:
reading ~1000 plugin files on every `tsl state start` cost ~2 s, while a directory scan
is cheap. It is a warn-only signal (W-PIN-01), so this trade-off is acceptable.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

_SKIP_DIRS = {
    "__pycache__",
    ".git",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".venv",
    "node_modules",
    "tests",  # test fixtures do not change how a run behaves; keeps the hook fast
}


def _scan(root: Path, rel: str, out: list[tuple[str, int, int]]) -> None:
    with os.scandir(root / rel if rel else root) as it:
        for e in it:
            name = f"{rel}/{e.name}" if rel else e.name
            if e.is_dir(follow_symlinks=False):
                if e.name not in _SKIP_DIRS:
                    _scan(root, name, out)
            elif e.is_file() and not e.name.endswith(".pyc"):
                st = e.stat()
                out.append((name, st.st_size, st.st_mtime_ns))


def tree_digest(root: Path) -> str:
    files: list[tuple[str, int, int]] = []
    _scan(root, "", files)
    h = hashlib.sha256()
    for name, size, mtime in sorted(files):
        h.update(f"{name}\0{size}\0{mtime}\0".encode())
    return "sha256:" + h.hexdigest()


def tsl_digest() -> str:
    import tsl

    return tree_digest(Path(tsl.__file__).parent)
