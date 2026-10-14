#!/usr/bin/env python3
"""commit-msg hook: the first line follows Conventional Commits (DEV-01 §2.4). CI checks PR titles."""

from __future__ import annotations

import re
import sys

TYPES = "feat|fix|docs|test|refactor|perf|build|ci|chore|revert"
PATTERN = re.compile(rf"^({TYPES})(\([a-z,-]+\))?!?: .{{1,72}}$")
EXEMPT = ("Merge ", "Revert ", "fixup!", "squash!")


def main(path: str) -> int:
    with open(path, encoding="utf-8") as fh:
        title = fh.readline().strip()
    if PATTERN.match(title) or title.startswith(EXEMPT):
        return 0
    print(f"commit title must follow Conventional Commits (DEV-01 §2.4): {title!r}")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
