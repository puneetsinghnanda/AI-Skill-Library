"""tsl next in code mode (next-action.v2): the loop runs checks, review record and decide."""

from __future__ import annotations

import json
from typing import Any

from e2e_steps import SESSION, next_action, start_run, write_artifact
from helpers import World, intent_artifact, review_json, ticket_snapshot
from tsl.core.clock import iso
from tsl.core.config import ORG_DEFAULTS
from tsl.orchestrator.loop import FIX_ROUNDS

LONG_SUMMARY = " ".join(f"Sentence {i} about order history." for i in range(1, 8))
MAJOR = {
    "id": "F-1",
    "severity": "major",
    "category": "completeness",
    "text": "Retention rule is not listed as a requirement",
    "cites": [
        {
            "ref": "context/intent-baseline.md#data-retention",
            "quote": "Order events are kept 24 hours",
        }
    ],
}


def _json(w: World, rel: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((w.companion / rel).read_text(encoding="utf-8"))
    return data


def _state(w: World, run_id: str) -> dict[str, Any]:
    return _json(w, f"runs/{run_id}/state.json")


def _start(w: World, loop: str = "code") -> str:
    code, env, _, err = w.cli(
        ["state", "start", "brownfield-change", "ABC-142", "--loop", loop, "--json"],
        session=SESSION,
    )
    assert code == 0 and env is not None, (env, err)
    return str(env["data"]["run_id"])


def _nxt(w: World, run_id: str) -> dict[str, Any]:
    code, env = next_action(w, run_id)
    assert code == 0, env
    return dict(env["data"])


def _review_record(w: World, art: str) -> dict[str, Any]:
    """The recorded review of attempt 1: still beside the artifact, or archived by a retry."""
    cur = art.replace(".md", ".review.json")
    if (w.companion / cur).is_file():
        return _json(w, cur)
    base, _, name = art.rpartition("/")
    return _json(w, f"{base}/history/{name[:-3]}/a1/{name[:-3]}.review.json")


def _write_req(w: World, run_id: str, art: str, **variant: Any) -> None:
    ticket_rel = f"artifacts/ABC-142/{run_id}/ticket.md"
    tp = w.companion / ticket_rel
    tp.parent.mkdir(parents=True, exist_ok=True)
    if not tp.exists():
        tp.write_text(ticket_snapshot(run_id), encoding="utf-8")
    code, inp, _, err = w.cli(["verify", art, "--inputs", "--json"], session=SESSION)
    assert code == 0 and inp is not None, err
    long_summary = variant.pop("long_summary", False)
    text = intent_artifact(inp["data"]["envelope"], ticket_rel, **variant)
    if long_summary:
        text = text.replace("The ticket asks for order history on the order page.", LONG_SUMMARY)
    write_artifact(w, art, text)


def _review(w: World, d: dict[str, Any], **kw: Any) -> None:
    pkg = _json(w, d["review"]["package_path"])
    (w.companion / d["review"]["write_to"]).parent.mkdir(parents=True, exist_ok=True)
    (w.companion / d["review"]["write_to"]).write_text(review_json(pkg, **kw), encoding="utf-8")


def _to_reviewer(w: World, run_id: str, **variant: Any) -> dict[str, Any]:
    d = _nxt(w, run_id)
    assert d["action"] == "run_step", d
    _write_req(w, run_id, d["artifact_path"], **variant)
    r = _nxt(w, run_id)
    assert r["action"] == "run_reviewer", r
    return r


# 1: state start
def test_start_loop_code_stores_run_loop_and_driver(world: World) -> None:
    st = _state(world, _start(world, "code"))
    assert st["run_loop"] == "code" and st["driver"] == "skill"


def test_start_loop_model_and_default_from_user_config(world: World) -> None:
    assert _state(world, _start(world, "model"))["run_loop"] == "model"
    run_id = start_run(world, ticket="ABC-143")  # no --loop: the test user config says model
    assert _state(world, run_id)["run_loop"] == "model"


def test_start_loop_bogus_is_usage_error(world: World) -> None:
    code, env, _, _ = world.cli(
        ["state", "start", "brownfield-change", "ABC-142", "--loop", "bogus", "--json"],
        session=SESSION,
    )
    assert code != 0 and env is not None and env["code"] == "E-USE-01"


# 2, 3, 10: first next, idempotency, current_action
def test_first_next_is_run_step_v2_with_instruction_file(world: World) -> None:
    run_id = _start(world)
    d = _nxt(world, run_id)
    assert d["schema"] == "next-action.v2" and d["action"] == "run_step"
    assert d["run_id"] == run_id and d["step"] == "req" and d["attempt"] == 1
    assert d["instruction_path"] == f"runs/{run_id}/instructions/req.a1.json"
    assert _json(world, d["instruction_path"]) == d
    assert d["allowed_tools"] and d["retry"] is None and d["say"]


def test_next_is_idempotent(world: World) -> None:
    run_id = _start(world)
    first = _nxt(world, run_id)
    rev = _state(world, run_id)["rev"]
    assert _nxt(world, run_id) == first
    assert _state(world, run_id)["rev"] == rev


def test_next_idempotent_at_reviewer(world: World) -> None:
    run_id = _start(world)
    r = _to_reviewer(world, run_id)
    rev = _state(world, run_id)["rev"]
    assert _nxt(world, run_id) == r
    assert _state(world, run_id)["rev"] == rev


def test_current_action_is_recorded(world: World) -> None:
    run_id = _start(world)
    assert not _state(world, run_id).get("current_action")
    _nxt(world, run_id)
    cur = _state(world, run_id)["current_action"]
    assert (cur["action"], cur["step"], cur["attempt"], cur["driver"]) == (
        "run_step",
        "req",
        1,
        "skill",
    )
    _to_reviewer(world, run_id)
    cur = _state(world, run_id)["current_action"]
    assert (cur["action"], cur["step"], cur["attempt"]) == ("run_reviewer", "req", 1)


# 4: fix rounds
def test_self_check_failure_gives_fix_then_full_checks_after_rounds(world: World) -> None:
    run_id = _start(world)
    d = _nxt(world, run_id)
    art = d["artifact_path"]
    _write_req(world, run_id, art, long_summary=True)
    f1 = _nxt(world, run_id)
    assert f1["action"] == "fix" and f1["fix"], f1
    assert _nxt(world, run_id)["fix"] == f1["fix"]  # unchanged: same fix, no new round
    p = world.companion / art
    for i in range(FIX_ROUNDS - 1):  # still failing after an edit: one more round each
        p.write_text(p.read_text(encoding="utf-8") + f"\nedit {i}\n", encoding="utf-8")
        assert _nxt(world, run_id)["action"] == "fix"
    p.write_text(p.read_text(encoding="utf-8") + "\nlast edit\n", encoding="utf-8")
    after = _nxt(world, run_id)  # rounds used up: full checks run anyway
    assert after["action"] == "run_reviewer", after


# 5: review, decide, then what the workflow has next (brownfield-change: a gate after req)
def test_clean_artifact_review_decide_and_reach_the_gate(world: World) -> None:
    run_id = _start(world)
    r = _to_reviewer(world, run_id)
    assert r["review"]["package_path"] and r["review"]["write_to"]
    _review(world, r)
    n = _nxt(world, run_id)
    assert n["schema"] == "next-action.v2" and n["action"] == "pause_approval", n
    assert n["say"].startswith("req passed"), n
    assert _state(world, run_id)["status"] == "PAUSED_APPROVAL"


# 6: invalid review
def test_invalid_review_reruns_reviewer_then_unavailable(world: World) -> None:
    run_id = _start(world)
    r = _to_reviewer(world, run_id)
    art = r["artifact_path"]
    (world.companion / r["review"]["write_to"]).parent.mkdir(parents=True, exist_ok=True)
    for _ in range(int(ORG_DEFAULTS["retry"]["review"]) - 1):
        (world.companion / r["review"]["write_to"]).write_text("not json", encoding="utf-8")
        r = _nxt(world, run_id)
        assert r["action"] == "run_reviewer", r
    (world.companion / r["review"]["write_to"]).write_text("not json", encoding="utf-8")
    _nxt(world, run_id)
    rev = _review_record(world, art)
    assert rev["status"] == "could_not_review"
    assert "E-REV-02" in rev["status_reason"]


# 7: RETRY seeds the next attempt
def test_retry_attempt_is_seeded_from_previous(world: World) -> None:
    run_id = _start(world)
    r = _to_reviewer(world, run_id)
    first_text = (world.companion / r["artifact_path"]).read_text(encoding="utf-8")
    _review(world, r, findings=[MAJOR])
    n = _nxt(world, run_id)
    assert n["action"] == "run_step" and n["step"] == "req" and n["attempt"] == 2, n
    assert n["retry"]["cause"] == "retry_review"
    assert n["retry"]["seeded_from"].endswith("/req.md")
    assert n["retry"]["feedback"]
    assert (world.companion / n["artifact_path"]).read_text(encoding="utf-8") == first_text
    assert _nxt(world, run_id) == n  # seeded content is not mistaken for a finished attempt


# 8: hard gate failure skips the review
def test_hard_gate_failure_decides_without_review(world: World) -> None:
    run_id = _start(world)
    d = _nxt(world, run_id)
    art = d["artifact_path"]
    _write_req(world, run_id, art)
    line = {
        "ts": iso(world.clock()),
        "session_id": "sess-setup",
        "step": "req",
        "attempt": 1,
        "tool": "Bash",
        "target": "cat context/manifest.json",
        "decision": "allow",
        "code": None,
        "read_only": True,
    }
    with (world.companion / f"runs/{run_id}/tool-log.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(line, sort_keys=True) + "\n")
    n = _nxt(world, run_id)
    p = world.companion / art
    for i in range(FIX_ROUNDS):  # the self-check lists H7 too: use the fix rounds up first
        assert n["action"] == "fix", n
        p.write_text(p.read_text(encoding="utf-8") + f"\nedit {i}\n", encoding="utf-8")
        n = _nxt(world, run_id)
    assert n["action"] != "run_reviewer", n
    assert n["step"] == "req" and n["attempt"] == 2 and n["retry"], n
    rev = _review_record(world, art)
    assert rev["status"] == "could_not_review"


# 9: model mode
def test_model_mode_still_returns_v1(world: World) -> None:
    run_id = _start(world, "model")
    d = _nxt(world, run_id)
    assert d["action"] == "run_skill" and d.get("schema") != "next-action.v2"
    assert "instruction_path" not in d


# 11: the skill writes content only; tsl fills in the envelope (design A1 §6 #4)
def test_artifact_without_envelope_is_stamped_and_reaches_review(world: World) -> None:
    from tsl.core.frontmatter import split
    from tsl.core.jsonio import dump_yaml

    run_id = _start(world)
    d = _nxt(world, run_id)
    art = d["artifact_path"]
    _write_req(world, run_id, art)
    p = world.companion / art
    doc = split(p.read_text(encoding="utf-8"))
    owned = ("schema", "run_id", "step", "attempt", "skill", "inputs", "pack_sha")
    stamped = {k: doc.front[k] for k in owned if k in doc.front}
    content = {k: v for k, v in doc.front.items() if k not in owned}
    p.write_text("---\n" + dump_yaml(content) + "---\n" + doc.body, encoding="utf-8")
    r = _nxt(world, run_id)
    assert r["action"] == "run_reviewer", r
    after = split(p.read_text(encoding="utf-8")).front
    assert {k: after[k] for k in stamped} == stamped


# 12: the verifier could not run (Docker off): stop with its error, mark nothing as checked
def test_verifier_unavailable_stops_instead_of_reviewing(monkeypatch: Any) -> None:
    import pytest

    from tsl.core.errors import TslError
    from tsl.harness import verify as verify_mod
    from tsl.orchestrator.loop import _Loop

    def unavailable(*_a: Any, **_k: Any) -> None:
        raise TslError("E-H3-07", "docker not running", data={"gates": []})

    monkeypatch.setattr(verify_mod, "verify_artifact", unavailable)
    loop = _Loop(None, None, "run_x")  # type: ignore[arg-type]
    with pytest.raises(TslError) as exc:
        loop._full_checks("artifacts/T-1/run_x/impl.md")
    assert exc.value.code == "E-H3-07"
    assert "Paused at impl" in exc.value.message and "Docker" in str(exc.value.next)
    assert loop.notes == []
