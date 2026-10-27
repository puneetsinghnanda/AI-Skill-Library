"""Code skills copy code[] from verify --inputs; downstream H5 accepts upstream trace ids;
the verifier skips coverage when the project has no coverage script."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from e2e_steps import SESSION, next_action, start_run
from helpers import World, ticket_snapshot
from tsl.core.hashing import sha256_bytes
from tsl.gitops.git import Git, worktree_tree
from tsl.harness import verifier as vmod
from tsl.harness.gates import GateResult, _code_matches, _foundation


def test_verify_inputs_envelope_carries_the_branch_diff_for_code_skills(world: World) -> None:
    run_id = start_run(world, "code-change", "ABC-151")
    _code, env = next_action(world, run_id)
    art = env["data"]["artifact_path"]
    (world.companion / f"artifacts/ABC-151/{run_id}").mkdir(parents=True, exist_ok=True)
    (world.companion / f"artifacts/ABC-151/{run_id}/ticket.md").write_text(
        ticket_snapshot(run_id, "ABC-151")
    )
    branch = json.loads((world.companion / f"runs/{run_id}/state.json").read_text())["branch"][
        "sample-orders"
    ]
    target = world.product / "api/src/routes/orders.js"
    target.write_text(target.read_text() + "// history: newest first\n")
    _, inp, _, _ = world.cli(["verify", art, "--inputs", "--json"], session=SESSION)
    assert inp is not None
    tree = worktree_tree(world.product)
    [code] = inp["data"]["envelope"]["code"]
    assert code["repo"] == "sample-orders" and code["base_sha"] == branch["base_sha"]
    assert code["head_sha"] == tree
    assert code["diff_sha256"] == sha256_bytes(
        Git(world.product).diff_bytes(branch["base_sha"], tree)
    )
    assert "api/src/routes/orders.js" in code["files"]


def _ci(tmp_path: Path, front: dict[str, Any], inputs: list[dict[str, Any]]) -> Any:
    return SimpleNamespace(
        art=SimpleNamespace(front=front), root=tmp_path, expected_inputs=inputs, state=None
    )


def test_foundation_takes_trace_ids_from_upstream_artifacts(tmp_path: Path) -> None:
    (tmp_path / "design.md").write_text("---\nschema: design.v1\ntrace: [REQ-1, REQ-2]\n---\n# D\n")
    ci = _ci(tmp_path, {}, [{"path": "design.md", "schema": "design.v1"}])
    assert {"REQ-1", "REQ-2"} <= _foundation(ci)
    ci = _ci(tmp_path, {}, [{"path": "design.md", "schema": None}])
    assert "REQ-1" not in _foundation(ci)


def test_foundation_accepts_the_run_ticket_id(tmp_path: Path) -> None:
    ci = _ci(tmp_path, {}, [])
    assert "HMS-2" not in _foundation(ci)
    ci.state = {"ticket": "HMS-2"}
    assert "HMS-2" in _foundation(ci)


def _code_ci(declared: list[dict[str, Any]]) -> Any:
    change = {"repo": "app", "diff_sha256": "a" * 64, "files": ["src/x.ts"]}
    return SimpleNamespace(
        skill=SimpleNamespace(is_code=True),
        product_changes=[change],
        art=SimpleNamespace(front={"code": declared}),
    )


def test_code_matches_the_measured_diff() -> None:
    good = [{"repo": "app", "diff_sha256": "a" * 64, "files": ["src/x.ts"]}]
    g = GateResult("H5")
    _code_matches(_code_ci(good), g)
    assert g.status != "fail"
    for bad in ([], [{"repo": "app", "diff_sha256": "b" * 64, "files": ["src/x.ts"]}]):
        g = GateResult("H5")
        _code_matches(_code_ci(bad), g)
        assert g.status == "fail" and "E-H5-03" in g.codes


@pytest.mark.parametrize(("exit_code", "status"), [(78, "skip"), (1, "fail"), (0, "pass")])
def test_coverage_step_exit_78_is_a_skip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, exit_code: int, status: str
) -> None:
    profile = {
        "id": "node-22@1",
        "image": "img@sha256:" + "1" * 64,
        "steps": {
            "prepare": {"cmd": "true", "timeout_s": 5},
            "coverage": {"cmd": "true", "timeout_s": 5},
        },
    }
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], **_: Any) -> Any:
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0 if len(calls) == 1 else exit_code)

    monkeypatch.setattr(vmod.DockerVerifier, "available", lambda self: True)
    monkeypatch.setattr(subprocess, "run", fake_run)
    res = vmod.DockerVerifier().run(profile, tmp_path, tmp_path / "out", with_coverage=True)
    assert [s.status for s in res.steps] == [status]


def test_lookup_paths_expand_run_and_ticket(tmp_path: Path) -> None:
    from tsl.harness.skillchecks import CheckEnv, _expand

    env = CheckEnv(
        front={"run_id": "run_X"},
        body="",
        root=tmp_path,
        input_paths=["context/conventions.md", "artifacts/HMS-1/run_X/impl.md"],
        input_texts={},
    )
    assert _expand(env, "artifacts/{ticket}/{run_id}/impl.checks.json") == (
        "artifacts/HMS-1/run_X/impl.checks.json"
    )
