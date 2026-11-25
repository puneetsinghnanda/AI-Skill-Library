"""H3 verifier containers behind an interface (SDD-03 §4.5, §5.5).

DockerVerifier runs each profile step in its own locked-down container.
Tests use a fake runner, and Docker-dependent tests skip when Docker is absent.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Collection
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

STEP_ORDER = ("build", "test", "lint", "sast", "secrets", "coverage")
SKIP_EXIT = 78  # EX_CONFIG: a profile step exits 78 when the project has nothing to run for it
LOG_MAX_BYTES = 200_000  # each step log keeps the last 200 kB of stdout and stderr
NO_LOG_STEPS = frozenset({"secrets"})  # its output can hold the secret it found
STEP_CODE = {
    "build": "E-H3-01",
    "test": "E-H3-02",
    "lint": "E-H3-03",
    "sast": "E-H3-04",
    "coverage": "E-H3-05",
}


class VerifierUnavailable(Exception):
    """The verifier could not run. E-H3-07 (Docker or image) unless `code` says otherwise.

    E-H3-08: dependency install (prepare) failed or timed out. E-H3-09: container out of memory.
    """

    def __init__(self, message: str, code: str = "E-H3-07", **fmt: Any) -> None:
        super().__init__(message)
        self.code = code
        self.data = fmt  # extra fields, e.g. timed_out and exit_code for E-H3-08


@dataclass
class StepResult:
    name: str
    status: str  # pass | fail | skip
    exit_code: int | None
    duration_ms: int
    report_sha256: str | None = None
    code: str | None = None
    detail: str = ""
    log: str | None = None  # file name of the step log in out_dir


@dataclass
class VerifierResult:
    profile: str
    image_digest: str
    steps: list[StepResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(s.status != "fail" for s in self.steps)


class VerifierRunner(Protocol):
    def available(self) -> bool: ...
    def run(
        self, profile: dict[str, Any], worktree: Path, out_dir: Path, with_coverage: bool
    ) -> VerifierResult: ...


PLACEHOLDER_DIGEST = "sha256:" + "0" * 64
LIMITS = {"cpus": "2", "memory": "4g", "pids": "512"}  # SDD-03 §5.5
# Warn below this much free memory. Measured on ONE small app: the HMS sample app (22 test files,
# 165 tests; docs/testing/validation/verifier-memory-HMS-11/). The highest verifier step peaked at
# 0.55-0.89 GB, well under the 4 GB limit, and the whole workflow (container, Claude Code, Docker
# daemon, a hook) at about 1.5 GB. A larger product repo may need much more: re-measure on one
# before relying on 1.5 GB and VERIFIER_NEEDS. The old threshold (limit + 1.5 GB = 5.5 GB) fired
# on most runs on a 16 GB laptop. The check runs once, before the first step (DockerVerifier.run):
# a drop during the run is not caught (HMS-15 went down to 0.68 GB free).
LOW_MEMORY_MB = 1536
VERIFIER_NEEDS = "about 1 GB"
TOP_USERS = 3
OOM_EXIT = 137  # 128 + SIGKILL: the kernel killed the container, usually for memory
RUN_USER = "1000:1000"  # SDD-03 §5.5; each verifier image has this uid


def image_digest(profile: dict[str, Any]) -> str:
    """Pinned digest of a profile image; a tag or the placeholder digest is refused (E-H3-07)."""
    image = str(profile["image"])
    if "@sha256:" not in image:
        raise VerifierUnavailable("image not pinned by digest")
    digest = "sha256:" + image.split("@sha256:", 1)[1]
    if digest == PLACEHOLDER_DIGEST:
        raise VerifierUnavailable(
            f"verifier image for {profile.get('id')} has the placeholder digest; "
            "set it from verifier-images.yml in a reviewed PR"
        )
    return digest


def docker_command(profile: dict[str, Any], step: str, worktree: Path, out_dir: Path) -> list[str]:
    """`docker run` for one profile step (SDD-03 §5.5; SEC-01 §5.5, §8.4 hardening flags).

    Every step but `prepare` has no network. The source is always mounted read-only; build
    output goes to /tmp (tmpfs), the cache volume or /out.
    """
    spec = profile["steps"][step]
    net = ["--network", "none"] if step != "prepare" else []
    return [
        "docker",
        "run",
        "--rm",
        *net,
        "--read-only",
        "--tmpfs",
        "/tmp",  # noqa: S108 - container tmpfs, not a host path
        "--user",
        RUN_USER,
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--cpus",
        LIMITS["cpus"],
        "--memory",
        LIMITS["memory"],
        "--pids-limit",
        LIMITS["pids"],
        *worker_env(LIMITS["cpus"]),
        "-v",
        f"{worktree}:{profile.get('workdir', '/src')}:ro",
        "-v",
        "tsl-verifier-cache:/cache",
        "-v",
        f"{out_dir}:/out",
        str(profile["image"]),
        "sh",
        "-c",
        str(spec["cmd"]),
    ]


def worker_env(cpus: str) -> list[str]:
    """`docker run -e` flags that size test-runner worker pools to the container's CPU limit.

    `--cpus` caps CPU time but not the core count Node reports (os.availableParallelism() sees
    every host core), so vitest started one worker per host core minus one: 7 on an 8-core
    laptop, each holding its own copy of the code under test. Measured on the HMS-11 code: test
    step 724-739 MB with 7 workers. Environment variables, not a `--maxWorkers` flag, because the
    profile runs `npm test`, which may fan out to workspaces where a flag would not reach vitest.
    Each vitest major reads its own names, and ignores the others:
    - vitest 2 and 3 read VITEST_MAX_FORKS / VITEST_MAX_THREADS (pool `forks` / `threads`); the
      minimum is set too, since it otherwise defaults to the host core count and would exceed
      the maximum. Checked in 2.1.9 and 3.2.7.
    - vitest 4 and later read only VITEST_MAX_WORKERS and have no minimum. Checked in 4.1.12
      and 5.1.1.
    """
    n = max(1, int(float(cpus)))
    env = {
        "VITEST_MAX_WORKERS": n,
        "VITEST_MAX_FORKS": n,
        "VITEST_MAX_THREADS": n,
        "VITEST_MIN_FORKS": 1,
        "VITEST_MIN_THREADS": 1,
    }
    return [x for k, v in env.items() for x in ("-e", f"{k}={v}")]


def available_memory_mb() -> int | None:
    """Free host memory in MB; None when it cannot be read (stdlib only, never raises)."""
    try:
        if sys.platform == "win32":
            import ctypes

            class _Mem(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            m = _Mem()
            m.dwLength = ctypes.sizeof(_Mem)
            if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):  # type: ignore[attr-defined,unused-ignore]
                return None
            return int(m.ullAvailPhys // (1024 * 1024))
        if sys.platform == "darwin":
            out = subprocess.run(
                ["sysctl", "-n", "hw.memsize"], capture_output=True, timeout=5, check=False
            ).stdout
            vm = subprocess.run(["vm_stat"], capture_output=True, timeout=5, check=False).stdout
            page = re.search(rb"page size of (\d+)", vm)
            free = sum(
                int(m.group(1))
                for m in re.finditer(rb"Pages (?:free|inactive|speculative):\s+(\d+)", vm)
            )
            if not out.strip() or not page:
                return None
            return int(free * int(page.group(1)) // (1024 * 1024))
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) // 1024
    except Exception:
        return None
    return None


def _parse_tasklist(text: str) -> dict[str, int]:
    """`tasklist /fo csv /nh` rows -> {image name: KB}.

    Mem Usage is locale-formatted ("1,234 K", "1.234 K", "1 234 K"), so only its digits are kept.
    """
    import csv

    out: dict[str, int] = {}
    for row in csv.reader(text.splitlines()):
        if len(row) < 5:
            continue
        digits = re.sub(r"\D", "", row[4])
        if digits:
            name = re.sub(r"\.exe$", "", row[0], flags=re.I)
            out[name] = out.get(name, 0) + int(digits)
    return out


def _parse_ps(text: str) -> dict[str, int]:
    """`ps -axo rss=,comm=` lines -> {command basename: KB}."""
    out: dict[str, int] = {}
    for line in text.splitlines():
        rss, _, comm = line.strip().partition(" ")
        if rss.isdigit() and comm.strip():
            name = comm.strip().rsplit("/", 1)[-1]
            out[name] = out.get(name, 0) + int(rss)
    return out


def _proc_rss() -> dict[str, int]:
    """Linux: {process name: KB} from /proc/<pid>/status."""
    out: dict[str, int] = {}
    for st in Path("/proc").glob("[0-9]*/status"):
        try:
            name, rss = "", 0
            for line in st.read_text().splitlines():
                if line.startswith("Name:"):
                    name = line.split(":", 1)[1].strip()
                elif line.startswith("VmRSS:"):
                    rss = int(line.split()[1])
        except (OSError, ValueError, IndexError):
            continue
        if name and rss:
            out[name] = out.get(name, 0) + rss
    return out


def top_memory_users(n: int = TOP_USERS) -> list[tuple[str, int]]:
    """The n process names using the most memory, as (name, MB), summed over each name's processes.

    Resident memory per process; shared pages count once per process, so a many-process app (a
    browser) reads a little high. Good enough to say what to close. Never raises; [] when unknown.
    """
    try:
        if sys.platform == "win32":
            text = subprocess.run(
                ["tasklist", "/fo", "csv", "/nh"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            ).stdout
            kb = _parse_tasklist(text)
        elif sys.platform == "darwin":
            text = subprocess.run(
                ["ps", "-axo", "rss=,comm="], capture_output=True, text=True, timeout=5, check=False
            ).stdout
            kb = _parse_ps(text)
        else:
            kb = _proc_rss()
    except Exception:
        return []
    top = sorted(kb.items(), key=lambda x: -x[1])[:n]
    return [(name, size // 1024) for name, size in top]


def _size(mb: int) -> str:
    return f"{mb / 1024:.1f} GB" if mb >= 1024 else f"{mb} MB"


def low_memory_warning(
    available_mb: int | None,
    users: Callable[[], list[tuple[str, int]]] | None = None,
) -> str | None:
    """A warning when free memory is below LOW_MEMORY_MB, naming the top memory users."""
    if available_mb is None or available_mb >= LOW_MEMORY_MB:
        return None
    top = (users or top_memory_users)()
    named = (
        " Top memory users: " + ", ".join(f"{name} {_size(mb)}" for name, mb in top) + "."
        if top
        else ""
    )
    return (
        f"Low memory: {available_mb / 1024:.1f} GB free; the verifier needs {VERIFIER_NEEDS} "
        f"(its limit is {LIMITS['memory'].upper().replace('G', ' GB')}).{named} "
        "Close some programs before the run, or the verifier may be killed for memory."
    )


def export_source(repo: Path) -> Path:
    """Copy the files git tracks or would track (not ignored ones) into a new temp folder.

    The scanners then see the change being verified, not node_modules, build output or a local
    .env. The caller deletes the folder.
    """
    out = Path(tempfile.mkdtemp(prefix="tsl-src-"))
    names = subprocess.run(
        ["git", "-C", str(repo), "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        capture_output=True,
        check=True,
    ).stdout.split(b"\0")
    for raw in names:
        if not raw:
            continue
        rel = raw.decode("utf-8", "surrogateescape")
        src = repo / rel
        if not src.is_file() and not src.is_symlink():
            continue  # tracked but deleted in the working copy
        dst = out / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst, follow_symlinks=False)
    return out


class DockerVerifier:
    """docker run --rm --network none --read-only ... per step (SDD-03 §5.5)."""

    # Docker Desktop on Windows (WSL 2) often takes 3-10 s to answer `docker info` after idle.
    INFO_TIMEOUT_S = int(os.environ.get("TSL_DOCKER_TIMEOUT_S", "30"))

    def __init__(self) -> None:
        self.warnings: list[str] = []

    def probe(self) -> str | None:
        """None when Docker answers; otherwise why it counts as unavailable."""
        if shutil.which("docker") is None:
            return "docker not found on PATH"
        why = "docker not running"
        for _ in range(2):
            try:
                r = subprocess.run(
                    ["docker", "info"],
                    capture_output=True,
                    timeout=self.INFO_TIMEOUT_S,
                    check=False,
                )
            except subprocess.TimeoutExpired:
                why = f"docker info timed out after {self.INFO_TIMEOUT_S} s"
                continue
            except OSError as exc:
                return f"docker could not start: {exc}"
            if r.returncode == 0:
                return None
            why = "docker not running"
        return why

    def available(self) -> bool:
        return self.probe() is None

    def run(
        self, profile: dict[str, Any], worktree: Path, out_dir: Path, with_coverage: bool
    ) -> VerifierResult:
        if not self.available():
            raise VerifierUnavailable(self.probe() or "docker not running")
        from tsl.core.hashing import sha256_file

        digest = image_digest(profile)
        res = VerifierResult(str(profile["id"]), digest)
        steps: dict[str, Any] = profile["steps"]
        out_dir.mkdir(parents=True, exist_ok=True)
        warn = low_memory_warning(available_memory_mb())
        if warn:
            self.warnings.append(warn)
            print(f"warning: {warn}", file=sys.stderr)
        names = ["prepare", *[s for s in STEP_ORDER if s in steps]]
        for name in names:
            if name == "coverage" and not with_coverage:
                continue
            spec = steps[name]
            cmd = docker_command(profile, name, worktree, out_dir)
            t0 = time.monotonic()
            try:
                p = subprocess.run(
                    cmd, capture_output=True, timeout=int(spec["timeout_s"]), check=False
                )
                code: int | None = p.returncode
                timed_out = False
                outs: tuple[bytes | None, bytes | None] = (p.stdout, p.stderr)
            except subprocess.TimeoutExpired as exc:
                code, timed_out = None, True
                outs = (exc.stdout, exc.stderr)
            ms = int((time.monotonic() - t0) * 1000)
            log = _write_log(out_dir, name, *outs, attempt=_attempt_of(out_dir))
            report = spec.get("report")
            rsha = sha256_file(out_dir / report) if report and (out_dir / report).exists() else None
            if name == "prepare":
                if timed_out or code != 0:
                    if code == OOM_EXIT:
                        raise _oom(name)
                    gone = self.probe()
                    # Docker stopped mid-prepare: that is E-H3-07, not an install failure. A slow
                    # `docker info` right after a heavy install is inconclusive: it stays E-H3-08.
                    if gone and "timed out" not in gone:
                        raise VerifierUnavailable(gone, timed_out=timed_out, exit_code=code)
                    why = (
                        f"timed out after {int(spec['timeout_s'])} s"
                        if timed_out
                        else f"exit {code}"
                    )
                    where = str(out_dir / log) if log else "none"
                    raise VerifierUnavailable(
                        f"prepare failed, log {where[-180:]}: {why}",
                        "E-H3-08",
                        timed_out=timed_out,
                        exit_code=code,
                    )
                continue
            if code == OOM_EXIT:
                raise _oom(name)
            if timed_out:
                res.steps.append(
                    StepResult(name, "fail", None, ms, rsha, "E-H3-06", f"{name} timed out", log)
                )
            elif code == 0:
                res.steps.append(StepResult(name, "pass", code, ms, rsha, log=log))
            elif code == SKIP_EXIT and name == "coverage":
                res.steps.append(
                    StepResult(
                        name, "skip", code, ms, rsha, None, "project has no coverage script", log
                    )
                )
            else:
                err = "E-SEC-01" if name == "secrets" else STEP_CODE.get(name, "E-H3-01")
                res.steps.append(
                    StepResult(name, "fail", code, ms, rsha, err, f"{name} exit {code}", log)
                )
        return res


def _oom(step: str) -> VerifierUnavailable:
    return VerifierUnavailable(
        f"verifier step {step} was killed (exit {OOM_EXIT}), most likely out of memory",
        "E-H3-09",
        step=step,
        limit=LIMITS["memory"],
    )


def _attempt_of(out_dir: Path) -> str | None:
    """'a2' from .../verifier/<step>/a2, so a retry keeps its own prepare log."""
    return out_dir.name if re.fullmatch(r"a\d+", out_dir.name) else None


def _write_log(
    out_dir: Path,
    name: str,
    stdout: bytes | str | None,
    stderr: bytes | str | None,
    attempt: str | None = None,
) -> str | None:
    """Keep the tail of a step's output as <name>.log so a retry can see why it failed."""
    if name in NO_LOG_STEPS:
        return None
    parts = [x.encode() if isinstance(x, str) else x for x in (stdout, stderr) if x]
    body = b"\n".join(parts)[-LOG_MAX_BYTES:]
    fname = f"{name}-{attempt}.log" if attempt and name == "prepare" else f"{name}.log"
    (out_dir / fname).write_bytes(body)
    return fname


def log_tail(path: Path, max_chars: int) -> str:
    """Last lines of a step log, one line, at most max_chars."""
    try:
        text = path.read_bytes().decode("utf-8", "replace")
    except OSError:
        return ""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    tail = " | ".join(lines[-8:])
    return tail[-max_chars:]


# Lines that say what broke, in the output of tsc, vite, vitest, jest, eslint, pytest and ruff.
# npm's own trailer ("npm error code 2", "npm error path ...") never says what broke, and in the
# HMS-24 impl build log it was all the old last-8-lines tail showed; the TS2741 line above it
# was the error.
_ERROR_LINE = re.compile(
    r"error TS\d+|^\s*FAIL\b|^\s*[×✗✕]\s|^\s*❯\s+\S+:\d+|"
    r"\b(?:Assertion|Type|Reference|Syntax|Range|Import|Module|Name|Attribute|Key|Value)?Error\b:|"
    r"^\s*(?:Test Files|Tests)\s.*\bfailed\b|^FAILED\s|^E\s{2,}\S|^\s*[-+] (?:Expected|Received)\b|"
    r"^\s*\d+:\d+\s+error\s|^\S+:\d+:\d+: [A-Z]+\d+|\berror during build\b|"
    r"\*\*\* Error compiling"
)
_NOISE = re.compile(r"^\s*npm (?:error|ERR!|warn|notice)\b", re.I)


def error_lines(path: Path, max_chars: int = 1500, max_lines: int = 15) -> str:
    """The lines of a step log that say what failed, in the order the log has them, one per
    line. Falls back to the log tail when no line looks like an error. Never raises."""
    try:
        text = path.read_bytes().decode("utf-8", "replace")
    except OSError:
        return ""
    return error_lines_of(text, max_chars, max_lines) or log_tail(path, max_chars)


def error_lines_of(text: str, max_chars: int = 1500, max_lines: int = 15) -> str:
    """error_lines over output text (a local tool's stdout and stderr); "" when nothing looks
    like an error."""
    lines = [ln.rstrip() for ln in text.splitlines() if ln.strip() and not _NOISE.search(ln)]
    hits = [ln.strip() for ln in lines if _ERROR_LINE.search(ln)]
    if not hits:
        hits = [ln.strip() for ln in lines if re.search(r"\berror\b", ln, re.I)]
    if not hits:
        return ""
    out: list[str] = []
    size = 0
    for ln in dict.fromkeys(hits):
        ln = ln[:300]
        if len(out) >= max_lines or size + len(ln) > max_chars:
            out.append(f"... {len(dict.fromkeys(hits)) - len(out)} more line(s) in the log")
            break
        out.append(ln)
        size += len(ln) + 1
    return "\n".join(out)


def _sarif_path(loc: dict[str, Any], bases: dict[str, Any], root: str = "") -> str:
    """Repo-relative path of a SARIF location: the verifier works on a copy in /cache/w (or
    /src); a local tool reports absolute paths under `root`."""
    from urllib.parse import unquote

    art = (loc.get("physicalLocation") or {}).get("artifactLocation") or {}
    uri = str(art.get("uri") or "")
    base = (bases.get(str(art.get("uriBaseId") or "")) or {}).get("uri") or ""
    if base and "://" not in uri and not uri.startswith("/"):
        uri = str(base).rstrip("/") + "/" + uri
    path = unquote(re.sub(r"^file://", "", uri)).replace("\\", "/")
    if re.match(r"^/[A-Za-z]:/", path):  # file:///C:/x on Windows
        path = path[1:]
    local = root.replace("\\", "/").rstrip("/") + "/" if root else ""
    if local and path.lower().startswith(local.lower()):
        return path[len(local) :]
    for base_dir in ("/cache/w/", "/src/"):
        if base_dir in path:
            return path.split(base_dir, 1)[1]
    while path.startswith("./"):
        path = path[2:]
    return path


def sarif_errors(
    path: Path, files: Collection[str] | None = None, limit: int = 20
) -> tuple[list[str], int, int]:
    """Results of a lint SARIF report that fail the step: level error and not suppressed in
    the source (eslint-disable). Each as "path:line:col rule: message".

    Returns (lines, errors in `files`, all errors). When `files` is given only results in those
    files are listed, unless none is, then the first of all results. Never raises."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return [], 0, 0
    return sarif_errors_of(text, files, limit)


def sarif_errors_of(
    text: str, files: Collection[str] | None = None, limit: int = 20, root: str = ""
) -> tuple[list[str], int, int]:
    """sarif_errors over SARIF text (a local `ruff check --output-format sarif`), paths made
    relative to `root`."""
    import json

    try:
        data = json.loads(text)
    except ValueError:
        return [], 0, 0
    if not isinstance(data, dict):
        return [], 0, 0
    found: list[tuple[str, str]] = []
    for run in data.get("runs") or []:
        bases = run.get("originalUriBaseIds") or {}
        for r in run.get("results") or []:
            if r.get("suppressions") or str(r.get("level") or "warning") != "error":
                continue
            locs = r.get("locations") or [{}]
            where = _sarif_path(locs[0], bases, root)
            reg = (locs[0].get("physicalLocation") or {}).get("region") or {}
            pos = f"{where}:{reg.get('startLine', '?')}:{reg.get('startColumn', '?')}"
            msg = re.sub(r"\s+", " ", str((r.get("message") or {}).get("text") or "")).strip()
            found.append((where, f"{pos} {r.get('ruleId') or 'lint'}: {msg[:200]}"))
    every = [line for _, line in found]
    mine = [line for where, line in found if files is not None and where in files]
    shown = every if files is None else (mine or every)
    return shown[:limit], len(mine), len(found)
