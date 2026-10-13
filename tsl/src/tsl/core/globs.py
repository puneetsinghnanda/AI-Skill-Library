"""Path globs with `**` (any number of folders), `*` and `?` inside one folder."""

from __future__ import annotations

import re
from functools import lru_cache


@lru_cache(maxsize=512)
def _compile(pattern: str) -> re.Pattern[str]:
    out = ""
    i = 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out += "(?:.*/)?"
            i += 3
        elif pattern.startswith("**", i):
            out += ".*"
            i += 2
        elif pattern[i] == "*":
            out += "[^/]*"
            i += 1
        elif pattern[i] == "?":
            out += "[^/]"
            i += 1
        else:
            out += re.escape(pattern[i])
            i += 1
    return re.compile(out + r"\Z")


def match(path: str, pattern: str) -> bool:
    p = path.replace("\\", "/")
    if not pattern.startswith("/"):
        p = p.lstrip("/")
    return bool(_compile(pattern).match(p))


def any_match(path: str, patterns: list[str]) -> bool:
    return any(match(path, p) for p in patterns)
