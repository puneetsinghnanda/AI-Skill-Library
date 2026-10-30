"""H3 verifier containers behind an interface (SDD-03 §4.5, §5.5).

DockerVerifier runs each profile step in its own locked-down container.
Tests use a fake runner, and Docker-dependent tests skip when Docker is absent.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
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
    """Docker not running or image unavailable (E-H3-07)."""


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
        why = self.probe()
        if why is not None:
            raise VerifierUnavailable(why)
        from tsl.core.hashing import sha256_file

        digest = image_digest(profile)
        res = VerifierResult(str(profile["id"]), digest)
        steps: dict[str, Any] = profile["steps"]
        out_dir.mkdir(parents=True, exist_ok=True)
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
            log = _write_log(out_dir, name, *outs)
            report = spec.get("report")
            rsha = sha256_file(out_dir / report) if report and (out_dir / report).exists() else None
            if name == "prepare":
                if timed_out or code != 0:
                    raise VerifierUnavailable("prepare failed")
                continue
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


def _write_log(
    out_dir: Path, name: str, stdout: bytes | str | None, stderr: bytes | str | None
) -> str | None:
    """Keep the tail of a step's output as <name>.log so a retry can see why it failed."""
    if name in NO_LOG_STEPS:
        return None
    parts = [x.encode() if isinstance(x, str) else x for x in (stdout, stderr) if x]
    body = b"\n".join(parts)[-LOG_MAX_BYTES:]
    (out_dir / f"{name}.log").write_bytes(body)
    return f"{name}.log"


def log_tail(path: Path, max_chars: int) -> str:
    """Last lines of a step log, one line, at most max_chars."""
    try:
        text = path.read_bytes().decode("utf-8", "replace")
    except OSError:
        return ""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    tail = " | ".join(lines[-8:])
    return tail[-max_chars:]
