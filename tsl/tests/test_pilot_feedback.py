"""Pilot feedback (HMS-4, HMS-6): step tools are refused before they run, failed checks go to
decide, the verifier sees only the change, and runs are easy to list."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from e2e_steps import SESSION, do_req_step, hook, next_action, start_run
from helpers import World
from tsl.core.clock import iso
from tsl.gitops.git import Git
from tsl.harness.commands import bash_allowed, is_read_only, strip_cd
from tsl.harness.verifier import DockerVerifier, export_source


# --------------------------------------------------------------------------- command shapes
def test_cd_prefix_is_stripped_before_matching() -> None:
    assert strip_cd("cd /c/x && tsl verify a.md") == "tsl verify a.md"
    assert strip_cd('cd "C:/a b"; cd y && tsl next r') == "tsl next r"
    assert bash_allowed("cd C:/Puneet/x; tsl verify a.md --json", ["Bash(tsl verify *)"])
    assert bash_allowed("cd x && PYTHONIOENCODING=utf-8 tsl next r", [])
    assert not bash_allowed("cd x && rm -rf y", ["Bash(tsl verify *)"])
    assert is_read_only("cd ../repo && cat a.txt")
    assert not is_read_only("cd ../repo && cat a.txt > b")


# --------------------------------------------------------------------------- pre-tool hook
def _pre(w: World, tool: str, tool_input: dict[str, Any]) -> dict[str, Any] | None:
    out, code = hook(w, "pre-tool", {"tool_name": tool, "tool_input": tool_input})
    assert code == 0
    return json.loads(out) if out else None


def _reason(res: dict[str, Any] | None) -> str:
    assert res is not None, "expected a deny"
    hso = res["hookSpecificOutput"]
    assert hso["permissionDecision"] == "deny"
    return str(hso["permissionDecisionReason"])


def _log(w: World, run_id: str) -> list[dict[str, Any]]:
    p = w.companion / "runs" / run_id / "tool-log.jsonl"
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()] if p.is_file() else []


def test_open_step_refuses_off_skill_tools_before_they_run(world: World) -> None:
    run_id = start_run(world)
    res = do_req_step(world, run_id, until="written")
    art = res["artifact"]
    assert "E-POL-06" in _reason(_pre(world, "WebFetch", {"url": "https://example.com"}))
    assert "PowerShell" in _reason(_pre(world, "PowerShell", {"command": "tsl next x"}))
    why = _reason(_pre(world, "Bash", {"command": "cat context/manifest.json"}))
    assert "Read, Grep or Glob" in why
    assert "only tsl commands" in _reason(_pre(world, "Bash", {"command": "docker info"}))
    # the skill's own tools and the run loop's tools still run
    cmd = f"cd {world.companion} && tsl verify {art} --json"
    assert _pre(world, "Bash", {"command": cmd}) is None
    assert _pre(world, "Read", {"file_path": str(world.companion / art)}) is None
    assert _pre(world, "Skill", {"skill": "truminds:review"}) is None
    targets = [e["target"] for e in _log(world, run_id)]
    assert not any("manifest" in t or "docker" in t for t in targets)
    assert f"tsl verify {art} --json"[:80] in targets  # logged without the cd prefix


def test_tools_are_not_step_limited_before_the_skill_launches(world: World) -> None:
    run_id = start_run(world)
    _c, env = next_action(world, run_id)
    assert env["data"]["action"] == "run_skill"
    assert _pre(world, "WebFetch", {"url": "https://example.com"}) is None


def test_mcp_tools_are_left_to_pre_mcp(world: World) -> None:
    run_id = start_run(world)
    do_req_step(world, run_id, until="written")
    assert _pre(world, "mcp__ccd_turn__update_plan", {}) is None


# --------------------------------------------------------------------------- stuck run
def test_failed_checks_go_to_decide_which_records_the_skipped_review(world: World) -> None:
    run_id = start_run(world)
    res = do_req_step(world, run_id, until="written")
    art = res["artifact"]
    line = {
        "ts": iso(world.clock()),
        "session_id": SESSION,
        "step": "req",
        "attempt": 1,
        "tool": "Bash",
        "target": "cat context/manifest.json",
        "decision": "allow",
        "code": None,
        "read_only": True,
    }
    with (world.companion / "runs" / run_id / "tool-log.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(line, sort_keys=True) + "\n")
    _code, env, _, _err = world.cli(["verify", art, "--json"], session=SESSION)
    assert env is not None and env["ok"] is False
    _c, nxt = next_action(world, run_id)
    assert nxt["data"]["action"] == "run_decide", nxt
    _code, dec, _, err = world.cli(["decide", art, "--json"], session=SESSION)
    assert dec is not None, err
    assert dec["data"]["outcome"] == "RETRY", dec
    review = json.loads((world.companion / art.replace(".md", ".review.json")).read_text())
    assert review["status"] == "could_not_review"
    assert "H7" in review["status_reason"]


# --------------------------------------------------------------------------- verifier
def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def test_export_source_leaves_out_ignored_files(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "node_modules" / "x").mkdir(parents=True)
    _git(repo, "init", "-q")
    (repo / ".gitignore").write_text("node_modules/\n.env\n")
    (repo / "src" / "a.ts").write_text("export const a = 1;\n")
    (repo / "node_modules" / "x" / "i.js").write_text("x")
    (repo / ".env").write_text("TOKEN=not-real\n")
    _git(repo, "add", ".gitignore", "src/a.ts")
    (repo / "src" / "new.ts").write_text("export const b = 2;\n")  # untracked, not ignored
    out = export_source(repo)
    try:
        names = sorted(p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file())
    finally:
        import shutil

        shutil.rmtree(out, ignore_errors=True)
    assert names == [".gitignore", "src/a.ts", "src/new.ts"]


def test_docker_probe_names_a_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def slow(cmd: list[str], **_kw: Any) -> Any:
        calls.append(cmd)
        raise subprocess.TimeoutExpired(cmd, 30)

    monkeypatch.setattr("shutil.which", lambda _n: "docker")
    monkeypatch.setattr("subprocess.run", slow)
    assert (
        DockerVerifier().probe() == f"docker info timed out after {DockerVerifier.INFO_TIMEOUT_S} s"
    )
    assert len(calls) == 2  # retried once
    monkeypatch.setattr("shutil.which", lambda _n: None)
    assert DockerVerifier().probe() == "docker not found on PATH"


# --------------------------------------------------------------------------- companion check
def test_records_are_working_files_until_decided(tmp_path: Path) -> None:
    from tsl.services.companion import _working_record

    repo = tmp_path / "c"
    d = repo / "artifacts" / "T-1" / "run_x"
    d.mkdir(parents=True)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")

    def commit(name: str, text: str) -> str:
        (d / name).write_text(text)
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", name)
        return Git(repo).out("rev-parse", "HEAD")

    class C:
        git = Git(repo)

    commit("req.checks.json", "1")
    c2 = commit("req.checks.json", "2")  # re-verified before decide: allowed
    assert _working_record(C(), c2, "artifacts/T-1/run_x/req.checks.json")  # type: ignore[arg-type]
    commit("req.verification.json", "v")
    c4 = commit("req.checks.json", "3")  # changed after decide: a finding
    assert not _working_record(C(), c4, "artifacts/T-1/run_x/req.checks.json")  # type: ignore[arg-type]
    assert not _working_record(C(), c4, "artifacts/T-1/run_x/req.verification.json")  # type: ignore[arg-type]


# --------------------------------------------------------------------------- state show
def test_state_show_lists_each_run(world: World) -> None:
    run_id = start_run(world)
    code, _env, out, err = world.cli(["state", "show"], session=SESSION)
    assert code == 0, err
    assert run_id in out and "RUNNING" in out and "--all" in out
