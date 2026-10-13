"""End-to-end simulated run: requirement-review -> decide on a temp companion repo (TC-E2E-001 shape)."""

from __future__ import annotations

import json

from e2e_steps import SESSION, do_req_step, next_action, start_run, write_artifact
from helpers import World, git
from tsl.schemas.registry import errors


def test_requirement_review_to_decide_pass(world: World) -> None:
    run_id = start_run(world)
    res = do_req_step(world, run_id)
    env = res["env"]
    assert res["code"] == 0, env
    assert env["data"]["outcome"] == "PASS"
    assert env["data"]["band"] == "High"
    vpath = world.companion / env["data"]["verification_path"]
    rec = json.loads(vpath.read_text())
    assert errors("verification.v1", rec) == []
    assert rec["signals"]["S1"] == 1.0 and rec["signals"]["S5"] == "fresh"
    state = json.loads((world.companion / f"runs/{run_id}/state.json").read_text())
    assert errors("run-state.v1", state) == []
    assert state["steps"][0]["status"] == "DONE"
    # the decide commit was pushed to the companion remote
    assert "decide req a1" in git(world.companion_remote, "log", "--oneline", "main")


def test_full_run_gate_story_and_completion(world: World) -> None:
    run_id = start_run(world)
    assert do_req_step(world, run_id)["code"] == 0
    code, env = next_action(world, run_id)
    assert code == 4 and env["code"] == "E-RUN-02" and env["data"]["action"] == "pause_approval"
    appr = world.companion / f"runs/{run_id}/approvals.md"
    text = appr.read_text().replace(
        "decision:          # approve | reject | changes | abort", "decision: approve"
    )
    appr.write_text(text)
    git(world.companion, "commit", "-qam", "approve G-req")
    git(world.companion, "push", "-q", "origin", "main")
    # the run owner may not approve their own step
    code, env2, _, _ = world.cli(["approve", run_id, "G-req", "--json"], user="eng")
    assert code == 3 and env2 is not None and env2["code"] == "E-AUTH-05"
    code, env3, _, err = world.cli(["approve", run_id, "G-req", "--json"], user="tl")
    assert code == 0, (env3, err)
    world.sync_companion()
    code, env4, _, err = world.cli(["state", "resume", run_id, "--json"], session=SESSION)
    assert code == 0, (env4, err)
    assert env4 is not None and env4["data"]["status"] == "RUNNING"
    code, env5 = next_action(world, run_id)
    assert env5["data"]["action"] == "run_skill" and env5["data"]["step"] == "split"
    assert env5["data"]["inputs"][0]["schema"] == "intent.v1"
    art = env5["data"]["artifact_path"]
    _, inp, _, _ = world.cli(["verify", art, "--inputs", "--json"], session=SESSION)
    assert inp is not None
    fm = dict(inp["data"]["envelope"])
    fm.update(
        {
            "trace": ["REQ-1"],
            "known": ["S-1"],
            "assumed": [],
            "unknown": [],
            "stories": [
                {
                    "id": "S-1",
                    "title": "See order history",
                    "trace": ["REQ-1"],
                    "acceptance_criteria": [
                        {
                            "id": "AC1",
                            "text": "Given a customer with orders when "
                            "they open the order page then they see newest first",
                        }
                    ],
                }
            ],
        }
    )
    import yaml

    body = "\n".join(f"## {s}\nS-1 text.\n" for s in ("Stories", "Known", "Assumed", "Unknown"))
    out, _ = write_artifact(
        world, art, "---\n" + yaml.safe_dump(fm, sort_keys=False) + "---\n\n" + body
    )
    assert out == "", out
    _, pkg, _, _ = world.cli(["review", "prepare", art, "--json"], session=SESSION)
    assert pkg is not None
    package = json.loads((world.companion / pkg["data"]["package_path"]).read_text())
    from helpers import review_json

    code, _, _, err = world.cli(
        ["review", "record", art, "--json"],
        session=SESSION,
        stdin=review_json(package, rubric_ids=["SS-R1", "SS-R2"]),
    )
    assert code == 0, err
    code, dec, _, err = world.cli(["decide", art, "--json"], session=SESSION)
    assert code == 0, (dec, err)
    code, env6 = next_action(world, run_id)
    assert env6["data"]["action"] == "open_pr"
    code, env7, _, err = world.cli(["pr", run_id, "--json"], session=SESSION)
    assert code == 0, (env7, err)
    assert (
        env7 is not None and env7["data"]["prs"] == []
    )  # no code changed: run completes without a PR
    code, env8 = next_action(world, run_id)
    assert env8["data"]["action"] == "done"
    assert not (world.companion / "runs/active/ABC-142__brownfield-change.lock").exists()
