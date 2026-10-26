"""H3 verifier containers behind an interface (SDD-03 §4.5, §5.5).

DockerVerifier runs each profile step in its own locked-down container.
Tests use a fake runner, and Docker-dependent tests skip when Docker is absent.
"""

from __future__ import annotations

import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

STEP_ORDER = ("build", "test", "lint", "sast", "secrets", "coverage")
SKIP_EXIT = 78  # EX_CONFIG: a profile step exits 78 when the project has nothing to run for it
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


class DockerVerifier:
    """docker run --rm --network none --read-only ... per step (SDD-03 §5.5)."""

    def available(self) -> bool:
        if shutil.which("docker") is None:
            return False
        try:
            r = subprocess.run(["docker", "info"], capture_output=True, timeout=3, check=False)
        except (OSError, subprocess.TimeoutExpired):
            return False
        return r.returncode == 0

    def run(
        self, profile: dict[str, Any], worktree: Path, out_dir: Path, with_coverage: bool
    ) -> VerifierResult:
        if not self.available():
            raise VerifierUnavailable("docker not running")
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
            except subprocess.TimeoutExpired:
                code, timed_out = None, True
            ms = int((time.monotonic() - t0) * 1000)
            report = spec.get("report")
            rsha = sha256_file(out_dir / report) if report and (out_dir / report).exists() else None
            if name == "prepare":
                if timed_out or code != 0:
                    raise VerifierUnavailable("prepare failed")
                continue
            if timed_out:
                res.steps.append(
                    StepResult(name, "fail", None, ms, rsha, "E-H3-06", f"{name} timed out")
                )
            elif code == 0:
                res.steps.append(StepResult(name, "pass", code, ms, rsha))
            elif code == SKIP_EXIT and name == "coverage":
                res.steps.append(
                    StepResult(name, "skip", code, ms, rsha, None, "project has no coverage script")
                )
            else:
                err = "E-SEC-01" if name == "secrets" else STEP_CODE.get(name, "E-H3-01")
                res.steps.append(
                    StepResult(name, "fail", code, ms, rsha, err, f"{name} exit {code}")
                )
        return res
