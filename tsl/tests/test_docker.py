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


# --------------------------------------------------------------- no Docker needed (SDD-03 §5.5)
REPO = Path(__file__).resolve().parents[2]
PROFILES = REPO / "plugins" / "truminds" / "verifiers"


def _profile(pid: str = "node-22@1") -> dict[str, object]:
    from tsl.core.jsonio import read_yaml

    data = read_yaml(PROFILES / pid / "profile.yaml")
    assert isinstance(data, dict)
    return data


def test_step_command_is_locked_down(tmp_path: Path) -> None:
    from tsl.harness.verifier import docker_command

    prof = _profile()
    cmd = docker_command(prof, "test", tmp_path / "wt", tmp_path / "out")
    joined = " ".join(cmd)
    for flag in (
        "--network none",
        "--read-only",
        "--tmpfs /tmp",
        "--user 1000:1000",
        "--cap-drop ALL",
        "--security-opt no-new-privileges",
        "--cpus 2",
        "--memory 4g",
        "--pids-limit 512",
        f"{tmp_path / 'wt'}:/src:ro",
    ):
        assert flag in joined, flag
    assert cmd[-3:] == ["sh", "-c", prof["steps"]["test"]["cmd"]]  # type: ignore[index]
    # prepare is the only step allowed to reach the package registry
    prep = " ".join(docker_command(prof, "prepare", tmp_path / "wt", tmp_path / "out"))
    assert "--network none" not in prep and ":/src:ro" in prep and "--cap-drop ALL" in prep


def test_placeholder_digest_is_refused() -> None:
    from tsl.harness.verifier import image_digest

    for pid in ("node-20@1", "node-22@1", "python-312@1"):
        with pytest.raises(VerifierUnavailable, match="placeholder"):
            image_digest(_profile(pid))
    real = dict(
        _profile(), image="ghcr.io/example-org/truminds/verifier-node-22@sha256:" + "ab" * 32
    )
    assert image_digest(real) == "sha256:" + "ab" * 32


def test_repo_profiles_load_through_tsl() -> None:
    from tsl.schemas.registry import errors

    for d in sorted(p for p in PROFILES.iterdir() if p.is_dir()):
        assert errors("verifier-profile.v1", _profile(d.name)) == [], d.name
