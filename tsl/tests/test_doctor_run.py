"""tsl doctor --run: live run-readiness checks that name the fix (hardening)."""

from __future__ import annotations

from typing import Any

import pytest

from helpers import World, git
from tsl.gitops.git import Git, GitError
from tsl.insights.client import HttpResult


def _run(world: World) -> tuple[int, dict[str, Any], dict[str, dict[str, str]]]:
    code, env, _, err = world.cli(["doctor", "--run", "--json"])
    assert env is not None, err
    return code, env, {c["id"]: c for c in env["data"]["checks"]}


def test_ready_laptop_passes_every_run_check(world: World) -> None:
    _, _, checks = _run(world)
    for cid in (
        "service-awake",
        "sign-in-live",
        "key-registered",
        "docker-running",
        "line-endings",
        "no-conflicts",
        "no-local-edits",
        "no-leftover-stash",
        "product-sample-orders",
        "pack-fresh",
    ):
        assert checks[cid]["status"] == "pass", checks[cid]


def test_refused_sign_in_says_log_in(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(world.insights, "get_me", lambda token: HttpResult(401, None))
    code, env, checks = _run(world)
    assert (
        checks["sign-in-live"]["status"] == "fail" and checks["sign-in-live"]["fix"] == "tsl login"
    )
    assert code == 3 and env["code"] == "E-ENV-01"


def test_docker_down_and_stale_product_clone_are_named(world: World) -> None:
    world.verifier.up = False
    (world.product / "NOTES.md").write_text("x\n")
    git(world.product, "add", "NOTES.md")
    git(world.product, "commit", "-qm", "ahead")
    git(world.product, "push", "-q", "origin", "main")
    git(world.product, "reset", "-q", "--hard", "HEAD~1")
    _, _, checks = _run(world)
    assert checks["docker-running"]["status"] == "fail"
    prod = checks["product-sample-orders"]
    assert prod["status"] == "fail" and "pull" in prod["fix"]


def test_conflicting_local_edit_is_explained(world: World) -> None:
    other = world.base / "companion-2"
    git(world.base, "clone", "-q", str(world.companion_remote), str(other))
    (other / "artifacts" / ".gitkeep").write_text("from GitHub\n")
    git(
        other,
        "-c",
        "user.name=Other",
        "-c",
        "user.email=other@example.test",
        "commit",
        "-qam",
        "remote edit",
    )
    git(other, "push", "-q", "origin", "main")
    (world.companion / "artifacts" / ".gitkeep").write_text("my hand edit\n")
    g = Git(world.companion)
    g.fetch()
    with pytest.raises(GitError) as exc:
        g.rebase("origin/main")
    err = exc.value.tsl()
    assert "conflict" in err.message and "git checkout HEAD -- artifacts/.gitkeep" in err.next
    _, _, checks = _run(world)
    assert checks["no-conflicts"]["status"] == "fail"
    assert checks["no-leftover-stash"]["status"] == "warn"


def test_human_output_lists_each_check(world: World) -> None:
    world.verifier.up = False
    _, _, out, _ = world.cli(["doctor", "--run"])
    assert "✖ docker-running" in out and "→ Start Docker Desktop" in out
