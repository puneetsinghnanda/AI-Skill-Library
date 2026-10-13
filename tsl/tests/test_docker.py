"""Verifier containers (SDD-03 §5.5). Needs a running Docker daemon; skipped otherwise."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from tsl.harness.verifier import DockerVerifier, VerifierUnavailable


def _docker_up() -> bool:
    if shutil.which("docker") is None:
        return False
    try:
        return (
            subprocess.run(
                ["docker", "info"], capture_output=True, timeout=5, check=False
            ).returncode
            == 0
        )
    except (OSError, subprocess.TimeoutExpired):
        return False


needs_docker = [
    pytest.mark.docker,
    pytest.mark.skipif(not _docker_up(), reason="Docker daemon not available"),
]


@needs_docker[0]
@needs_docker[1]
def test_docker_verifier_is_available() -> None:
    assert DockerVerifier().available()


@needs_docker[0]
@needs_docker[1]
def test_unpinned_image_is_refused(tmp_path: Path) -> None:
    profile = {"id": "node-20@1", "image": "node:20", "steps": {}}
    with pytest.raises(VerifierUnavailable):
        DockerVerifier().run(profile, tmp_path, tmp_path / "out", with_coverage=False)


def test_unavailable_without_docker(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda name: None)
    assert DockerVerifier().available() is False
