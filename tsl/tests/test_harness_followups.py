"""Verifier step logs reach the retry; changes feedback carries the approver comment;
ci-verify binds earlier code steps to a commit on the way to the PR head."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from tsl.ci.verify import _tree_in_history
from tsl.gitops.git import Git
from tsl.harness import verifier as vmod
from tsl.harness.verify import _with_log
from tsl.schemas.registry import require_valid

PROFILE = {
    "id": "node-22@1",
    "image": "img@sha256:" + "1" * 64,
    "steps": {
        "prepare": {"cmd": "true", "timeout_s": 5},
        "test": {"cmd": "true", "timeout_s": 5},
        "secrets": {"cmd": "true", "timeout_s": 5},
    },
}


def _run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> vmod.VerifierResult:
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], **_: Any) -> Any:
        calls.append(cmd)
        if len(calls) == 1:  # prepare
            return subprocess.CompletedProcess(cmd, 0, b"", b"")
        return subprocess.CompletedProcess(cmd, 1, b"ok 1\nFAIL patients.test.ts\n", b"AKIA-x")

    monkeypatch.setattr(vmod.DockerVerifier, "available", lambda self: True)
    monkeypatch.setattr(subprocess, "run", fake_run)
    return vmod.DockerVerifier().run(PROFILE, tmp_path, tmp_path / "out", with_coverage=False)


def test_failed_step_keeps_its_log_and_secrets_keeps_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    res = _run(tmp_path, monkeypatch)
    test, secrets = res.steps
    assert test.status == "fail" and test.log == "test.log"
    assert b"FAIL patients.test.ts" in (tmp_path / "out/test.log").read_bytes()
    assert secrets.log is None and not (tmp_path / "out/secrets.log").exists()


def test_failure_detail_names_the_log_and_its_last_lines(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    res = _run(tmp_path, monkeypatch)
    detail = _with_log(res.steps[0], tmp_path / "out", "runs/r/verifier/impl")
    assert detail.startswith("test exit 1; log runs/r/verifier/impl/test.log: ")
    assert "FAIL patients.test.ts" in detail and len(detail) <= 500


def test_feedback_may_carry_the_approver_comment() -> None:
    fb = {
        "schema": "feedback.v1",
        "run_id": "run_01M5VBPY40KETZZR1EY7H5KK0V",
        "step": "ut",
        "from_attempt": 1,
        "kind": "rework",
        "gate_failures": [],
        "findings": [],
        "dropped": [],
        "must_resolve": [],
        "comment": "Add a test where every future appointment is Cancelled.",
    }
    require_valid("feedback.v1", fb, "feedback")


def test_earlier_code_step_tree_is_found_on_the_way_to_head(tmp_path: Path) -> None:
    g = Git(tmp_path)
    g.run("init", "-q")
    g.run("config", "user.email", "t@example.com")
    g.run("config", "user.name", "T")
    (tmp_path / "a.txt").write_text("base\n")
    g.run("add", "-A")
    g.run("commit", "-qm", "base")
    base = g.head()
    (tmp_path / "a.txt").write_text("impl\n")
    g.run("commit", "-qam", "impl")
    impl_tree = g.tree_of("HEAD")
    (tmp_path / "b.txt").write_text("ut\n")
    g.run("add", "-A")
    g.run("commit", "-qm", "ut")
    head = g.head()
    assert _tree_in_history(g, base, head, impl_tree)
    assert not _tree_in_history(g, base, head, g.tree_of(base))
