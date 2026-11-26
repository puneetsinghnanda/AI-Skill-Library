"""tsl state show --progress: the data behind the Mods progress panel (roadmap item 5).

One run, picked by the Claude session it is bound to, with every step's status and band, what a
paused run waits on (and the exact command), and the open questions with their text. Read only:
it must work offline and never change the run."""

from __future__ import annotations

import json
from typing import Any

from e2e_steps import SESSION, do_req_step, start_run
from helpers import World


def _progress(world: World, *args: str, session: str | None = SESSION) -> dict[str, Any]:
    code, env, _, err = world.cli(["state", "show", *args, "--progress", "--json"], session=session)
    assert code == 0 and env is not None, (env, err)
    return dict(env)


def test_no_run_without_a_bound_session(world: World) -> None:
    start_run(world)
    for session in (None, "sess-other"):  # no session, or one that never ran this run
        env = _progress(world, session=session)
        assert env["data"] == {"progress": None} and env["message"] == "No active run", env


def test_the_bound_run_with_its_steps(world: World) -> None:
    run_id = start_run(world)
    p = _progress(world)["data"]["progress"]
    assert p["run_id"] == run_id and p["ticket"] == "ABC-142" and p["bound"] is True
    assert p["status"] == "RUNNING" and p["waiting"] is None
    assert p["steps"][0] == {
        "id": "req",
        "kind": "skill",
        "status": "PENDING",
        "attempt": None,
        "band": None,
    }
    res = do_req_step(world, run_id)
    assert res["code"] == 0, res["env"]
    p = _progress(world)["data"]["progress"]
    req = p["steps"][0]
    assert (req["status"], req["attempt"], req["band"]) == ("DONE", 1, "High"), req
    assert all(s["band"] is None for s in p["steps"][1:])
    # The same run by id, from any session.
    assert _progress(world, run_id, session=None)["data"]["progress"]["run_id"] == run_id


def test_paused_for_input_lists_the_open_questions(world: World) -> None:
    run_id = start_run(world)
    res = do_req_step(world, run_id, variant={"blocking_question": True})
    assert res["env"]["data"]["action"] == "pause_input", res["env"]
    p = _progress(world)["data"]["progress"]
    assert p["status"] == "PAUSED_INPUT"
    assert p["waiting"] == {
        "kind": "input",
        "gate": None,
        "role": None,
        "command": f"/truminds:resume {run_id}",
        "file": f"runs/{run_id}/open-questions.md",
    }
    q = p["questions"]
    assert q["open_blocking"] == 1, q
    first = q["items"][0]
    assert first["blocking"] is True and first["ask"] == "product owner"
    assert first["text"].startswith("Ticket wants history; the baseline keeps 24 hours."), first


def test_paused_for_approval_names_the_gate_role_and_command(world: World) -> None:
    run_id = start_run(world)
    res = do_req_step(world, run_id, score=2)
    assert res["env"]["data"]["action"] == "pause_approval", res["env"]
    p = _progress(world)["data"]["progress"]
    assert p["status"] == "PAUSED_APPROVAL"
    assert p["steps"][0]["band"] == "Low"
    w = p["waiting"]
    assert w["kind"] == "approval" and w["command"] == f"/tsl-gate {run_id}", w
    assert w["gate"].startswith("G-escalate-req") and w["role"], w


def test_read_only_and_unknown_run(world: World) -> None:
    run_id = start_run(world)
    state = world.companion / f"runs/{run_id}/state.json"
    before = state.read_bytes()
    _progress(world)
    assert state.read_bytes() == before  # the panel never changes the run
    code, env, _, _ = world.cli(
        ["state", "show", "run_nope", "--progress", "--json"], session=SESSION
    )
    assert code == 3 and env is not None and env["code"] == "E-RUN-04", env


def test_a_broken_questions_file_shows_no_questions(world: World) -> None:
    run_id = start_run(world)
    do_req_step(world, run_id, variant={"blocking_question": True})
    (world.companion / f"runs/{run_id}/open-questions.md").write_text("not front matter\n")
    p = _progress(world)["data"]["progress"]
    assert p["questions"] == {
        "open_blocking": 0,
        "open_non_blocking": 0,
        "open_ide": 0,
        "items": [],
    }
    assert json.dumps(p)  # still a full answer


def test_a_paused_run_still_shows_its_step(world: World) -> None:
    """tsl decide clears the cursor after every decision, also the one that pauses the run: the
    panel falls back to the step that waits, so a paused run still shows 'step n of m'."""
    run_id = start_run(world)
    do_req_step(world, run_id, variant={"blocking_question": True})
    st = json.loads((world.companion / f"runs/{run_id}/state.json").read_text())
    assert not (st.get("cursor") or {}).get("step"), st.get("cursor")
    p = _progress(world)["data"]["progress"]
    assert p["current"] == "req" and p["position"] == {"n": 1, "of": len(p["steps"])}, p


def test_questions_accepted_on_resume_are_not_open(world: World) -> None:
    """A question frozen on resume (answered_sha256) is settled, even with no answer: a
    non-blocking one takes its default then."""
    run_id = start_run(world)
    do_req_step(world, run_id, variant={"blocking_question": True})
    p = _progress(world)["data"]["progress"]
    qid = p["questions"]["items"][0]["id"]
    sp = world.companion / f"runs/{run_id}/state.json"
    st = json.loads(sp.read_text())
    st["questions"]["answered_sha256"][qid] = "0" * 64
    sp.write_text(json.dumps(st))
    q = _progress(world)["data"]["progress"]["questions"]
    assert qid not in [i["id"] for i in q["items"]], q
    assert q["open_blocking"] == p["questions"]["open_blocking"] - 1, q


def test_a_signed_reject_is_shown_as_a_reject(world: World) -> None:
    run_id = start_run(world)
    res = do_req_step(world, run_id, score=2)
    gate = res["env"]["data"]["gate"]
    code, env, _, err = world.cli(
        ["gate", run_id, "reject", "--gate", gate, "--comment-file", "-", "--json"],
        user="tl",
        stdin="Out of scope for this release",
    )
    assert code == 0, (env, err)
    world.sync_companion()
    w = _progress(world)["data"]["progress"]["waiting"]
    assert w["kind"] == "resume" and w["gate"] == gate and w["decision"] == "reject", w


def test_one_broken_state_file_leaves_the_others(world: World) -> None:
    run_id = start_run(world)
    other = world.companion / "runs/run_01JZZZZZZZZZZZZZZZZZZZZZZZ/state.json"
    other.parent.mkdir(parents=True)
    other.write_text("<<<<<<< HEAD\n{\n", encoding="utf-8")
    assert _progress(world)["data"]["progress"]["run_id"] == run_id


def test_the_session_index_finds_the_run_without_a_scan(world: World, monkeypatch: Any) -> None:
    """The hooks keep a session index (run_id, companion): the panel reads that one run."""
    import tsl.state.progress as prog

    run_id = start_run(world)
    index = world.rt(session=SESSION).home.session(SESSION)
    if not index.is_file():  # the start hook writes it in a session; write it as it would
        index.parent.mkdir(parents=True, exist_ok=True)
        index.write_text(json.dumps({"run_id": run_id, "companion": str(world.companion)}))

    def no_scan(_comp: Any) -> list[str]:
        raise AssertionError("scanned every run")

    monkeypatch.setattr(prog, "all_runs", no_scan)
    assert _progress(world)["data"]["progress"]["run_id"] == run_id
