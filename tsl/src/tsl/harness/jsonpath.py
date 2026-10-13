"""A small, safe path language for structured front matter.

Supports the forms used by skill checks and eval assertions:
  $.a.b[*].c     a[].b     a[?k=='v'].b     a[?k==`true`]     a[0]
No code is evaluated.
"""

from __future__ import annotations

import json
import re
from typing import Any

TOKEN = re.compile(r"\.?([A-Za-z_][A-Za-z0-9_-]*)|\[(\*|\d+|\?[^\]]+)\]|\[\]")
FILTER = re.compile(
    r"^\?\s*@?\.?([A-Za-z_][A-Za-z0-9_]*)\s*(==|!=)\s*(?:'([^']*)'|`([^`]*)`|\"([^\"]*)\")$"
)


class PathError(ValueError):
    pass


def compile_path(path: str) -> list[tuple[str, str]]:
    p = path.strip()
    if p.startswith("$"):
        p = p[1:]
    pos = 0
    out: list[tuple[str, str]] = []
    while pos < len(p):
        m = TOKEN.match(p, pos)
        if not m or m.end() == pos:
            raise PathError(f"bad path {path!r} at {pos}")
        if m.group(1) is not None:
            out.append(("key", m.group(1)))
        elif m.group(2) is not None:
            g = m.group(2)
            if g == "*":
                out.append(("all", ""))
            elif g.isdigit():
                out.append(("idx", g))
            else:
                if not FILTER.match(g):
                    raise PathError(f"bad filter {g!r}")
                out.append(("filter", g))
        else:
            out.append(("all", ""))
        pos = m.end()
    return out


def _lit(raw: str | None, js: str | None, dq: str | None) -> Any:
    if raw is not None:
        return raw
    if dq is not None:
        return dq
    try:
        return json.loads(js or "null")
    except ValueError:
        return js


def select(obj: Any, path: str) -> list[Any]:
    cur: list[Any] = [obj]
    for kind, arg in compile_path(path):
        nxt: list[Any] = []
        for v in cur:
            if kind == "key":
                if isinstance(v, dict) and arg in v:
                    nxt.append(v[arg])
            elif kind == "all":
                if isinstance(v, list):
                    nxt.extend(v)
                elif isinstance(v, dict):
                    nxt.extend(v.values())
            elif kind == "idx":
                if isinstance(v, list) and int(arg) < len(v):
                    nxt.append(v[int(arg)])
            elif kind == "filter":
                m = FILTER.match(arg)
                if m is None:
                    raise PathError(f"bad filter {arg!r}")
                field, op, lit = m.group(1), m.group(2), _lit(m.group(3), m.group(4), m.group(5))
                items = v if isinstance(v, list) else []
                for it in items:
                    if isinstance(it, dict):
                        eq = it.get(field) == lit
                        if eq == (op == "=="):
                            nxt.append(it)
        cur = nxt
    return cur
