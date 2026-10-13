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

        image = str(profile["image"])
        if "@sha256:" not in image:
            raise VerifierUnavailable("image not pinned by digest")
        digest = "sha256:" + image.split("@sha256:", 1)[1]
        res = VerifierResult(str(profile["id"]), digest)
        steps: dict[str, Any] = profile["steps"]
        out_dir.mkdir(parents=True, exist_ok=True)
        names = ["prepare", *[s for s in STEP_ORDER if s in steps]]
        for name in names:
            if name == "coverage" and not with_coverage:
                continue
            spec = steps[name]
            net = ["--network", "none"] if name != "prepare" else []
            src_mode = "ro"  # the source is always mounted read-only (SDD-03 §5.5)
            cmd = [
                "docker",
                "run",
                "--rm",
                *net,
                "--read-only",
                "--tmpfs",
                "/tmp",  # noqa: S108 - container tmpfs, not a host path
                "--user",
                "1000:1000",
                "--cpus",
                "2",
                "--memory",
                "4g",
                "--pids-limit",
                "512",
                "-v",
                f"{worktree}:{profile.get('workdir', '/src')}:{src_mode}",
                "-v",
                "tsl-verifier-cache:/cache",
                "-v",
                f"{out_dir}:/out",
                image,
                "sh",
                "-c",
                str(spec["cmd"]),
            ]
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
            else:
                err = "E-SEC-01" if name == "secrets" else STEP_CODE.get(name, "E-H3-01")
                res.steps.append(
                    StepResult(name, "fail", code, ms, rsha, err, f"{name} exit {code}")
                )
        return res
