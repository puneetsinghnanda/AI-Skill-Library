"""H3 verifier containers behind an interface (SDD-03 §4.5, §5.5).

DockerVerifier runs each profile step in its own locked-down container.
Tests use a fake runner, and Docker-dependent tests skip when Docker is absent.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from tsl.core.jsonio import atomic_write, loads_strict

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
            if report and spec.get("parse") == "sarif" and (out_dir / report).exists():
                compact_sarif(out_dir / report)  # before the hash: the stored file is the one cited
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


def compact_sarif(path: Path) -> bool:
    """Keep only the rules a SARIF report's results use; True when the file was rewritten.

    Semgrep lists every rule of its ruleset in tool.driver.rules: in run HMS-28 that was 2.0 of
    the 2.4 MB of sast.sarif, for 4 results, and a reviewer's cite into it failed E-REV-05 "file
    too large" (citations.MAX_BYTES). Results are kept whole; ruleIndex and rule.index are
    renumbered to the kept list, and run.properties.truminds_rules_dropped says how many went.
    A rule stays when a result names it, or names a sub-rule of it ("js/xss" for
    "js/xss/reflected"). A run that points at rules any other way (rule.toolComponent into
    tool.extensions, rule.guid, notifications' associatedRule, ruleConfigurationOverrides, rule
    relationships or deprecated ids) is left whole, and so is a file that is not
    SARIF JSON or cannot be rewritten: the report is then hashed as the tool wrote it."""
    try:
        text = path.read_text(encoding="utf-8")
        # Strict: duplicate keys or NaN would come back changed, so such a file stays as written.
        doc = loads_strict(text)
    except (OSError, UnicodeDecodeError, ValueError):
        return False
    runs = doc.get("runs") if isinstance(doc, dict) else None
    changed = False
    for run in runs if isinstance(runs, list) else []:
        if _compact_run(run):
            changed = True
    if not changed:
        return False
    # Keep the tool's layout: an indented report stays citeable by line, a minified one stays
    # small. Written only when it is smaller than what the tool wrote.
    indented = text.count("\n") > 1
    out = json.dumps(doc, indent=2 if indented else None, ensure_ascii=False) + "\n"
    if len(out.encode("utf-8")) >= len(text.encode("utf-8")):
        return False
    try:
        atomic_write(path, out)
    except OSError:
        return False  # e.g. a report the container's user owns: keep it as the tool wrote it
    return True


def _compact_run(run: Any) -> bool:
    if not isinstance(run, dict):
        return False
    tool = run.get("tool")
    driver = tool.get("driver") if isinstance(tool, dict) else None
    if not isinstance(driver, dict) or not isinstance(driver.get("rules"), list):
        return False
    rules: list[Any] = driver["rules"]
    raw = run.get("results")
    if raw is not None and not isinstance(raw, list):
        return False
    results: list[dict[str, Any]] = [r for r in raw or [] if isinstance(r, dict)]
    # A result may also name its rule by reportingDescriptorReference (rule.id, rule.index).
    refs: list[dict[str, Any]] = []
    for r in results:
        ref = r.get("rule")
        refs.append(ref if isinstance(ref, dict) else {})
    # Other ways to point at a rule (SARIF 2.1.0): a result's rule.toolComponent (into
    # tool.extensions) or rule.guid, notifications' associatedRule, ruleConfigurationOverrides
    # in invocations, rules' relationships and deprecatedIds/deprecatedGuids. Dropping or
    # renumbering could break them. A notification's own "descriptor" names the notification
    # (Semgrep: "Syntax error"), not a rule, so it does not count.
    invocations = json.dumps(run.get("invocations", []))
    if (
        any("toolComponent" in f or "guid" in f for f in refs)
        or '"associatedRule"' in invocations
        or '"ruleConfigurationOverrides"' in invocations
        or any(
            isinstance(rule, dict)
            and ({"relationships", "deprecatedIds", "deprecatedGuids"} & rule.keys())
            for rule in rules
        )
    ):
        return False
    # Only string ids and integer indexes count: anything else names no rule (and a list or an
    # object in a set would raise).
    named = [r.get("ruleId") for r in results] + [f.get("id") for f in refs]
    ids = {x for x in named if isinstance(x, str) and x}
    pos = [r.get("ruleIndex") for r in results] + [f.get("index") for f in refs]
    idx = {x for x in pos if isinstance(x, int) and not isinstance(x, bool)}

    def used(i: int, rule: Any) -> bool:
        rid = rule.get("id") if isinstance(rule, dict) else None
        if i in idx:
            return True
        if not isinstance(rid, str):
            return False
        return rid in ids or any(x.startswith(rid + "/") for x in ids)

    keep = [i for i, rule in enumerate(rules) if used(i, rule)]
    if len(keep) == len(rules):
        return False
    new = {old: n for n, old in enumerate(keep)}
    for r, f in zip(results, refs, strict=True):
        if isinstance(r.get("ruleIndex"), int) and r["ruleIndex"] in new:
            r["ruleIndex"] = new[r["ruleIndex"]]
        if isinstance(f.get("index"), int) and f["index"] in new:
            f["index"] = new[f["index"]]
    driver["rules"] = [rules[i] for i in keep]
    props = run.setdefault("properties", {})
    if isinstance(props, dict):
        props["truminds_rules_dropped"] = len(rules) - len(keep)
    return True


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
