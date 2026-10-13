"""Release-1 extractors for JavaScript and TypeScript repos (SDD-06 §5.2).

Deterministic: same commit and same extractor version give the same facts. They
read only through RepoView, never run product code, never touch the network.
Parsing is done with conservative regular expressions; anything not pinned down
is listed in `unresolved`, never guessed.
"""

from __future__ import annotations

import json
import posixpath
import re
from dataclasses import dataclass, field
from typing import Any, Protocol

from tsl.context.repoview import RepoView

JS_EXT = (".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx")


@dataclass
class ExtractResult:
    facts: list[dict[str, Any]] = field(default_factory=list)
    unresolved: list[dict[str, Any]] = field(default_factory=list)
    empty_reason: str | None = None


class Extractor(Protocol):
    name: str
    version: str
    section: str

    def applies(self, view: RepoView) -> bool: ...
    def extract(self, view: RepoView) -> ExtractResult: ...


def _src(view: RepoView, path: str, line: int = 1) -> dict[str, Any]:
    return {"repo": view.repo, "path": path, "line": max(1, line)}


def _line(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def modules_of(view: RepoView) -> list[str]:
    files = view.list_files()
    pk = sorted(
        posixpath.dirname(f) or "." for f in files if posixpath.basename(f) == "package.json"
    )
    if pk:
        return pk
    tops = sorted({f.split("/")[1] for f in files if f.startswith("src/") and f.count("/") >= 2})
    return [f"src/{t}" for t in tops] or ["."]


def module_for(path: str, modules: list[str]) -> str:
    best = "."
    for m in modules:
        if (m == "." or path == m or path.startswith(m + "/")) and len(m) >= len(best):
            best = m
    return best


class RepoTree:
    name, version, section = "repo-tree", "1.0.0", "module-map"
    SYM = re.compile(
        r"^\s*(?:export\s+(?:default\s+)?)?(?:async\s+)?(function|class)\s+([A-Za-z_$][\w$]*)"
        r"|^\s*export\s+const\s+([A-Za-z_$][\w$]*)\s*=",
        re.M,
    )

    def applies(self, view: RepoView) -> bool:
        return True

    def extract(self, view: RepoView) -> ExtractResult:
        files = view.list_files()
        mods = modules_of(view)
        res = ExtractResult()
        for m in mods:
            mine = [f for f in files if module_for(f, mods) == m]
            langs: dict[str, int] = {}
            for f in mine:
                ext = posixpath.splitext(f)[1].lstrip(".") or "none"
                langs[ext] = langs.get(ext, 0) + 1
            src = (
                f"{m}/package.json"
                if m != "."
                else ("package.json" if "package.json" in files else (mine[0] if mine else "."))
            )
            res.facts.append(
                {
                    "id": f"module:{view.repo}:{m}",
                    "kind": "module",
                    "name": m,
                    "files": len(mine),
                    "languages": dict(sorted(langs.items())),
                    "source": _src(view, src),
                }
            )
        for f in files:
            if not f.endswith(JS_EXT):
                continue
            text = view.read_text(f)
            if text is None:
                continue
            for mm in self.SYM.finditer(text):
                name = mm.group(2) or mm.group(3)
                start = _line(text, mm.start())
                end = _block_end(text, mm.start())
                res.facts.append(
                    {
                        "id": f"sym:{view.repo}:{f}:{name}",
                        "kind": "symbol",
                        "name": name,
                        "end_line": end,
                        "source": _src(view, f, start),
                    }
                )
        if not res.facts:
            res.empty_reason = "no tracked files in scope"
        return res


def _block_end(text: str, start: int) -> int:
    i = text.find("{", start)
    nl = text.find("\n", start)
    if i == -1 or (nl != -1 and i > nl and text[start:i].count("\n") > 1):
        return _line(text, start)
    depth = 0
    for j in range(i, len(text)):
        if text[j] == "{":
            depth += 1
        elif text[j] == "}":
            depth -= 1
            if depth == 0:
                return _line(text, j)
    return _line(text, len(text) - 1)


IMPORT = re.compile(
    r"""(?:import\s+[^'"]*?from\s*|require\(\s*|import\(\s*)['"](\.{1,2}/[^'"]+)['"]"""
)


class NpmManifests:
    name, version, section = "npm-manifests", "1.0.0", "dependency-graph"

    def applies(self, view: RepoView) -> bool:
        return any(posixpath.basename(f) == "package.json" for f in view.list_files())

    def extract(self, view: RepoView) -> ExtractResult:
        res = ExtractResult()
        files = view.list_files()
        locked: dict[str, str] = {}
        for f in files:
            if posixpath.basename(f) == "package-lock.json":
                try:
                    lock = json.loads(view.read_text(f) or "{}")
                except ValueError:
                    continue
                for k, v in (lock.get("packages") or {}).items():
                    if k.startswith("node_modules/") and isinstance(v, dict) and v.get("version"):
                        locked[k.removeprefix("node_modules/")] = str(v["version"])
        for f in files:
            if posixpath.basename(f) != "package.json":
                continue
            raw = view.read_text(f)
            try:
                pkg = json.loads(raw or "{}")
            except ValueError:
                res.unresolved.append(
                    {"source": _src(view, f), "reason": "package.json does not parse"}
                )
                continue
            for dev, key in ((False, "dependencies"), (True, "devDependencies")):
                for name, rng in sorted((pkg.get(key) or {}).items()):
                    fact = {
                        "id": f"dep:{view.repo}:{f}:{name}",
                        "kind": "dependency",
                        "name": name,
                        "range": str(rng)[:100],
                        "dev": dev,
                        "source": _src(view, f),
                    }
                    if name in locked:
                        fact["locked"] = locked[name]
                    res.facts.append(fact)
        mods = modules_of(view)
        edges: set[tuple[str, str]] = set()
        for f in files:
            if not f.endswith(JS_EXT):
                continue
            text = view.read_text(f)
            if text is None:
                continue
            for m in IMPORT.finditer(text):
                target = posixpath.normpath(posixpath.join(posixpath.dirname(f), m.group(1)))
                a, b = module_for(f, mods), module_for(target, mods)
                if a != b:
                    edges.add((a, b))
        for a, b in sorted(edges):
            res.facts.append({"id": f"import:{a}->{b}", "kind": "import", "from": a, "to": b})
        if not res.facts:
            res.empty_reason = "no dependencies declared"
        return res


ROUTE = re.compile(
    r"\b(app|router|[A-Za-z_$][\w$]*Router)\.(get|post|put|patch|delete)\(\s*(['\"`])([^'\"`]*)\3"
)
USE = re.compile(r"\bapp\.use\(\s*['\"]([^'\"]+)['\"]\s*,\s*([A-Za-z_$][\w$]*)\s*\)")
REQ = re.compile(
    r"(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*require\(\s*['\"](\.{1,2}/[^'\"]+)['\"]\s*\)"
    r"|import\s+([A-Za-z_$][\w$]*)\s+from\s+['\"](\.{1,2}/[^'\"]+)['\"]"
)
UI = re.compile(r"<Route\b[^>]*\bpath=\{?['\"]([^'\"]+)['\"]")
UI_OBJ = re.compile(r"\bpath\s*:\s*['\"](/[^'\"]*)['\"]")
FETCH = re.compile(r"\bfetch\(\s*(['\"`])(/[^'\"`]*)\1([^)]*)\)")
AXIOS = re.compile(r"\baxios\.(get|post|put|patch|delete)\(\s*(['\"`])(/[^'\"`]*)\2")


class JsRoutes:
    name, version, section = "js-routes", "1.0.0", "api-inventory"

    def applies(self, view: RepoView) -> bool:
        return any(f.endswith(JS_EXT) for f in view.list_files())

    def extract(self, view: RepoView) -> ExtractResult:
        res = ExtractResult()
        files = [f for f in view.list_files() if f.endswith(JS_EXT)]
        texts = {f: t for f in files if (t := view.read_text(f)) is not None}
        prefix: dict[str, str] = {}
        for f, text in texts.items():
            names: dict[str, str] = {}
            for m in REQ.finditer(text):
                ident, rel = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4))
                target = posixpath.normpath(posixpath.join(posixpath.dirname(f), rel))
                for cand in (
                    target,
                    *(target + e for e in JS_EXT),
                    *(target + "/index" + e for e in JS_EXT),
                ):
                    if cand in texts:
                        names[ident] = cand
                        break
            for m in USE.finditer(text):
                if m.group(2) in names:
                    prefix[names[m.group(2)]] = m.group(1).rstrip("/")
        seen: dict[str, int] = {}

        def add(fid: str, fact: dict[str, Any]) -> None:
            n = seen.get(fid, 0) + 1
            seen[fid] = n
            fact["id"] = fid if n == 1 else f"{fid}#{n}"
            res.facts.append(fact)

        for f, text in sorted(texts.items()):
            for m in ROUTE.finditer(text):
                line = _line(text, m.start())
                if m.group(3) == "`" or "${" in m.group(4):
                    res.unresolved.append(
                        {"source": _src(view, f, line), "reason": "dynamic path expression"}
                    )
                    continue
                path = prefix.get(f, "") + (
                    m.group(4) if m.group(4).startswith("/") else "/" + m.group(4)
                )
                path = path.rstrip("/") or "/"
                method = m.group(2).upper()
                add(
                    f"http:{method}:{path}",
                    {
                        "kind": "http",
                        "method": method,
                        "path": path,
                        "source": _src(view, f, line),
                        "confidence": "resolved",
                    },
                )
            for rx in (UI, UI_OBJ):
                for m in rx.finditer(text):
                    if rx is UI_OBJ and not re.search(r"createBrowserRouter|routes", text):
                        continue
                    add(
                        f"ui:{m.group(1)}",
                        {
                            "kind": "ui",
                            "path": m.group(1),
                            "source": _src(view, f, _line(text, m.start())),
                            "confidence": "resolved",
                        },
                    )
            for m in FETCH.finditer(text):
                line = _line(text, m.start())
                if m.group(1) == "`" and "${" in m.group(2):
                    res.unresolved.append(
                        {"source": _src(view, f, line), "reason": "dynamic path expression"}
                    )
                    continue
                mm = re.search(r"method\s*:\s*['\"](\w+)['\"]", m.group(3))
                method = (mm.group(1) if mm else "GET").upper()
                add(
                    f"call:{method}:{m.group(2)}",
                    {
                        "kind": "call",
                        "method": method,
                        "path": m.group(2),
                        "source": _src(view, f, line),
                        "confidence": "resolved",
                    },
                )
            for m in AXIOS.finditer(text):
                line = _line(text, m.start())
                if m.group(2) == "`" and "${" in m.group(3):
                    res.unresolved.append(
                        {"source": _src(view, f, line), "reason": "dynamic path expression"}
                    )
                    continue
                method = m.group(1).upper()
                add(
                    f"call:{method}:{m.group(3)}",
                    {
                        "kind": "call",
                        "method": method,
                        "path": m.group(3),
                        "source": _src(view, f, line),
                        "confidence": "resolved",
                    },
                )
        if not res.facts:
            res.empty_reason = "no routes or client calls found"
        return res


CREATE = re.compile(
    r"create\s+table\s+(?:if\s+not\s+exists\s+)?([\w.\"]+)\s*\((.*?)\)\s*;", re.I | re.S
)
ALTER_ADD = re.compile(
    r"alter\s+table\s+(?:if\s+exists\s+)?([\w.\"]+)\s+add\s+(?:column\s+)?"
    r"(?:if\s+not\s+exists\s+)?([\w\"]+)\s+([^,;]+)",
    re.I,
)
DROP = re.compile(r"drop\s+table\s+(?:if\s+exists\s+)?([\w.\"]+)", re.I)
INDEX = re.compile(
    r"create\s+(?:unique\s+)?index\s+(?:if\s+not\s+exists\s+)?([\w\"]+)\s+on\s+([\w.\"]+)"
    r"\s*\(([^)]*)\)",
    re.I,
)
DML = re.compile(r"^\s*(insert|update|delete|copy)\b", re.I | re.M)


def _u(s: str) -> str:
    return s.strip().strip('"').lower()


def _default_kind(spec: str) -> str | None:
    m = re.search(
        r"\bdefault\s+(.+?)(?:\s+(?:not\s+null|null|primary|references|unique|check)\b|$)",
        spec,
        re.I,
    )
    if not m:
        return None
    v = m.group(1).strip().lower()
    if v.startswith("nextval") or "serial" in spec.lower():
        return "sequence"
    if "(" in v:
        return "function"
    return "literal"


class SqlMigrations:
    name, version, section = "sql-migrations", "1.0.0", "db-schema"

    def __init__(self, globs: list[str] | None = None) -> None:
        self.globs = globs or ["**/migrations/**/*.sql", "**/migrations/*.sql"]

    def _files(self, view: RepoView) -> list[str]:
        out: set[str] = set()
        for g in self.globs:
            out.update(view.list_files(g))
        return sorted(out, key=lambda p: (posixpath.basename(p), p))

    def applies(self, view: RepoView) -> bool:
        return bool(self._files(view))

    def extract(self, view: RepoView) -> ExtractResult:
        res = ExtractResult()
        tables: dict[str, dict[str, Any]] = {}
        cols: dict[str, dict[str, Any]] = {}
        indexes: dict[str, dict[str, Any]] = {}
        dml_files = 0
        for f in self._files(view):
            text = view.read_text(f)
            if text is None:
                continue
            stem = posixpath.splitext(posixpath.basename(f))[0]
            res.facts.append(
                {
                    "id": f"migration:{stem}",
                    "kind": "migration",
                    "name": stem,
                    "source": _src(view, f),
                }
            )
            if DML.search(text):
                dml_files += 1
            clean = re.sub(r"--[^\n]*", "", text)
            for m in CREATE.finditer(clean):
                t = _u(m.group(1))
                line = _line(clean, m.start())
                tab: dict[str, Any] = {
                    "id": f"table:{t}",
                    "kind": "table",
                    "name": t,
                    "columns": [],
                    "primary_key": [],
                    "foreign_keys": [],
                    "source": _src(view, f, line),
                }
                for part in _split_cols(m.group(2)):
                    p = part.strip()
                    low = p.lower()
                    if low.startswith("primary key"):
                        tab["primary_key"] = [
                            _u(x) for x in re.findall(r"\(([^)]*)\)", p)[0].split(",")
                        ]
                        continue
                    if low.startswith(("foreign key", "constraint", "unique", "check")):
                        fk = re.search(
                            r"foreign\s+key\s*\(([^)]*)\)\s*references\s+([\w.\"]+)", p, re.I
                        )
                        if fk:
                            tab["foreign_keys"].append(
                                {
                                    "columns": [_u(x) for x in fk.group(1).split(",")],
                                    "references": f"table:{_u(fk.group(2))}",
                                }
                            )
                        continue
                    bits = p.split()
                    if len(bits) < 2:
                        continue
                    c = _u(bits[0])
                    cid = f"column:{t}.{c}"
                    tab["columns"].append(cid)
                    cols[cid] = {
                        "id": cid,
                        "kind": "column",
                        "table": f"table:{t}",
                        "name": c,
                        "type": bits[1].lower().rstrip(","),
                        "nullable": "not null" not in low and "primary key" not in low,
                        "default_kind": _default_kind(p),
                        "source": _src(view, f, line),
                    }
                    if "primary key" in low:
                        tab["primary_key"].append(c)
                    ref = re.search(r"references\s+([\w.\"]+)", p, re.I)
                    if ref:
                        tab["foreign_keys"].append(
                            {"columns": [c], "references": f"table:{_u(ref.group(1))}"}
                        )
                tables[t] = tab
            for m in ALTER_ADD.finditer(clean):
                t, c = _u(m.group(1)), _u(m.group(2))
                if t in tables:
                    cid = f"column:{t}.{c}"
                    if cid not in tables[t]["columns"]:
                        tables[t]["columns"].append(cid)
                    spec = m.group(3)
                    cols[cid] = {
                        "id": cid,
                        "kind": "column",
                        "table": f"table:{t}",
                        "name": c,
                        "type": spec.split()[0].lower(),
                        "nullable": "not null" not in spec.lower(),
                        "default_kind": _default_kind(spec),
                        "source": _src(view, f, _line(clean, m.start())),
                    }
            for m in INDEX.finditer(clean):
                n = _u(m.group(1))
                indexes[n] = {
                    "id": f"index:{n}",
                    "kind": "index",
                    "name": n,
                    "table": f"table:{_u(m.group(2))}",
                    "columns": [_u(x) for x in m.group(3).split(",")],
                    "source": _src(view, f, _line(clean, m.start())),
                }
            for m in DROP.finditer(clean):
                t = _u(m.group(1))
                tables.pop(t, None)
                for cid in [k for k in cols if k.startswith(f"column:{t}.")]:
                    cols.pop(cid)
        res.facts += list(tables.values()) + list(cols.values()) + list(indexes.values())
        if dml_files:
            res.unresolved.append(
                {
                    "source": _src(view, self._files(view)[0]),
                    "reason": f"DML skipped in {dml_files} file(s)",
                }
            )
        if not res.facts:
            res.empty_reason = "no migrations found"
        return res


def _split_cols(body: str) -> list[str]:
    out, depth, cur = [], 0, ""
    for ch in body:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            out.append(cur)
            cur = ""
        else:
            cur += ch
    if cur.strip():
        out.append(cur)
    return out


TEST_GLOBS = ["**/*.test.*", "**/*.spec.*", "**/__tests__/**"]
FRAMEWORKS = ["jest", "vitest", "mocha", "@playwright/test", "cypress"]
TITLE = re.compile(r"\b(describe|it|test)\(\s*(['\"])([^'\"]{1,200})\2")


class JsTestLayout:
    name, version, section = "js-test-layout", "1.0.0", "test-layout"

    def __init__(self, globs: list[str] | None = None) -> None:
        self.globs = globs or TEST_GLOBS

    def _tests(self, view: RepoView) -> list[str]:
        out: set[str] = set()
        for g in self.globs:
            out.update(view.list_files(g))
        return sorted(out)

    def applies(self, view: RepoView) -> bool:
        return True

    def extract(self, view: RepoView) -> ExtractResult:
        res = ExtractResult()
        mods = modules_of(view)
        fw_by_mod: dict[str, str] = {}
        for m in mods:
            pj = view.read_text("package.json" if m == "." else f"{m}/package.json")
            try:
                pkg = json.loads(pj or "{}")
            except ValueError:
                pkg = {}
            deps = {**(pkg.get("dependencies") or {}), **(pkg.get("devDependencies") or {})}
            fw_by_mod[m] = next((f for f in FRAMEWORKS if f in deps), "unknown")
        for f in self._tests(view):
            text = view.read_text(f) or ""
            mod = module_for(f, mods)
            fw = fw_by_mod.get(mod, "unknown")
            if "playwright" in f or "e2e" in f:
                fw = "@playwright/test" if fw == "unknown" else fw
            titles = [m.group(3) for m in TITLE.finditer(text)][:50]
            res.facts.append(
                {
                    "id": f"test:{view.repo}:{f}",
                    "kind": "test",
                    "module": f"module:{view.repo}:{mod}",
                    "framework": fw.removeprefix("@").split("/")[0],
                    "titles": titles,
                    "source": _src(view, f),
                }
            )
        if not res.facts:
            res.empty_reason = "no test files found"
        return res


def registry(
    migration_globs: list[str] | None = None, test_globs: list[str] | None = None
) -> list[Any]:
    return [
        RepoTree(),
        NpmManifests(),
        JsRoutes(),
        SqlMigrations(migration_globs),
        JsTestLayout(test_globs),
    ]
