"""PR body: what changed, finding text, pack distance, questions answered by default."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

from tsl.services import pr, pr_body

RUN = "run_01ABCDEFGHJKMNPQRSTVWXYZ12"

IMPL = """---
schema: change.v1
summary: "Adds a read-only count to GET /api/doctors/:id."
code:
  - repo: shop
    files: [api/a.ts]
---
# Change: T-1

## Summary
- x

## Changes
- api/src/a.ts — new: shared window rule for the count.
- web/src/b.tsx — DetailPage: the labelled link, @eng-4f2a <b>see</b>.

## Known
- none
"""

DESIGN = """---
schema: design.v1
---
# Design

## Components
Components:
- Thing — new, module:x: does it.

Endpoints:
- GET /api/doctors/:id — changed: adds `count` and `window`.
- GET /api/other — existing: no change.

Story coverage:
- S-1: x
"""

QUESTIONS = """---
schema: open-questions.v1
status: open
step: design
---
# Open questions

## Q-01 · non-blocking · ask: tech lead
**Question:** Which zone?
**Proposed default:** Hospital zone.
answer: UTC
answered_by: eng-4f2a
decision:

## Q-02 · non-blocking · ask: tech lead
**Question:** Cover the Cancelled status?
**Proposed default:** Use NO_SHOW only; add the Cancelled test before merge.
answer:
answered_by:
decision:

## Q-03 · non-blocking · ask: tech lead
**Question:** Page size?
**Proposed default:** none
answer:
answered_by:
decision:
"""


def _ctx(root: Path) -> Any:
    comp = SimpleNamespace(root=root, path=lambda rel: root / rel)
    state = {
        "ticket": "T-1",
        "workflow": "feature",
        "pack": {"signed_at": "2026-01-01"},
        "gates": [],
    }
    return SimpleNamespace(state=state, run_id=RUN, comp=comp)


def _rows(art: str) -> list[dict[str, Any]]:
    kept = [{"id": "F-1", "severity": "minor", "text": "Missing *claim* for @someone\nsecond line"}]
    return [
        {
            "step": "design",
            "skill": "design@1",
            "outcome": "PASS",
            "band": "High",
            "record": "r1",
            "kept": kept,
            "artifact": f"{art}/design.md",
        },
        {
            "step": "impl",
            "skill": "implement@1",
            "outcome": "PASS",
            "band": "High",
            "record": "r2",
            "kept": [],
            "artifact": f"{art}/impl.md",
        },
    ]


def _world(tmp_path: Path) -> tuple[Any, str]:
    art = f"artifacts/T-1/{RUN}"
    (tmp_path / art).mkdir(parents=True)
    (tmp_path / art / "impl.md").write_text(IMPL, encoding="utf-8")
    (tmp_path / art / "design.md").write_text(DESIGN, encoding="utf-8")
    (tmp_path / "runs" / RUN).mkdir(parents=True)
    (tmp_path / "runs" / RUN / "open-questions.md").write_text(QUESTIONS, encoding="utf-8")
    return _ctx(tmp_path), art


def _status(behind: int, fresh: bool = True) -> dict[str, Any]:
    return {
        "state_block": {
            "fresh": fresh,
            "source_sha": {"shop": "abc1234ffff"},
            "commits_behind": {"shop": behind},
        }
    }


def _section_of(out: str, heading: str) -> str:
    return out.split(f"\n{heading}\n")[1].split("\n### ")[0]


def test_body_golden(tmp_path: Path) -> None:
    ctx, art = _world(tmp_path)
    out = pr.body(ctx, _rows(art), "High", "shop", _status(3))
    pack = next(x for x in out.splitlines() if x.startswith("**Context pack:**"))
    assert pack.startswith(
        "**Context pack:** signed 2026-01-01 · built at abc1234, 3 commits behind"
    )
    assert "fresh" not in pack
    what = _section_of(out, "### What changed")
    assert "Adds a read-only count to GET /api/doctors/:id." in what
    assert "- `api/src/a.ts`: new: shared window rule for the count." in what
    assert "@​eng-4f2a" in what and "<b>" not in what
    assert "- API GET /api/doctors/:id — changed: adds" in what
    assert "/api/other" not in what
    assert r"- [minor] design: F-1 Missing \*claim\* for @​someone second line" in out
    qs = _section_of(out, "### Questions answered by default")
    assert "2 non-blocking" in qs and "Q-01" not in qs
    assert (
        r"- Q-02: Cover the Cancelled status? → default: Use NO\_SHOW only; add the Cancelled test before merge."
        in qs
    )
    assert "⚠ needs action before merge" in qs
    assert "- Q-03: Page size? → default: no default" in qs
    assert qs.count("⚠") == 1


TICKET = """---
schema: ticket-snapshot.v1
run_id: {run}
ticket: T-1
source: file
fetched_at: '2026-01-01T00:00:00Z'
title: Show the doctor filter on the appointment list, and leave out Cancelled
  from the Today link @bob
---
# T-1
"""


def test_change_comes_first_and_harness_details_last(tmp_path: Path) -> None:
    ctx, art = _world(tmp_path)
    (tmp_path / art / "ticket.md").write_text(TICKET.format(run=RUN), encoding="utf-8")
    out = pr.body(ctx, _rows(art), "High", "shop", _status(0))
    heads = [x for x in out.splitlines() if x.startswith("#")]
    assert heads == [
        "## T-1: Show the doctor filter on the appointment list, and leave out Cancelled from "
        "the Today link @​bob",
        "### What changed",
        "### Questions answered by default",
        "### Findings for the reviewer (not blocking)",
        "### Reviewer checklist",
        "### Harness details",
    ]
    details = _section_of(out, "### Harness details")
    for part in ("**Run:**", "**Context pack:**", "| Step |", "Lowest band:", "Human decisions"):
        assert part in details and part not in out.split("### Harness details")[0]
    assert out.endswith(f"<!-- tsl:run_id={RUN} -->")


def test_pr_title_is_the_ticket_title(tmp_path: Path) -> None:
    _, art = _world(tmp_path)
    assert pr_body.ticket_title(tmp_path, "T-1", RUN) is None  # no ticket.md
    assert pr_body.pr_title("T-1", None, "feature (run_x)") == "T-1: feature (run_x)"
    (tmp_path / art / "ticket.md").write_text(TICKET.format(run=RUN), encoding="utf-8")
    title = pr_body.ticket_title(tmp_path, "T-1", RUN)
    assert title is not None and "\n" not in title and title.startswith("Show the doctor filter")
    t = pr_body.pr_title("T-1", title, "feature (run_x)")
    assert t.startswith("T-1: Show the doctor filter") and t.endswith("…")
    assert len(t) == pr_body.TITLE_CHARS
    assert pr_body.pr_title("T-1", "Short", "x") == "T-1: Short"
    (tmp_path / art / "ticket.md").write_text("no front matter", encoding="utf-8")
    assert pr_body.ticket_title(tmp_path, "T-1", RUN) is None


def test_up_to_date_and_unchecked_never_say_fresh_when_behind(tmp_path: Path) -> None:
    pack = {"signed_at": "S", "fresh": True}
    last = " (as of the last fetch)"
    assert (
        pr_body.pack_line(pack, "shop", _status(0))
        == "signed S · built at abc1234, up to date" + last
    )
    assert pr_body.pack_line(pack, "shop", _status(1)).endswith("1 commit behind" + last)
    assert pr_body.pack_line(pack, "shop", _status(60, False)).endswith(
        "60 commits behind, stale" + last
    )
    unchecked = pr_body.pack_line(pack, "shop", None)
    assert "fresh" not in unchecked and unchecked.endswith("not checked")


def test_fallbacks_when_artifacts_missing(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    rows = _rows("artifacts/none")
    out = pr.body(ctx, rows, "High", "shop")
    assert "Changes in shop from run" in out
    assert "Questions answered by default" not in out


def test_action_rule() -> None:
    # the real HMS-7 defaults: Q-06 asks for work, Q-03 only describes the design choice
    assert pr_body.default_actions("Add on this branch before merge")
    assert not pr_body.default_actions("Add to GET /api/doctors/:id as a read-only field")
    assert pr_body.default_actions("This should be added. TODO later")
    assert pr_body.default_actions("fix it before merging")
    assert pr_body.default_actions("leave a follow-up ticket")
    assert not pr_body.default_actions("Use the hospital zone")
    assert not pr_body.default_actions("The count must exclude Cancelled")
    assert not pr_body.default_actions(None)


def test_md_neutralises_markup_mentions_and_links() -> None:
    out = pr_body.md("\\<img src=x> ![p](http://evil/p.png) @bob #12 a|b `c` &#64; www.x")
    assert out.startswith("\\\\\\<img")  # the backslash is escaped, so the < stays escaped
    assert "\\!\\[p\\]\\(" in out
    assert "http://" not in out and "@bob" not in out and "&#64;" not in out
    assert "\\#12" in out and "a\\|b" in out and "\\`c\\`" in out
    assert "\n" not in pr_body.md("one\n## heading\ntwo")
    long = pr_body.md("x" * 500, limit=50)
    assert long.endswith("…") and len(long) == 50
