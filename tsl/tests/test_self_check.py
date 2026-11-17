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
    assert "change only what each item" in env["next"]


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
