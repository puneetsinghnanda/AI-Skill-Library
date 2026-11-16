"""tsl verify <artifact> --self-check and the post-write soft-check warning (roadmap item 2).

A skill runs the self-check once after writing, fixes what it lists in one rewrite, then hands
over. HMS-9 requirement-review went to band Low on S2 alone (RR-C12: summary over 5 sentences),
which nothing reported before the review."""

from __future__ import annotations

import json
from typing import Any

from e2e_steps import SESSION, next_action, start_run, write_artifact
from helpers import World, intent_artifact, ticket_snapshot

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
    text = intent_artifact(inp["data"]["envelope"], ticket_rel, drop_section=drop)
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
    assert env["data"] == {"artifact": art, "ok": True, "fix": []}


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
    assert "in one rewrite" in env["next"]


def test_hard_gate_failure_is_listed_not_raised(world: World) -> None:
    art, out, _ = _write(world, start_run(world), drop_section="Known")
    assert json.loads(out)["decision"] == "block", out
    env = _self_check(world, art)
    gates = [f for f in env["data"]["fix"] if f["kind"] == "gate"]
    assert gates and all(f["detail"] for f in gates), env["data"]
