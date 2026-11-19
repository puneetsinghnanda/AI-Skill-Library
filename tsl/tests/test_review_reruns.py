"""Review rounds that cost a full rerun for nothing (HMS-21).

- A reviewer quoting an item's YAML line under #item:<id> was rejected twice (design, CO-8).
- A quote in the right file under the wrong anchor cost a full review round each time.
- The reviewer, never given ide-answers.md or open-questions.md, called a cite of them
  cross-step and an open question missing; the rerun re-asked Q-05 as Q-06.
- The main session re-typed every review JSON; the reviewer now writes it itself."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from e2e_steps import SESSION, do_req_step, start_run
from helpers import World, review_json
from tsl.approvals import questions_md
from tsl.harness import citations as cit
from tsl.review.service import INSTRUCTIONS

RUN = "run_01TEST"
DESIGN = """---
schema: design.v1
components:
  - {id: CO-7, name: "AppointmentsPage: pass started through", module: "module:x:web", change: changed}
  - {id: CO-8, name: "Dashboard tests (api and web): add awaitingOutcome", module: "module:x:api", change: changed}
endpoints:
  - id: EP-1
    method: GET
    path: /api/dashboard
  - id: EP-2
    method: GET
    path: /api/appointments
---

# Design

## Components {#components}
- CO-8 Dashboard tests, changed: add awaitingOutcome to both suites.
- CO-80 Something else entirely.
"""

QUESTIONS = f"""---
schema: open-questions.v1
run_id: {RUN}
ticket: T-1
workflow: brownfield-change@1.4.0
step: threat@1.0.0
created_at: '2026-11-17T09:55:21Z'
status: open
---

# Open questions — T-1 (req step)

## Q-04 · non-blocking · ask: product owner
**Question:** Which list does the tile open?
**Proposed default:** none
answer: The started list
answered_by: eng-1
decision:

## Q-05 · non-blocking · ask: tech lead · round 4
**Question:** T-2 and T-8 accept unbounded count scans (awaitingOutcome has no lower bound, and the list total is unpaged) with no new control. Do you accept these performance risks for HMS-21, or should implement add a status/starts_at index?
**Proposed default:** none
answer:
answered_by:
decision:
"""

Q06 = {
    "id": "Q-06",
    "ask": "tech lead",
    "question": "Do you accept, for HMS-21, that the Awaiting outcome count and the started=true "
    "list total have no lower time bound (threat T-2 and T-8), or should a lower bound or a "
    "(status, starts_at) index be added?",
    "evidence": ["artifacts/T-1/run_01TEST/threat.md#item:T-2"],
}


def _resolver(tmp_path: Path) -> cit.Resolver:
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "design.md").write_text(DESIGN, encoding="utf-8")
    (tmp_path / "runs" / RUN).mkdir(parents=True)
    (tmp_path / "runs" / RUN / "open-questions.md").write_text(QUESTIONS, encoding="utf-8")
    return cit.Resolver(tmp_path, {}, {})


def _check(r: cit.Resolver, ref: str, quote: str, review: bool = True) -> cit.CiteResult:
    c = cit.parse_review(ref, set())
    assert c is not None, ref
    return cit.verify(c, quote, [], r, review=review)


# ------------------------------------------------------------------------- item spans (#2)
def test_review_item_cite_covers_the_flow_entry_as_written(tmp_path: Path) -> None:
    r = _resolver(tmp_path)
    q = 'name: "Dashboard tests (api and web): add awaitingOutcome", module: "module:x:api"'
    assert _check(r, "a/design.md#item:CO-8", q).ok
    assert _check(r, "a/design.md#CO-8", q).ok  # bare id reads as item:CO-8
    # The body line that names the item, but not one naming another item (CO-80).
    assert _check(r, "a/design.md#item:CO-8", "add awaitingOutcome to both suites").ok
    assert not _check(r, "a/design.md#item:CO-8", "Something else entirely").ok
    # Another item's line is not CO-8's.
    assert not _check(r, "a/design.md#item:CO-8", "AppointmentsPage: pass started through").ok


def test_review_item_cite_covers_a_block_entry(tmp_path: Path) -> None:
    r = _resolver(tmp_path)
    assert _check(r, "a/design.md#item:EP-2", "path: /api/appointments").ok
    assert not _check(r, "a/design.md#item:EP-2", "path: /api/dashboard").ok


def test_artifact_item_cite_keeps_the_json_span(tmp_path: Path) -> None:
    """An artifact's own cite stays strict: the raw YAML line is a reviewer convenience."""
    r = _resolver(tmp_path)
    c = cit.parse("a/design.md#item:CO-8", set())
    assert c is not None
    # HMS-21's quote: two keys in written order; the JSON span sorts them (module before name).
    q = 'name: "Dashboard tests (api and web): add awaitingOutcome", module: "module:x:api"'
    assert not cit.verify(c, q, [], r).ok
    assert cit.verify(c, "Dashboard tests (api and web): add awaitingOutcome", [], r).ok


# ---------------------------------------------------------------------- one-place repair (#2)
def test_locate_unique_finds_the_one_place_only() -> None:
    text = "a\nOrder events are\nkept 24 hours.\nb\nkept twice\nkept twice\n"
    assert cit.locate_unique("Order events are kept 24 hours", text) == (2, 3)
    assert cit.locate_unique("kept twice", text) is None  # two places: not repaired
    assert cit.locate_unique("not in the file at all", text) is None
    assert cit.locate_unique("short", text) is None


# ------------------------------------------------------------------ open questions (#4)
def test_open_question_cite_resolves_in_every_form(tmp_path: Path) -> None:
    r = _resolver(tmp_path)
    path = f"runs/{RUN}/open-questions.md"
    assert _check(r, f"{path}#q-05", "unbounded count scans", review=False).ok
    assert _check(r, f"{path}#Q-05", "unbounded count scans").ok  # bare id in a review
    assert _check(r, f"{path}#item:Q-05", "unbounded count scans").ok
    assert not _check(r, f"{path}#q-05", "Which list does the tile open?").ok  # that is Q-04
    res = _check(r, f"{path}#q-09", "unbounded count scans")
    assert not res.ok and res.reason == "question Q-09 not found"


def test_a_claim_citing_an_open_question_still_needs_its_key_term(tmp_path: Path) -> None:
    """Second review fix 1: an unanswered question is no evidence that a claim holds, so the
    cite must resolve and still carry the claim's key term (unlike an ide-answers cite)."""
    r = _resolver(tmp_path)
    path = f"runs/{RUN}/open-questions.md"
    claim = {"id": "C1", "text": "`awaitingOutcome` is bounded", "cites": [f"{path}#q-05"]}
    assert cit.verify_claim(claim, r, set()).ok  # the term is in Q-05
    claim["text"] = "`retentionDays` is 30"
    assert not cit.verify_claim(claim, r, set()).ok
    claim["cites"] = [f"{path}#q-07"]
    assert not cit.verify_claim(claim, r, set()).ok


def test_unanswered_lists_open_questions_with_their_cite(tmp_path: Path) -> None:
    _resolver(tmp_path)
    got = questions_md.unanswered(tmp_path / "runs" / RUN / "open-questions.md", RUN)
    assert [(q["id"], q["cite"]) for q in got] == [("Q-05", f"runs/{RUN}/open-questions.md#q-05")]
    assert questions_md.unanswered(tmp_path / "missing.md", RUN) == []


def test_duplicate_question_is_found() -> None:
    open_qs = [
        {
            "id": "Q-05",
            "ask": "tech lead",
            "question": QUESTIONS.split("**Question:** ")[2].split("\n")[0],
            "evidence": [],
        }
    ]
    assert questions_md.duplicate_of(Q06, open_qs) == "Q-05"
    assert questions_md.duplicate_of({**Q06, "ask": "product owner"}, open_qs) is None
    other = {"id": "Q-07", "ask": "tech lead", "question": "Should the tile show T-2 in red?"}
    assert questions_md.duplicate_of(other, open_qs) is None


def test_instructions_name_the_run_records_and_the_review_file() -> None:
    for words in ("Run records", "#q-05", "#a-01", "Write the review to", "exactly once"):
        assert words in INSTRUCTIONS, words


# ------------------------------------------------------------------- end to end (world)
def _misplaced(world: World, art: str, package: dict[str, Any], quote: str) -> tuple[int, Any]:
    finding = {
        "id": "F-1",
        "severity": "minor",
        "category": "consistency",
        "text": "Retention differs from the baseline.",
        "cites": [{"ref": "context/intent-baseline.md#goals", "quote": quote}],
    }
    code, env, _, err = world.cli(
        ["review", "record", art, "--json"],
        session=SESSION,
        stdin=review_json(package, findings=[finding]),
    )
    assert env is not None, err
    return code, env


def test_quote_under_the_wrong_anchor_is_moved_not_rejected(world: World) -> None:
    run_id = start_run(world)
    res = do_req_step(world, run_id, until="prepared")
    art = res["artifact"]
    code, env = _misplaced(world, art, res["package"], "Order events are kept 24 hours")
    assert code == 0, env
    assert [w["code"] for w in env["warnings"]] == ["E-REV-06"], env
    rev = json.loads((world.companion / art.replace(".md", ".review.json")).read_text())
    ref = rev["findings"][0]["cites"][0]["ref"]
    assert ref.startswith("context/intent-baseline.md#L"), ref
    # decide verifies the moved cite and keeps the finding.
    code, dec, _, err = world.cli(["decide", art, "--json"], session=SESSION)
    assert dec is not None, err
    rec = json.loads((world.companion / dec["data"]["verification_path"]).read_text())
    assert [f["id"] for f in rec["findings_kept"]] == ["F-1"]


def test_package_lists_run_records_and_where_to_write(world: World) -> None:
    run_id = start_run(world)
    res = do_req_step(world, run_id, until="written")
    (world.companion / f"runs/{run_id}/ide-answers.md").write_text("# IDE answers\n\n## A-01\n")
    stale = world.companion / f"runs/{run_id}/review-input/req.review.json"
    stale.parent.mkdir(parents=True, exist_ok=True)
    stale.write_text("{}")  # the last round's JSON: prepare removes it (review fix 1)
    code, env, _, err = world.cli(["review", "prepare", res["artifact"], "--json"], session=SESSION)
    assert code == 0 and env is not None, err
    data = env["data"]
    assert data["review_input_path"] == f"runs/{run_id}/review-input/req.review.json"
    pkg = json.loads((world.companion / data["package_path"]).read_text())
    assert pkg["run_records"] == [{"name": "ide-answers", "path": f"runs/{run_id}/ide-answers.md"}]
    md = data["package"]
    assert f"- ide-answers: runs/{run_id}/ide-answers.md" in md
    assert f"Write the review to: runs/{run_id}/review-input/req.review.json" in md
    assert not stale.exists()


# ------------------------------------------------------------- the reviewer's one write (#5b)
def _pre_write(world: World, target: Path, agent_type: str | None, tool: str = "Write") -> str:
    from e2e_steps import hook

    data: dict[str, Any] = {
        "hook_event_name": "PreToolUse",
        "tool_name": tool,
        "tool_input": {"file_path": str(target), "content": "{}"},
    }
    if agent_type:
        data["agent_type"] = agent_type
    out, _ = hook(world, "pre-tool", data)
    if not out.strip():
        return "allow"  # the hook says nothing on allow
    return str(json.loads(out)["hookSpecificOutput"]["permissionDecision"])


def test_reviewer_may_write_only_its_review_input(world: World) -> None:
    from e2e_steps import next_action

    run_id = start_run(world)
    next_action(world, run_id)
    review_in = world.companion / "runs" / run_id / "review-input" / "req.review.json"
    art = world.companion / "artifacts" / "T-1" / run_id / "req.md"
    assert _pre_write(world, review_in, "truminds:reviewer") == "allow"
    assert _pre_write(world, art, "truminds:reviewer") == "deny"
    assert _pre_write(world, review_in, "truminds:reviewer", tool="Edit") == "deny"
    # The main session keeps writing as before.
    assert _pre_write(world, review_in, None) == "allow"


def test_reviewer_write_is_refused_off_its_file_and_never_logged(world: World) -> None:
    """Review fixes 2, 4, 9: only this run's current step file; refusals are not logged."""
    from e2e_steps import next_action

    review_in = world.companion / "runs" / "run_X" / "review-input" / "req.review.json"
    assert _pre_write(world, review_in, "truminds:reviewer") == "deny"  # no bound run
    run_id = start_run(world)
    next_action(world, run_id)
    base = world.companion / "runs"
    assert (
        _pre_write(
            world, base / run_id / "review-input" / "design.review.json", "truminds:reviewer"
        )
        == "deny"
    )  # another step
    assert (
        _pre_write(
            world, base / "run_OTHER" / "review-input" / "req.review.json", "truminds:reviewer"
        )
        == "deny"
    )  # another run
    log = base / run_id / "tool-log.jsonl"
    entries = [json.loads(x) for x in log.read_text().splitlines()] if log.is_file() else []
    assert not [e for e in entries if e.get("decision") == "deny"], entries


def test_repair_never_moves_a_cite_that_names_one_thing(tmp_path: Path) -> None:
    """Review fix 3: CO-7's line is not evidence for CO-8; a heading cite is still moved."""
    from tsl.review.service import _repair

    r = _resolver(tmp_path)
    item = cit.parse("a/design.md#item:CO-8", set())
    assert item is not None
    assert _repair(item, "AppointmentsPage: pass started through", r) is None
    head = cit.parse("a/design.md#design", set())
    assert head is not None
    assert _repair(head, "AppointmentsPage: pass started through", r) == "a/design.md#L4"


def test_claim_cite_is_not_widened(tmp_path: Path) -> None:
    """Review fix 10: #claim:<id> stays the claims[] entry, even in a review."""
    (tmp_path / "x.md").write_text(
        "---\nclaims:\n  - {id: C1, text: only this}\ncomponents:\n  - {id: C1, name: other thing}\n"
        "---\n\n| C1 | a table row about other thing |\n",
        encoding="utf-8",
    )
    r = cit.Resolver(tmp_path, {}, {})
    assert _check(r, "x.md#claim:C1", "only this").ok
    assert not _check(r, "x.md#claim:C1", "a table row about other thing").ok


def test_locate_unique_is_fast_on_a_large_file() -> None:
    """Review fix 8: one pass, not a window per line."""
    import time

    text = "\n".join(f"line {i} says the thing about the" for i in range(50_000))
    text += "\nthe one real sentence ends with the"
    t = time.perf_counter()
    assert cit.locate_unique("the one real sentence ends with the", text) == (50_001, 50_001)
    assert time.perf_counter() - t < 3.0


def test_broken_questions_file_does_not_stop_next(tmp_path: Path) -> None:
    """Review fix 6: a hand-edited header ('round' with no number) is not an error."""
    p = tmp_path / "open-questions.md"
    p.write_text(QUESTIONS.replace("· round 4", "· round"), encoding="utf-8")
    assert questions_md.unanswered(p, RUN) == []


def test_ticket_id_in_paths_and_common_words_do_not_make_a_duplicate() -> None:
    """Review fix 5."""
    a = {
        "id": "Q-05",
        "ask": "tech lead",
        "evidence": ["artifacts/HMS-21/run_1/threat.md#item:T-2"],
        "question": "Should this count include cancelled visits for HMS-21?",
    }
    b = {
        "id": "Q-07",
        "ask": "tech lead",
        "evidence": ["artifacts/HMS-21/run_1/design.md#item:EP-1"],
        "question": "Should this endpoint return a count with paging for HMS-21?",
    }
    assert questions_md.duplicate_of(b, [a], frozenset({"HMS-21"})) is None


def test_values_check_reads_only_the_cited_question(tmp_path: Path) -> None:
    """Review fix 7: a number in another question does not source a requirement."""
    from tsl.harness.skillchecks import CheckEnv, c_values_sourced

    _resolver(tmp_path)
    oq = f"runs/{RUN}/open-questions.md"
    p = tmp_path / oq
    p.write_text(
        p.read_text(encoding="utf-8").replace("The started list", "Keep 30 days"), encoding="utf-8"
    )
    req = {
        "id": "REQ-1",
        "status": "known",
        "statement": "Retain events 30 days",
        "cites": [f"{oq}#q-05"],
    }
    env = CheckEnv({"run_id": RUN, "requirements": [req]}, "", tmp_path, [], {})
    assert c_values_sourced(env, {}) == "REQ-1: value '30 days' not in a cited line"
    req["cites"] = [f"{oq}#q-04"]
    assert c_values_sourced(env, {}) is None
    # Second review fix 2: a value in the question or its proposed default is not an answer.
    p.write_text(
        p.read_text(encoding="utf-8").replace(
            "**Proposed default:** none\nanswer:\n", "**Proposed default:** 30 days\nanswer:\n"
        ),
        encoding="utf-8",
    )
    assert "**Proposed default:** 30 days" in p.read_text(encoding="utf-8")
    req["cites"] = [f"{oq}#q-05"]
    assert c_values_sourced(env, {}) == "REQ-1: value '30 days' not in a cited line"


def test_unsupported_verdict_needs_one_good_cite_like_decide(world: World) -> None:
    """Second review fix 5: record asks no more than decide, which accepts an unsupported
    verdict when any one of its cites verifies."""
    run_id = start_run(world)
    res = do_req_step(world, run_id, until="prepared")
    text = review_json(res["package"])
    obj = json.loads(text.split("```json\n", 1)[1].split("\n```", 1)[0])
    good = {
        "ref": "context/intent-baseline.md#data-retention",
        "quote": "Order events are kept 24 hours",
    }
    bad = {
        "ref": "context/intent-baseline.md#data-retention",
        "quote": "Order events are kept 90 days",
    }
    obj["claims_checked"] = [{"claim_id": "C1", "verdict": "unsupported", "cites": [good, bad]}]
    code, env, _, err = world.cli(
        ["review", "record", res["artifact"], "--json"], session=SESSION, stdin=json.dumps(obj)
    )
    assert env is not None, err
    assert code == 0 and env["warnings"] == [], env
    obj["claims_checked"][0]["cites"] = [bad]
    code, env, _, err = world.cli(
        ["review", "record", res["artifact"], "--json"], session=SESSION, stdin=json.dumps(obj)
    )
    assert env is not None, err
    assert code == 2 and env["code"] == "E-REV-05", env


def test_duplicates_within_one_round_are_found() -> None:
    """Second review fix 6: decide compares each new question with those before it too."""
    seen: list[dict[str, Any]] = []
    flagged = []
    for q in (Q06, {**Q06, "id": "Q-07"}):
        flagged.append(questions_md.duplicate_of(q, seen, frozenset({"HMS-21"})))
        seen.append(q)
    assert flagged == [None, "Q-06"]
