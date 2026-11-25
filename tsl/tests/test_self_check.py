"""tsl verify <artifact> --self-check and the post-write soft-check warning (roadmap item 2).

A skill runs the self-check once after writing, fixes only what it lists with targeted edits, then
hands over. It is a preliminary check: it never fails the command, every problem is an item. HMS-9 requirement-review went to band Low on S2 alone (RR-C12: summary over 5 sentences),
which nothing reported before the review."""

from __future__ import annotations

import json
from typing import Any

import yaml

from e2e_steps import SESSION, next_action, start_run, write_artifact
from helpers import World, intent_artifact, ticket_snapshot
from test_e2e_code import _code_run
from tsl.core.frontmatter import split

LONG_SUMMARY = " ".join(f"Sentence {i} about order history." for i in range(1, 8))


def _write(world: World, run_id: str, **variant: Any) -> tuple[str, str, int]:
    """Write a requirement-review artifact; returns its path and the post-write hook output."""
    code, env = next_action(world, run_id)
    assert code == 0 and env["data"]["action"] == "run_skill", env
    art = env["data"]["artifact_path"]
    ticket_rel = f"artifacts/ABC-142/{run_id}/ticket.md"
    tp = world.companion / ticket_rel
    tp.parent.mkdir(parents=True, exist_ok=True)
    tp.write_text(ticket_snapshot(run_id), encoding="utf-8")
    code, inp, _, err = world.cli(["verify", art, "--inputs", "--json"], session=SESSION)
    assert code == 0 and inp is not None, err
    drop = variant.pop("drop_section", None)
    extra = {k: variant.pop(k) for k in ("known_value",) if k in variant}
    text = intent_artifact(inp["data"]["envelope"], ticket_rel, drop_section=drop, **extra)
    if variant.get("long_summary"):
        text = text.replace("The ticket asks for order history on the order page.", LONG_SUMMARY)
    if variant.get("weak_claim"):
        text = text.replace("kept `24 hours`", "kept `48 hours`")
    out, hcode = write_artifact(world, art, text)
    return art, out, hcode


def _self_check(world: World, art: str) -> dict[str, Any]:
    code, env, _, err = world.cli(["verify", art, "--self-check", "--json"], session=SESSION)
    assert code == 0 and env is not None, err  # never a failed command: the list is the answer
    return env


def test_clean_artifact_has_nothing_to_fix(world: World) -> None:
    art, out, _ = _write(world, start_run(world))
    assert out == "", out
    env = _self_check(world, art)
    assert env["message"] == "Self-check clean"
    assert env["data"] == {"artifact": art, "ok": True, "fix": [], "check": []}


def test_soft_check_and_weak_claim_are_listed_and_warned(world: World) -> None:
    art, out, hcode = _write(world, start_run(world), long_summary=True, weak_claim=True)
    assert hcode == 0
    ctx = json.loads(out)["hookSpecificOutput"]["additionalContext"]
    assert "Soft checks that fail: RR-C12: summary longer than 5 sentences" in ctx, ctx
    assert "Claims that will not verify: C1:" in ctx, ctx
    env = _self_check(world, art)
    fix = {(f["kind"], f["id"]): f["detail"] for f in env["data"]["fix"]}
    assert env["data"]["ok"] is False
    assert set(fix) == {("soft", "RR-C12"), ("claim", "C1")}, fix
    assert fix[("soft", "RR-C12")] == "summary longer than 5 sentences"
    assert fix[("claim", "C1")].startswith("element absent: `48 hours`")
    assert "edit only what each item" in env["next"]


def test_hard_gate_failure_is_listed_not_raised(world: World) -> None:
    art, out, _ = _write(world, start_run(world), drop_section="Known")
    assert json.loads(out)["decision"] == "block", out
    env = _self_check(world, art)
    gates = [f for f in env["data"]["fix"] if f["kind"] == "gate"]
    assert gates and all(f["detail"] for f in gates), env["data"]


def test_abort_code_is_listed_not_raised(world: World) -> None:
    canary = "AKIA" + "Z" * 16  # generated at run time, never committed (TC-SEC-004)
    art, out, _ = _write(world, start_run(world), known_value=f"newest first {canary}")
    assert json.loads(out)["reason"].startswith("E-SEC-01"), out
    env = _self_check(world, art)
    assert env["data"]["ok"] is False
    assert any(f["kind"] == "gate" and f["id"] == "H4" for f in env["data"]["fix"]), env["data"]


def test_code_skill_claim_on_uncommitted_lines_is_not_listed(world: World) -> None:
    """A code skill's claim on a line it added (not yet committed) resolves against the step's
    working tree, as at decide, so neither the self-check nor the hook lists it."""
    _run_id, info = _code_run(world)
    art = info["artifact"]
    lines = (world.product / "api/src/routes/orders.js").read_text().split("\n")
    n = next(i for i, x in enumerate(lines, 1) if "history: newest first" in x)
    p = world.companion / art
    doc = split(p.read_text(encoding="utf-8"))
    fm = dict(doc.front)
    fm["claims"] = [
        {
            "id": "C1",
            "text": "The route notes `history: newest first`",
            "cites": [f"sample-orders:api/src/routes/orders.js#L{n}"],
        }
    ]
    out, _ = write_artifact(
        world, art, "---\n" + yaml.safe_dump(fm, sort_keys=False) + "---\n\n" + doc.body
    )
    assert "Claims that will not verify" not in out, out
    env = _self_check(world, art)
    assert not [f for f in env["data"]["fix"] if f["kind"] == "claim"], env["data"]


def test_self_check_without_artifact_is_a_usage_error(world: World) -> None:
    code, env, _, _ = world.cli(["verify", "--self-check", "--json"], session=SESSION)
    assert code != 0 and env is not None and env["code"] == "E-USE-01", env


def test_any_other_error_is_listed_not_raised(world: World) -> None:
    art, _, _ = _write(world, start_run(world))
    env = _self_check(world, art.replace(".md", "-missing.md"))
    assert env["data"]["ok"] is False
    assert [f["kind"] for f in env["data"]["fix"]] == ["error"], env["data"]
    assert env["data"]["fix"][0]["id"].startswith("E-"), env["data"]


# --------------------------------------------------------------- content (roadmap A3)
def _to_split(world: World, known_value: str) -> tuple[str, str, dict[str, Any]]:
    """A run at the story-split step, the intent's REQ-1 saying `known_value`."""
    from e2e_steps import do_req_step
    from helpers import git

    run_id = start_run(world)
    assert do_req_step(world, run_id, variant={"known_value": known_value})["code"] == 0
    code, env = next_action(world, run_id)
    assert code == 4 and env["data"]["action"] == "pause_approval", env
    appr = world.companion / f"runs/{run_id}/approvals.md"
    appr.write_text(
        appr.read_text().replace(
            "decision:          # approve | reject | changes | abort", "decision: approve"
        )
    )
    git(world.companion, "commit", "-qam", "approve G-req")
    git(world.companion, "push", "-q", "origin", "main")
    code, _, _, err = world.cli(["gate", run_id, "approve", "--gate", "G-req", "--json"], user="tl")
    assert code == 0, err
    world.sync_companion()
    code, _, _, err = world.cli(["state", "resume", run_id, "--json"], session=SESSION)
    assert code == 0, err
    _, env = next_action(world, run_id)
    assert env["data"]["step"] == "split", env
    art = env["data"]["artifact_path"]
    _, inp, _, _ = world.cli(["verify", art, "--inputs", "--json"], session=SESSION)
    assert inp is not None
    return run_id, art, dict(inp["data"]["envelope"])


def test_story_split_content_items_come_back_as_checks(world: World) -> None:
    """A story that seeds one status for a REQ that counts by status, an order rule checked
    with no second candidate: data.check names both; data.fix stays empty (ok stays true)."""
    _run_id, art, fm = _to_split(
        world, "newest first, counted per status (Status is OPEN, SHIPPED or CANCELLED)"
    )
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
                            "text": "Given a customer with OPEN orders when they open the "
                            "order page then they see newest first",
                        }
                    ],
                }
            ],
        }
    )
    body = "\n".join(f"## {s}\nS-1 text.\n" for s in ("Stories", "Known", "Assumed", "Unknown"))
    out, _ = write_artifact(
        world, art, "---\n" + yaml.safe_dump(fm, sort_keys=False) + "---\n\n" + body
    )
    assert out == "", out  # the post-write hook does not run content checks
    env = _self_check(world, art)
    data = env["data"]
    assert data["ok"] is True and data["fix"] == [], data
    by_id = {c["id"]: c["detail"] for c in data["check"]}
    assert "SHIPPED, CANCELLED have none" in by_id["S-1"], by_id
    assert 'order ("newest")' in by_id["REQ-1"] and 'count ("counted")' in by_id["REQ-1"]
    assert env["message"].startswith("Self-check: nothing to fix; 2 content question(s)")
    assert "answer each item in data.check" in env["next"]
    assert "content_error" not in data


# -------------------------------------------------------- Docker test (roadmap A3)
TS_LOG = """> @hms/api@0.1.0 build
> tsc -p tsconfig.build.json

src/repositories/patientRepo.ts(159,5): error TS2741: Property 'visitSummary' is missing.
vite v5.4.21 building for production...
npm error Lifecycle script `build` failed with error:
npm error code 2
npm error command sh -c tsc -p tsconfig.build.json
"""


def _sarif(*results: tuple[str, str, bool]) -> dict[str, Any]:
    return {
        "runs": [
            {
                "results": [
                    {
                        "level": level,
                        "message": {"text": f"problem in {uri}"},
                        "ruleId": "no-unused-vars",
                        "locations": [
                            {
                                "physicalLocation": {
                                    "artifactLocation": {"uri": f"file:///cache/w/{uri}"},
                                    "region": {"startLine": 3, "startColumn": 7},
                                }
                            }
                        ],
                        **({"suppressions": [{"kind": "inSource"}]} if suppressed else {}),
                    }
                    for uri, level, suppressed in results
                ]
            }
        ]
    }


def _verifier_check(world: World, art: str) -> dict[str, Any]:
    code, env, _, err = world.cli(
        ["verify", art, "--self-check", "--verifier", "--json"], session=SESSION
    )
    assert code == 0 and env is not None, err
    return env


def _state(world: World, run_id: str) -> dict[str, Any]:
    state: dict[str, Any] = json.loads((world.companion / f"runs/{run_id}/state.json").read_text())
    return state


def test_docker_test_failure_is_a_fix_item_with_the_error_line(world: World) -> None:
    """HMS-24 impl a1: a build error the old log tail hid behind npm's trailer. The self-check
    names the TS error, runs only build, test and lint, and uses no attempt or budget."""
    run_id, info = _code_run(world)
    art = info["artifact"]
    before = _state(world, run_id)
    world.verifier.fail_step = "build"
    world.verifier.fail_log = TS_LOG
    env = _verifier_check(world, art)
    data = env["data"]
    assert world.verifier.steps_asked == [("build", "test", "lint")]
    item = next(f for f in data["fix"] if f["kind"] == "verifier")
    assert item["id"] == "build"
    assert "error TS2741" in item["detail"] and "npm error" not in item["detail"]
    assert (
        f"runs/{run_id}/verifier/" in item["detail"] and "/self-check/build.log" in item["detail"]
    )
    assert data["ok"] is False
    assert data["verifier"]["status"] == "fail" and data["verifier"]["runs"] == 1
    assert "Docker test failed (run 1 of 3)" in env["message"]
    assert "run the self-check with --verifier again" in env["next"]
    after = _state(world, run_id)
    assert after["steps"] == before["steps"]  # no attempt, no budget, no cursor change
    checks = json.loads((world.companion / art.replace(".md", ".checks.json")).read_text())
    assert next(g for g in checks["gates"] if g["id"] == "H3")["status"] == "pending"


def test_docker_test_lint_lists_the_changes_errors_from_sarif(world: World) -> None:
    """HMS-33 ut a2: lint failed with an empty lint.log. The SARIF errors in the files the step
    changed are listed; suppressed results and warnings are not."""
    _run_id, info = _code_run(world)
    world.verifier.fail_step = "lint"
    world.verifier.sarif = _sarif(
        ("api/src/routes/orders.js", "error", False),
        ("api/src/other.js", "error", False),
        ("api/src/routes/orders.js", "warning", False),
        ("api/src/routes/orders.js", "error", True),
    )
    item = next(
        f
        for f in _verifier_check(world, info["artifact"])["data"]["fix"]
        if f["kind"] == "verifier"
    )
    assert item["id"] == "lint"
    assert "1 of 2 lint error(s) are in files this step changed" in item["detail"]
    assert "api/src/routes/orders.js:3:7 no-unused-vars" in item["detail"]
    assert "api/src/other.js" not in item["detail"]


def test_docker_test_pass_and_the_per_attempt_limit(world: World) -> None:
    _run_id, info = _code_run(world)
    art = info["artifact"]
    for n in (1, 2, 3):
        env = _verifier_check(world, art)
        assert env["data"]["verifier"]["status"] == "pass", env
        assert env["data"]["verifier"]["runs"] == n
    assert env["message"] == "Self-check clean; Docker test passed (run 3 of 3)"
    env = _verifier_check(world, art)
    assert world.verifier.calls == 3
    assert env["data"]["verifier"]["status"] == "limit" and env["data"]["ok"] is True
    assert "Docker test not run: the Docker test already ran 3 times" in env["message"]


def test_docker_unavailable_is_not_an_item_to_fix(world: World) -> None:
    _run_id, info = _code_run(world)
    world.verifier.up = False
    env = _verifier_check(world, info["artifact"])
    assert env["data"]["ok"] is True
    assert env["data"]["verifier"]["status"] == "unavailable"
    assert env["data"]["verifier"]["code"] == "E-H3-07"
    assert "Docker test not run: docker not running" in env["message"]


def test_docker_test_runs_before_the_artifact_is_written(world: World) -> None:
    """The code skill runs the Docker test first, then copies code[] and writes the artifact:
    no artifact yet is not an error with --verifier."""
    run_id, info = _code_run(world)
    p = world.companion / info["artifact"]
    p.unlink()
    for side in (".checks.json",):
        q = world.companion / info["artifact"].replace(".md", side)
        if q.exists():
            q.unlink()
    env = _verifier_check(world, info["artifact"])
    assert env["data"]["fix"] == [] and env["data"]["check"] == []
    assert env["data"]["verifier"]["status"] == "pass"
    assert not p.exists()
    assert _state(world, run_id)["status"] == "RUNNING"


def test_docker_test_skips_a_step_that_changes_no_code(world: World) -> None:
    art, _, _ = _write(world, start_run(world))
    env = _verifier_check(world, art)
    assert env["data"]["verifier"]["status"] == "skip" and world.verifier.calls == 0
    assert env["data"]["ok"] is True


def test_verifier_flag_needs_self_check(world: World) -> None:
    art, _, _ = _write(world, start_run(world))
    code, env, _, _ = world.cli(["verify", art, "--verifier", "--json"], session=SESSION)
    assert code != 0 and env is not None and env["code"] == "E-USE-01", env


def test_docker_test_never_reports_a_stale_sarif(world: World) -> None:
    """Run 1 fails lint with a SARIF report; run 2 fails lint without writing one (eslint
    crashed): run 2 must not show run 1's errors."""
    _run_id, info = _code_run(world)
    world.verifier.fail_step = "lint"
    world.verifier.sarif = _sarif(("api/src/routes/orders.js", "error", False))
    first = _verifier_check(world, info["artifact"])["data"]["fix"]
    assert any("orders.js:3:7" in f["detail"] for f in first)
    world.verifier.sarif = None
    world.verifier.fail_log = "Oops! Something went wrong! :(\nESLint: 9.1.0\nTypeError: bad config"
    second = _verifier_check(world, info["artifact"])["data"]["fix"]
    item = next(f for f in second if f["kind"] == "verifier")
    assert "orders.js:3:7" not in item["detail"] and "TypeError: bad config" in item["detail"]
