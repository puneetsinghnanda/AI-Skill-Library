"""Local checks for `tsl verify <artifact> --self-check --local` (roadmap A3).

A code step type-checks and lints the files it changed on the engineer's machine, as a developer
does before pushing, and fixes what that finds inside its attempt. HMS-24 impl and HMS-33 ut lost
verifier retries to a type error and a lint slip in code the step had just written. The verifier
(H3, Docker) stays the independent check, like CI; tests stay with unit-test and the verifier.

Per product repo the step changed, by the family of its verifier profile:

- node (node-20@1, node-22@1). Packages: `npm ci --ignore-scripts` when node_modules is missing or
  its packages differ from package-lock.json. Type check: `tsc --noEmit -p <tsconfig.json>` for
  the project of each changed TypeScript file. Lint: `eslint -f json <changed files>`.
- python (python-312@1). Packages: `uv sync --frozen` when .venv is missing or uv.lock changed
  since tsl last synced. Compile: `py_compile` on each changed .py file. Lint: `ruff check
  --output-format sarif <changed .py files>`.

Tools run from the repo's own install (node_modules, .venv) through `node` and `uv` on the PATH,
never through a project script, so a script line the model edited does not run.

Not run, and said so in data.local, when what runs locally could be the model's code: the step
changed a file that decides which packages install or how the linter loads (package.json, a
lock file, an ESLint config, pyproject.toml ...), or wrote into node_modules or .venv during the
run (the tool log shows it). The verifier still checks those changes in Docker.

Never raises: the caller turns an unexpected error into an `error` item."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

from tsl.core.hashing import sha256_file
from tsl.harness.verifier import error_lines_of, sarif_errors_of

TOOL_TIMEOUT_S = 300
INSTALL_TIMEOUT_S = 900
MAX_LINES = 20
TS_EXT = (".ts", ".tsx", ".mts", ".cts")
JS_EXT = (".js", ".jsx", ".mjs", ".cjs", *TS_EXT)
# Files that decide what runs locally: which packages install, how the linter loads its config.
CONTROL = {
    "node": re.compile(
        r"(^|/)(package\.json|package-lock\.json|npm-shrinkwrap\.json|\.npmrc|"
        r"eslint\.config\.[cm]?[jt]s|\.eslintrc(\.[a-z]+)?)$"
    ),
    "python": re.compile(
        r"(^|/)(pyproject\.toml|uv\.lock|setup\.py|setup\.cfg|requirements[^/]*\.txt|"
        r"ruff\.toml|\.ruff\.toml)$"
    ),
}
TSC_LINE = re.compile(
    r"^(?P<path>.+?)\((?P<line>\d+),(?P<col>\d+)\): error (?P<code>TS\d+): (?P<msg>.*)$"
)

Runner = Callable[[list[str], Path, int], tuple[int | None, str]]


def run_tool(cmd: list[str], cwd: Path, timeout: int) -> tuple[int | None, str]:
    """(exit code, stdout + stderr). None for a timeout or a program that could not start."""
    env = {**os.environ, "NO_COLOR": "1", "FORCE_COLOR": "0", "npm_config_update_notifier": "false"}
    try:
        p = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            timeout=timeout,
            check=False,
            env=env,
            stdin=subprocess.DEVNULL,
        )
    except subprocess.TimeoutExpired:
        return None, f"{PurePosixPath(cmd[0]).name} timed out after {timeout} s"
    except OSError as exc:
        return None, f"{PurePosixPath(cmd[0]).name} could not start: {exc}"
    out = (p.stdout or b"").decode("utf-8", "replace")
    err = (p.stderr or b"").decode("utf-8", "replace")
    return p.returncode, out + ("\n" + err if err else "")


@dataclass
class Result:
    """What one local check found, ready for data.local and data.fix."""

    repo: str
    name: str
    status: str  # pass | fail | skip
    detail: str = ""
    errors: list[str] = field(default_factory=list)  # "path:line:col code: message"
    mine: int = 0  # errors in files the step changed


def family(profile: str) -> str | None:
    head = profile.split("@", 1)[0]
    if head.startswith("node"):
        return "node"
    if head.startswith("python"):
        return "python"
    return None


def written_into_installs(tool_log: Path) -> str | None:
    """A Write or Edit of this run into node_modules or .venv, from the tool log, or None."""
    if not tool_log.is_file():
        return None
    for line in tool_log.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if not isinstance(e, dict) or e.get("tool") not in ("Write", "Edit", "NotebookEdit"):
            continue
        target = str(e.get("target") or "").replace("\\", "/")
        if "/node_modules/" in target or "/.venv/" in target:
            return target
    return None


def control_files(fam: str, files: list[str]) -> list[str]:
    rx = CONTROL.get(fam)
    return [f for f in files if rx and rx.search(f)]


def _ordered(errors: list[tuple[str, str]], files: set[str]) -> tuple[list[str], int]:
    """Error lines with those in the step's own files first; and how many those are."""
    mine = [line for path, line in errors if path in files]
    rest = [line for path, line in errors if path not in files]
    return list(dict.fromkeys(mine + rest)), len(dict.fromkeys(mine))


def fix_detail(r: Result) -> str:
    """data.fix detail: the repo, how many errors and where, then the error lines."""
    n = len(r.errors)
    where = (
        f"{r.mine} in files this step changed"
        if r.mine
        else "none in files this step changed; it may come from what they use, or the base may "
        "already fail: fix only what this step caused"
    )
    head = f"{r.repo}: {n} {r.name} error(s), {where}" if n else f"{r.repo}: {r.name} failed"
    shown = r.errors[:MAX_LINES]
    more = [f"... {n - MAX_LINES} more"] if n > MAX_LINES else []
    body = "\n".join(shown + more) if shown else r.detail
    return (head + (":\n" + body if body else ""))[:3000]


# --------------------------------------------------------------------------------- node
class Node:
    def __init__(self, repo: str, root: Path, files: list[str], run: Runner) -> None:
        self.repo, self.root, self.files, self.run = repo, root, files, run
        self.node = shutil.which("node")

    def install_reason(self) -> str | None:
        nm = self.root / "node_modules"
        hidden = nm / ".package-lock.json"
        if not nm.is_dir() or not hidden.is_file():
            return "node_modules is missing"
        lock = self.root / "package-lock.json"
        if not lock.is_file():
            return None
        try:
            want = json.loads(lock.read_text(encoding="utf-8")).get("packages") or {}
            have = json.loads(hidden.read_text(encoding="utf-8")).get("packages") or {}
        except ValueError:
            return "node_modules/.package-lock.json does not parse"
        diff = [
            k
            for k, v in want.items()
            if "node_modules/" in k
            and isinstance(v, dict)
            and not v.get("optional")
            and not v.get("link")
            and (have.get(k) or {}).get("version") != v.get("version")
        ]
        if diff:
            return f"{len(diff)} installed package(s) differ from package-lock.json ({diff[0]})"
        return None

    def install(self) -> tuple[str | None, str | None]:
        """(why it installed, why it could not). Installs only when install_reason says so."""
        why = self.install_reason()
        if why is None:
            return None, None
        if not (self.root / "package-lock.json").is_file():
            return why, "no package-lock.json to install from; install the packages first"
        npm = shutil.which("npm")
        if npm is None:
            return why, "npm is not on the PATH"
        code, out = self.run(
            [npm, "ci", "--ignore-scripts", "--no-audit", "--no-fund"], self.root, INSTALL_TIMEOUT_S
        )
        if code != 0:
            return why, "npm ci failed: " + (error_lines_of(out, 600, 6) or out.strip()[-600:])
        return why, None

    def typecheck(self) -> Result:
        r = Result(self.repo, "typecheck", "skip")
        tsc = self.root / "node_modules" / "typescript" / "bin" / "tsc"
        ts = [f for f in self.files if f.endswith(TS_EXT) and (self.root / f).is_file()]
        if not ts:
            r.detail = "no TypeScript file changed"
            return r
        if self.node is None or not tsc.is_file():
            r.detail = "node or typescript is not installed"
            return r
        projects = sorted({p for p in (self._tsconfig(f) for f in ts) if p})
        if not projects:
            r.detail = "no tsconfig.json for the changed files"
            return r
        errors: list[tuple[str, str]] = []
        loose: list[str] = []
        for proj in projects:
            code, out = self.run(
                [self.node, str(tsc), "--noEmit", "--pretty", "false", "-p", proj],
                self.root,
                TOOL_TIMEOUT_S,
            )
            if code is None:
                r.status, r.detail = "skip", out
                return r
            parsed = 0
            for line in out.splitlines():
                m = TSC_LINE.match(line.strip())
                if m:
                    path = m.group("path").replace("\\", "/")
                    errors.append(
                        (
                            path,
                            f"{path}:{m.group('line')}:{m.group('col')} {m.group('code')}: "
                            f"{m.group('msg')}",
                        )
                    )
                    parsed += 1
            if code != 0 and not parsed:  # tsconfig or option errors have no file position
                loose.append(f"{proj}: " + (error_lines_of(out, 800, 8) or out.strip()[-800:]))
        r.errors, r.mine = _ordered(errors, set(self.files))
        r.errors += loose
        r.status = "fail" if r.errors else "pass"
        return r

    def _tsconfig(self, rel: str) -> str | None:
        d = (self.root / rel).parent
        while True:
            if (d / "tsconfig.json").is_file():
                return (d / "tsconfig.json").relative_to(self.root).as_posix()
            if d == self.root or self.root not in d.parents:
                return None
            d = d.parent

    def lint(self) -> Result:
        r = Result(self.repo, "lint", "skip")
        eslint = self.root / "node_modules" / "eslint" / "bin" / "eslint.js"
        js = [f for f in self.files if f.endswith(JS_EXT) and (self.root / f).is_file()]
        if not js:
            r.detail = "no JavaScript or TypeScript file changed"
            return r
        if self.node is None or not eslint.is_file():
            r.detail = "node or eslint is not installed"
            return r
        errors: list[tuple[str, str]] = []
        for i in range(0, len(js), 100):
            code, out = self.run(
                [self.node, str(eslint), "-f", "json", *js[i : i + 100]], self.root, TOOL_TIMEOUT_S
            )
            parsed = eslint_errors(out, self.root)
            if parsed is None or code not in (0, 1):
                # ESLint itself failed (config, crash): not something the step's code caused.
                r.status = "skip"
                r.detail = "eslint did not run: " + (
                    error_lines_of(out, 600, 6) or out.strip()[-600:]
                )
                return r
            errors += parsed
        r.errors, r.mine = _ordered(errors, set(self.files))
        r.status = "fail" if r.errors else "pass"
        return r


def eslint_errors(out: str, root: Path) -> list[tuple[str, str]] | None:
    """(path, "path:line:col rule: message") for each error of `eslint -f json`; None when the
    output holds no JSON report (ESLint failed before linting)."""
    start = out.find("[")
    if start < 0:
        return None
    try:
        data, _ = json.JSONDecoder().raw_decode(out[start:])
    except ValueError:
        return None
    if not isinstance(data, list):
        return None
    found: list[tuple[str, str]] = []
    base = str(root).replace("\\", "/").rstrip("/") + "/"
    for f in data:
        if not isinstance(f, dict):
            continue
        path = str(f.get("filePath") or "").replace("\\", "/")
        if path.lower().startswith(base.lower()):
            path = path[len(base) :]
        for m in f.get("messages") or []:
            if isinstance(m, dict) and m.get("severity") == 2:
                msg = re.sub(r"\s+", " ", str(m.get("message") or "")).strip()[:200]
                rule = m.get("ruleId") or ("parse" if m.get("fatal") else "lint")
                found.append(
                    (path, f"{path}:{m.get('line', '?')}:{m.get('column', '?')} {rule}: {msg}")
                )
    return found


# ------------------------------------------------------------------------------- python
class Python:
    def __init__(self, repo: str, root: Path, files: list[str], run: Runner) -> None:
        self.repo, self.root, self.files, self.run = repo, root, files, run
        self.uv = shutil.which("uv")
        self.py = [f for f in files if f.endswith(".py") and (root / f).is_file()]

    def _stamp(self) -> Path:
        return self.root / ".venv" / ".tsl-uv-lock.sha256"

    def install_reason(self) -> str | None:
        lock = self.root / "uv.lock"
        if not lock.is_file():
            return None
        if not (self.root / ".venv").is_dir():
            return ".venv is missing"
        stamp = self._stamp()
        have = stamp.read_text(encoding="utf-8").strip() if stamp.is_file() else ""
        return None if have == sha256_file(lock) else "uv.lock changed since tsl last synced"

    def install(self) -> tuple[str | None, str | None]:
        why = self.install_reason()
        if why is None:
            return None, None
        if self.uv is None:
            return why, "uv is not on the PATH"
        code, out = self.run([self.uv, "sync", "--frozen"], self.root, INSTALL_TIMEOUT_S)
        if code != 0:
            return why, "uv sync failed: " + (error_lines_of(out, 600, 6) or out.strip()[-600:])
        self._stamp().write_text(sha256_file(self.root / "uv.lock") + "\n", encoding="utf-8")
        return why, None

    def _python(self) -> list[str] | None:
        venv_py = (
            self.root
            / ".venv"
            / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
        )
        if venv_py.is_file():
            return [str(venv_py)]
        return [self.uv, "run", "--frozen", "--offline", "--no-sync", "python"] if self.uv else None

    def typecheck(self) -> Result:
        r = Result(self.repo, "compile", "skip")
        if not self.py:
            r.detail = "no Python file changed"
            return r
        py = self._python()
        if py is None:
            r.detail = "no .venv and uv is not on the PATH"
            return r
        errors: list[tuple[str, str]] = []
        for f in self.py:  # one by one: py_compile stops at the first file that fails
            code, out = self.run([*py, "-m", "py_compile", f], self.root, TOOL_TIMEOUT_S)
            if code is None:
                r.detail = out
                return r
            if code != 0:
                errors.append((f, f"{f}: " + (error_lines_of(out, 400, 4) or out.strip()[-400:])))
        r.errors, r.mine = _ordered(errors, set(self.files))
        r.status = "fail" if r.errors else "pass"
        return r

    def lint(self) -> Result:
        r = Result(self.repo, "lint", "skip")
        if not self.py:
            r.detail = "no Python file changed"
            return r
        exe = "Scripts/ruff.exe" if sys.platform == "win32" else "bin/ruff"
        ruff = self.root / ".venv" / exe
        cmd = str(ruff) if ruff.is_file() else shutil.which("ruff")
        if cmd is None:
            r.detail = "ruff is not installed"
            return r
        code, out = self.run(
            [cmd, "check", "--output-format", "sarif", *self.py], self.root, TOOL_TIMEOUT_S
        )
        if code not in (0, 1):
            r.detail = "ruff did not run: " + (error_lines_of(out, 600, 6) or out.strip()[-600:])
            return r
        lines, mine, _total = sarif_errors_of(out, set(self.files), limit=1000, root=str(self.root))
        r.errors, r.mine = lines, mine
        r.status = "fail" if lines else "pass"
        return r


# --------------------------------------------------------------------------------- entry
def check_repos(
    repos: list[tuple[str, str | None, Path | None, list[str]]],
    tool_log: Path,
    run: Runner | None = None,
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    """Run the local checks for [(repo, verifier profile, clone, files the step changed)].

    Returns data.local and the data.fix items (kind `local`, id = check name)."""
    run = run or run_tool
    info: dict[str, Any] = {"status": "skip", "checks": [], "installed": [], "not_run": []}
    fix: list[dict[str, str]] = []
    wrote = written_into_installs(tool_log)
    if wrote:
        info["detail"] = (
            f"not run: this run wrote into an install folder ({wrote}), so local tools could run "
            "the model's code; the verifier checks the change in Docker"
        )
        return info, fix
    ran = failed = False
    for repo, profile, clone, files in repos:
        if not files:
            continue  # the step changed nothing in this repo
        fam = family(profile or "")
        if clone is None or fam is None:
            skipped = "no clone" if clone is None else "no local checks for its profile"
            info["not_run"].append({"repo": repo, "detail": skipped})
            continue
        ctl = control_files(fam, files)
        if ctl:
            info["not_run"].append(
                {
                    "repo": repo,
                    "detail": f"this step changed {', '.join(ctl[:3])}, which decides what runs "
                    "locally; the verifier checks it in Docker",
                }
            )
            continue
        checker: Node | Python = (Node if fam == "node" else Python)(repo, clone, files, run)
        why, cannot = checker.install()
        if why:
            info["installed"].append(
                {"repo": repo, "reason": why, **({"error": cannot} if cannot else {})}
            )
        if cannot:
            info["not_run"].append({"repo": repo, "detail": cannot})
            continue
        for res in (checker.typecheck(), checker.lint()):
            entry: dict[str, Any] = {"repo": repo, "name": res.name, "status": res.status}
            if res.status == "skip" and res.detail:
                entry["detail"] = res.detail
            if res.status == "fail":
                entry["errors"] = len(res.errors)
                failed = True
                fix.append({"kind": "local", "id": res.name, "detail": fix_detail(res)})
            if res.status != "skip":
                ran = True
            info["checks"].append(entry)
    info["status"] = "fail" if failed else "pass" if ran else "skip"
    if not info["installed"]:
        del info["installed"]
    if not info["not_run"]:
        del info["not_run"]
    return info, fix
