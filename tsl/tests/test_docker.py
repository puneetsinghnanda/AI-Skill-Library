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
        "-e VITEST_MAX_WORKERS=2",
        "-e VITEST_MAX_FORKS=2",
        "-e VITEST_MAX_THREADS=2",
        "-e VITEST_MIN_FORKS=1",
        "-e VITEST_MIN_THREADS=1",
        f"{tmp_path / 'wt'}:/src:ro",
    ):
        assert flag in joined, flag
    assert cmd[-3:] == ["sh", "-c", prof["steps"]["test"]["cmd"]]  # type: ignore[index]
    # prepare is the only step allowed to reach the package registry
    prep = " ".join(docker_command(prof, "prepare", tmp_path / "wt", tmp_path / "out"))
    assert "--network none" not in prep and ":/src:ro" in prep and "--cap-drop ALL" in prep
    # Workers follow the CPU limit through env vars; no CPU pinning (--cpuset-cpus).
    assert "--cpuset-cpus" not in joined and "--cpuset-cpus" not in prep


def test_worker_env_follows_the_cpu_limit() -> None:
    from tsl.harness.verifier import worker_env

    assert worker_env("2") == [
        "-e",
        "VITEST_MAX_WORKERS=2",  # vitest 4 and later read only this one
        "-e",
        "VITEST_MAX_FORKS=2",
        "-e",
        "VITEST_MAX_THREADS=2",
        "-e",
        "VITEST_MIN_FORKS=1",
        "-e",
        "VITEST_MIN_THREADS=1",
    ]
    half = worker_env("0.5")  # a fractional limit still gets one worker, on every vitest major
    assert "VITEST_MAX_WORKERS=1" in half and "VITEST_MAX_FORKS=1" in half


def test_placeholder_digest_is_refused() -> None:
    from tsl.harness.verifier import image_digest

    placeholder = dict(
        _profile(), image="ghcr.io/example-org/truminds/verifier-node-22@sha256:" + "0" * 64
    )
    with pytest.raises(VerifierUnavailable, match="placeholder"):
        image_digest(placeholder)
    # the repository profiles are pinned to published images (verifier README "Image digests")
    for pid in ("node-20@1", "node-22@1", "python-312@1"):
        digest = image_digest(_profile(pid))
        assert digest != "sha256:" + "0" * 64 and len(digest) == len("sha256:") + 64
    real = dict(
        _profile(), image="ghcr.io/example-org/truminds/verifier-node-22@sha256:" + "ab" * 32
    )
    assert image_digest(real) == "sha256:" + "ab" * 32


def test_repo_profiles_load_through_tsl() -> None:
    from tsl.schemas.registry import errors

    for d in sorted(p for p in PROFILES.iterdir() if p.is_dir()):
        assert errors("verifier-profile.v1", _profile(d.name)) == [], d.name


def _fake_docker(monkeypatch: pytest.MonkeyPatch, results: dict[str, object]) -> None:
    """Docker answers; each step's `docker run` returns results[step] (an int exit or 'timeout')."""
    monkeypatch.setattr(DockerVerifier, "available", lambda self: True)
    monkeypatch.setattr(DockerVerifier, "probe", lambda self: None)
    # On macOS the free-memory check runs sysctl/vm_stat through subprocess.run; keep it out of
    # the fake so only `docker run` calls take a step result.
    monkeypatch.setattr("tsl.harness.verifier.available_memory_mb", lambda: None)
    steps = list(results)

    def fake_run(cmd, **kw):  # type: ignore[no-untyped-def]
        step = steps.pop(0)
        r = results[step]
        if r == "timeout":
            raise subprocess.TimeoutExpired(cmd, 1, output=b"npm ERR! network", stderr=b"")
        return subprocess.CompletedProcess(cmd, int(r), b"npm ERR! network", b"")  # type: ignore[call-overload]

    monkeypatch.setattr(subprocess, "run", fake_run)


def _prep_profile() -> dict:  # type: ignore[type-arg]
    return {
        "id": "node-22@1",
        "image": "img@sha256:" + "1" * 64,
        "steps": {
            "prepare": {"cmd": "npm ci", "timeout_s": 600},
            "build": {"cmd": "b", "timeout_s": 9},
        },
    }


def test_prepare_timeout_is_not_reported_as_docker(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _fake_docker(monkeypatch, {"prepare": "timeout"})
    out = tmp_path / "a2"
    with pytest.raises(VerifierUnavailable) as ei:
        DockerVerifier().run(_prep_profile(), tmp_path, out, False)
    assert ei.value.code == "E-H3-08"
    assert "timed out after 600 s" in str(ei.value) and "prepare-a2.log" in str(ei.value)
    assert (out / "prepare-a2.log").exists()
    assert ei.value.data == {"timed_out": True, "exit_code": None}
    assert str(ei.value).startswith("prepare failed, log ") and len(str(ei.value)) < 300


def test_prepare_exit_code_and_per_attempt_logs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    for n in (1, 2):
        _fake_docker(monkeypatch, {"prepare": 1})
        with pytest.raises(VerifierUnavailable) as ei:
            DockerVerifier().run(_prep_profile(), tmp_path, tmp_path / f"a{n}", False)
        assert ei.value.code == "E-H3-08" and "exit 1" in str(ei.value)
    assert (tmp_path / "a1" / "prepare-a1.log").exists()
    assert (tmp_path / "a2" / "prepare-a2.log").exists()


def test_prepare_failure_with_docker_gone_is_e_h3_07(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _fake_docker(monkeypatch, {"prepare": 1})
    monkeypatch.setattr(DockerVerifier, "probe", lambda self: "docker not running")
    with pytest.raises(VerifierUnavailable) as ei:
        DockerVerifier().run(_prep_profile(), tmp_path, tmp_path / "a1", False)
    assert ei.value.code == "E-H3-07" and ei.value.data["exit_code"] == 1


def test_prepare_failure_with_slow_docker_stays_e_h3_08(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A `docker info` timeout right after a heavy install is inconclusive, not "Docker gone"."""
    _fake_docker(monkeypatch, {"prepare": 1})
    monkeypatch.setattr(DockerVerifier, "probe", lambda self: "docker info timed out after 30 s")
    with pytest.raises(VerifierUnavailable) as ei:
        DockerVerifier().run(_prep_profile(), tmp_path, tmp_path / "a1", False)
    assert ei.value.code == "E-H3-08"


def test_killed_step_reports_memory(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _fake_docker(monkeypatch, {"prepare": 0, "build": 137})
    with pytest.raises(VerifierUnavailable) as ei:
        DockerVerifier().run(_prep_profile(), tmp_path, tmp_path / "a1", False)
    assert ei.value.code == "E-H3-09" and "out of memory" in str(ei.value)


def test_low_memory_warning_threshold_and_top_users() -> None:
    from tsl.harness.verifier import low_memory_warning

    users = lambda: [("chrome", 3200), ("code", 1400), ("teams", 900)]  # noqa: E731
    assert low_memory_warning(None, users) is None
    assert low_memory_warning(8000, users) is None
    # Above ~1.5 GB free there is no warning: the verifier measured 0.55-0.89 GB at its peak.
    # The old threshold (4 GB limit + 1.5 GB) fired here, on most 16 GB laptops.
    assert low_memory_warning(3000, users) is None
    assert low_memory_warning(1536, users) is None
    w = low_memory_warning(1200, users)
    assert w and "1.2 GB free" in w and "about 1 GB" in w and "limit is 4 GB" in w
    assert "Top memory users: chrome 3.1 GB, code 1.4 GB, teams 900 MB." in w


def test_low_memory_warning_without_process_list() -> None:
    from tsl.harness.verifier import low_memory_warning

    w = low_memory_warning(1000, lambda: [])
    assert w and "Top memory users" not in w and "1.0 GB free" in w


def test_top_memory_users_parsers() -> None:
    from tsl.harness.verifier import _parse_ps, _parse_tasklist

    tasklist = (
        '"chrome.exe","101","Console","1","1,234,560 K"\n'
        '"chrome.exe","102","Console","1","1.000.000 K"\n'  # dotted thousands (other locales)
        '"vmmemWSL","200","Services","0","2 097 152 K"\n'
        '"bad row"\n'
    )
    assert _parse_tasklist(tasklist) == {"chrome": 2234560, "vmmemWSL": 2097152}
    ps = "  512000 /Applications/Code.app/Contents/MacOS/Electron\n 2048 /usr/bin/zsh\n 1024 /usr/bin/zsh\n"
    assert _parse_ps(ps) == {"Electron": 512000, "zsh": 3072}


def test_top_memory_users_reads_this_machine() -> None:
    from tsl.harness.verifier import top_memory_users

    top = top_memory_users()
    assert len(top) <= 3 and all(isinstance(n, str) and mb >= 0 for n, mb in top)
    assert [mb for _, mb in top] == sorted((mb for _, mb in top), reverse=True)


def test_available_memory_reads_or_returns_none() -> None:
    from tsl.harness.verifier import available_memory_mb

    m = available_memory_mb()
    assert m is None or m > 0


def test_low_memory_warns_but_does_not_block(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _fake_docker(monkeypatch, {"prepare": 0, "build": 0})
    monkeypatch.setattr("tsl.harness.verifier.available_memory_mb", lambda: 1000)
    monkeypatch.setattr("tsl.harness.verifier.top_memory_users", lambda: [("chrome", 3000)])
    v = DockerVerifier()
    res = v.run(_prep_profile(), tmp_path, tmp_path / "a1", False)
    err = capsys.readouterr().err
    assert res.passed and v.warnings and "Low memory" in err and "chrome 2.9 GB" in err
