"""Code step end to end: run branch, H3 through the verifier interface, PR, then tsl ci-verify."""

from __future__ import annotations

import json
from typing import Any

import yaml

from e2e_steps import SESSION, hook, next_action, start_run, write_artifact
from helpers import World, git, review_json, ticket_snapshot
from tsl.core.hashing import sha256_bytes
from tsl.gitops.git import Git, worktree_tree


def _code_run(world: World) -> tuple[str, dict[str, Any]]:
    run_id = start_run(world, "code-change", "ABC-150")
    _code, env = next_action(world, run_id)
    assert env["data"]["action"] == "run_skill", env
    art = env["data"]["artifact_path"]
    (world.companion / f"artifacts/ABC-150/{run_id}").mkdir(parents=True, exist_ok=True)
    (world.companion / f"artifacts/ABC-150/{run_id}/ticket.md").write_text(
        ticket_snapshot(run_id, "ABC-150")
    )
    state = json.loads((world.companion / f"runs/{run_id}/state.json").read_text())
    branch = state["branch"]["sample-orders"]
    assert git(world.product, "rev-parse", "--abbrev-ref", "HEAD") == branch["name"]
    # Claude edits product code (pre-tool hook allows product paths during a run)
    target = world.product / "api/src/routes/orders.js"
    out, _ = hook(
        world, "pre-tool", {"tool_name": "Edit", "tool_input": {"file_path": str(target)}}
    )
    assert out == ""
    target.write_text(target.read_text() + "// history: newest first\n")
    tree = worktree_tree(world.product)
    diff = sha256_bytes(Git(world.product).diff_bytes(branch["base_sha"], tree))
    _, inp, _, _ = world.cli(["verify", art, "--inputs", "--json"], session=SESSION)
    assert inp is not None
    fm = dict(inp["data"]["envelope"])
    fm.update(
        {
            "known": ["CH-1"],
            "assumed": [],
            "unknown": [],
            "summary": "Comment added",
        }
    )
    # code[] comes from the verify --inputs re-run after the edit (E-H5-03 otherwise)
    assert fm["code"][0]["head_sha"] == tree and fm["code"][0]["diff_sha256"] == diff
    body = "\n".join(
        f"## {s}\nCH-1 text.\n" for s in ("Summary", "Changes", "Known", "Assumed", "Unknown")
    )
    out, _ = write_artifact(
        world, art, "---\n" + yaml.safe_dump(fm, sort_keys=False) + "---\n\n" + body
    )
    assert out == "", out
    return run_id, {"artifact": art}


def test_code_step_pr_and_ci_verify(world: World) -> None:
    run_id, info = _code_run(world)
    art = info["artifact"]
    checks = json.loads((world.companion / art.replace(".md", ".checks.json")).read_text())
    assert next(g for g in checks["gates"] if g["id"] == "H3")["status"] == "pending"
    # review prepare and decide refuse while H3 is pending
    code, env, _, _ = world.cli(["review", "prepare", art, "--json"], session=SESSION)
    assert code == 3 and env is not None and env["code"] == "E-REV-01"
    code, env, _, err = world.cli(["verify", art, "--gates", "H3", "--json"], session=SESSION)
    assert code == 0, (env, err)
    assert world.verifier.calls == 1
    code, pkg, _, _ = world.cli(["review", "prepare", art, "--json"], session=SESSION)
    assert code == 0 and pkg is not None
    package = json.loads((world.companion / pkg["data"]["package_path"]).read_text())
    code, _, _, err = world.cli(
        ["review", "record", art, "--json"],
        session=SESSION,
        stdin=review_json(package, rubric_ids=["IM-R1"]),
    )
    assert code == 0, err
    code, dec, _, err = world.cli(["decide", art, "--json"], session=SESSION)
    assert code == 0, (dec, err)
    assert dec is not None and dec["data"]["outcome"] == "PASS"
    rec = json.loads((world.companion / dec["data"]["verification_path"]).read_text())
    assert rec["product_changes"][0]["repo"] == "sample-orders"
    code, nxt = next_action(world, run_id)
    assert nxt["data"]["action"] == "open_pr"
    code, prenv, _, err = world.cli(["pr", run_id, "--json"], session=SESSION)
    assert code == 0, (prenv, err)
    assert prenv is not None
    pr = prenv["data"]["prs"][0]
    assert pr["draft"] is False and pr["branch"].startswith("tsl/ABC-150-")
    created = world.github.created[0]
    assert f"<!-- tsl:run_id={run_id} -->" in created["body"]
    assert git(world.product_remote, "rev-parse", pr["branch"]) == pr["head_sha"]
    # CI re-check of the PR (no LLM; signatures through the registry fake)
    gpr = world.github.prs[("example-org/sample-orders", pr["number"])]
    gpr.head_sha = pr["head_sha"]
    gpr.changed_files = ["api/src/routes/orders.js"]
    args = [
        "ci-verify",
        "--pr",
        str(pr["number"]),
        "--repo",
        "example-org/sample-orders",
        "--companion",
        str(world.companion),
        "--product",
        str(world.product),
        "--json",
    ]
    code, cienv, _, err = world.cli(args)
    assert code == 0, (cienv, err)
    assert cienv is not None and cienv["data"]["result"] == "pass"
    assert cienv["data"]["steps"][0]["recheck"] == "same"
    # PR code differs from the verified change -> E-CI-04
    git(world.product, "checkout", "-q", pr["branch"])
    (world.product / "api/src/db.js").write_text("module.exports = { query: () => [1] };\n")
    git(world.product, "commit", "-qam", "human edit")
    gpr.head_sha = git(world.product, "rev-parse", "HEAD")
    code, cienv2, _, _ = world.cli(args)
    assert code == 2 and cienv2 is not None and "E-CI-04" in cienv2["data"]["codes"]
    gpr.head_sha = pr["head_sha"]
    # artifact edited after PASS -> E-CI-02
    p = world.companion / art
    p.write_text(p.read_text() + "\nedited\n")
    code, cienv3, _, _ = world.cli(args)
    assert code == 2 and cienv3 is not None and "E-CI-02" in cienv3["data"]["codes"]
    # registry unreachable -> fail closed
    world.insights.verify_unreachable = True
    code, cienv4, _, _ = world.cli(args)
    assert code == 2 and cienv4 is not None and cienv4["code"] == "E-CI-06"


def test_ci_verify_no_marker(world: World) -> None:
    from tsl.github.client import PullRequest

    world.github.prs[("example-org/sample-orders", 9)] = PullRequest(
        9, "u", False, "0" * 40, "no marker", ["api/src/app.js"]
    )
    args = [
        "ci-verify",
        "--pr",
        "9",
        "--repo",
        "example-org/sample-orders",
        "--companion",
        str(world.companion),
        "--json",
    ]
    code, env, _, _ = world.cli(args)
    assert code == 2 and env is not None and env["code"] == "E-CI-01"
    world.github.prs[("example-org/sample-orders", 9)].changed_files = ["docs/readme.md"]
    code, env, _, _ = world.cli(args)
    assert code == 0 and env is not None and env["data"]["result"] == "pass"


def test_h3_failure_retries_in_fix_loop(world: World) -> None:
    _run_id, info = _code_run(world)
    world.verifier.fail_step = "test"
    code, env, _, _ = world.cli(
        ["verify", info["artifact"], "--gates", "H3", "--json"], session=SESSION
    )
    assert code == 2 and env is not None and env["code"] == "E-CHK-01"
    h3 = next(g for g in env["data"]["gates"] if g["id"] == "H3")
    assert h3["codes"] == ["E-H3-02"]
    world.verifier.up = False
    code, env, _, _ = world.cli(
        ["verify", info["artifact"], "--gates", "H3", "--json"], session=SESSION
    )
    assert code == 3 and env is not None and env["code"] == "E-H3-07"
