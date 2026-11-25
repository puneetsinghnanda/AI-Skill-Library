"""Content checks of story-split and unit-test, declared in their checks.yaml (roadmap A3).

The cases are cut down from the reviewer findings that cost a `split` or `ut` retry on 0.1.7
(HMS-23 to HMS-33). Each test runs the plugin's real checks.yaml through run_declared, so the
declarations are tested with the check kinds."""

from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import yaml

from tsl.harness.gates import added_lines, code_added
from tsl.harness.skillchecks import (
    CheckEnv,
    lists_after,
    named_set,
    run_declared,
    validate_declared,
    value_pattern,
    values_of,
)

PLUGIN = Path(__file__).resolve().parents[2] / "plugins" / "truminds" / "skills"
DATA_MODEL = (
    "# Data model\n\n## Appointments\nAn appointment links one doctor and one patient. Status is "
    "SCHEDULED,\nCOMPLETED, CANCELLED or NO_SHOW; a cancellation reason exists exactly when "
    "CANCELLED.\n"
)
TEST_FILES = r"(^|/)(test|tests|__tests__)/|\.(test|spec)\.[a-z]+$"


def _checks(skill: str) -> dict[str, Any]:
    return dict(yaml.safe_load((PLUGIN / skill / "checks.yaml").read_text(encoding="utf-8")))


def _outcome(env: CheckEnv, skill: str, cid: str) -> tuple[str, str, str]:
    o = next(o for o in run_declared(env, _checks(skill)) if o.id == cid)
    return o.status, o.gate, o.detail


def _story(sid: str, trace: list[str], *acs: str) -> dict[str, Any]:
    return {
        "id": sid,
        "title": f"Story {sid}",
        "trace": trace,
        "acceptance_criteria": [{"id": f"AC{i}", "text": t} for i, t in enumerate(acs, 1)],
    }


def _write_front(root: Path, rel: str, front: dict[str, Any]) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("---\n" + yaml.safe_dump(front) + "---\n# x\n", encoding="utf-8")


S4 = _story(
    "S-4",
    ["REQ-11"],
    "Given a Scheduled appointment, when staff open it, then the page is unchanged",
    "Given a Completed appointment, when staff open it, then the page is unchanged",
    "Given a Cancelled appointment, when staff open it, then the page is unchanged",
    "Given a No-show appointment, when staff open it, then the page is unchanged",
)
UT_BODY = """# Unit tests: HMS-31
## Summary
Tests for the appointment page.
## Tests
- web/src/__tests__/AppointmentDetailPage.test.tsx:
  - REQ-11: a Scheduled appointment keeps its actions (S-4 AC1).
  - REQ-11: a Cancelled appointment keeps its reason (S-4 AC3).
## Known
- S-4: covered.
## Unknown
None
"""


def _ut_env(
    tmp_path: Path,
    stories: list[dict[str, Any]] | None,
    body: str = UT_BODY,
    trace: list[str] | None = None,
    added: dict[str, str] | None = None,
) -> CheckEnv:
    named: dict[str, str] = {}
    if stories is not None:
        _write_front(tmp_path, "in/stories.md", {"schema": "stories.v1", "stories": stories})
        named["stories"] = "in/stories.md"
    return CheckEnv(
        {"schema": "ut-result.v1", "trace": trace or ["REQ-11"]},
        body,
        tmp_path,
        list(named.values()),
        {},
        named,
        code_added=(lambda: added) if added is not None else None,
    )


# ------------------------------------------------------------------- unit-test: hard gates
def test_every_ac_is_named_on_a_tests_line_hms31(tmp_path: Path) -> None:
    """HMS-31 ut a1 F-2: S-4 listed as covered; AC2 (Completed) and AC4 (No-show) untested."""
    status, gate, detail = _outcome(_ut_env(tmp_path, [S4]), "unit-test", "unit-test.acs-named")
    assert (status, gate) == ("fail", "H5")
    assert detail == "S-4 AC2, S-4 AC4 not named in Tests or Unknown"


def test_an_ac_under_unknown_or_in_any_written_form_counts(tmp_path: Path) -> None:
    excused = UT_BODY.replace("None\n", "- U-1: S-4 AC2 and AC4 need a browser.\n")
    assert (
        _outcome(_ut_env(tmp_path, [S4], excused), "unit-test", "unit-test.acs-named")[0] == "pass"
    )
    forms = UT_BODY.replace(
        "  - REQ-11: a Cancelled appointment keeps its reason (S-4 AC3).",
        "  - S-4: Completed and Cancelled unchanged (AC2 to AC3),\n    No-show too (AC4).",
    )
    assert _outcome(_ut_env(tmp_path, [S4], forms), "unit-test", "unit-test.acs-named")[0] == "pass"
    alone = UT_BODY.replace("(S-4 AC3)", "(S-4)")  # a story alone names none of its ACs
    status, _, detail = _outcome(_ut_env(tmp_path, [S4], alone), "unit-test", "unit-test.acs-named")
    assert status == "fail" and "S-4 AC3" in detail


def test_req_dropped_from_trace_hms28(tmp_path: Path) -> None:
    """HMS-28 ut a1 F-1: REQ-12 traced by S-5 has no test and is not in the ut trace."""
    s5 = _story("S-5", ["REQ-12"], "Given status Inactive, when ..., then only Inactive doctors")
    env = _ut_env(tmp_path, [S4, s5])
    status, gate, detail = _outcome(env, "unit-test", "unit-test.reqs-traced")
    assert (status, gate) == ("fail", "H5")
    assert detail == "REQ-12 covered fewer than 1 times and not named under Unknown"
    under_unknown = UT_BODY.replace("None\n", "- U-1: REQ-12 is unchanged code, no test added.\n")
    env = _ut_env(tmp_path, [S4, s5], under_unknown)
    assert _outcome(env, "unit-test", "unit-test.reqs-traced")[0] == "pass"
    env = _ut_env(tmp_path, [S4, s5], trace=["REQ-11", "REQ-12"])
    assert _outcome(env, "unit-test", "unit-test.reqs-traced")[0] == "pass"


def test_without_stories_the_ut_checks_do_not_apply(tmp_path: Path) -> None:
    """A defect run's unit-test (and eval case EC-01) has no stories input."""
    env = _ut_env(tmp_path, None, added={"api/test/a.test.ts": "x"})
    for cid in ("unit-test.acs-named", "unit-test.reqs-traced", "unit-test.ac-values-in-tests"):
        assert _outcome(env, "unit-test", cid)[0] == "skip", cid


# ---------------------------------------------------------------- unit-test: soft check
def test_ac_values_must_be_in_the_added_test_lines_hms30(tmp_path: Path) -> None:
    """HMS-30 ut a1 F-1: S-2 AC1 needs the 21st row on page 2; the fixture had 5 rows."""
    s2 = _story(
        "S-2", ["REQ-4"], "Given 21 matching appointments, when page 2 opens, then the 21st shows"
    )
    body = UT_BODY.replace("(S-4 AC1)", "(S-4 AC1, S-2 AC1)")
    five = {
        "api/test/list.test.ts": "const rows = make(5)",
        "api/src/list.ts": "const pageSize = 21",  # not a test file: does not count
    }
    env = _ut_env(tmp_path, [s2, S4], body, ["REQ-4", "REQ-11"], five)
    status, gate, detail = _outcome(env, "unit-test", "unit-test.ac-values-in-tests")
    assert (status, gate) == ("fail", "soft")
    assert detail == "no added test line holds a value of S-2 AC1 (21)"
    env = _ut_env(
        tmp_path, [s2, S4], body, ["REQ-4", "REQ-11"], {"api/test/list.test.ts": "make(21)"}
    )
    assert _outcome(env, "unit-test", "unit-test.ac-values-in-tests")[0] == "pass"
    env = _ut_env(tmp_path, [s2, S4], body, ["REQ-4", "REQ-11"], None)  # no code step
    assert _outcome(env, "unit-test", "unit-test.ac-values-in-tests")[0] == "skip"


def test_values_of_and_value_forms() -> None:
    assert values_of("Given 21 matching (S-2 AC1) at 09:30, then the 21st shows") == ["09:30", "21"]
    assert values_of("Given one appointment, when REQ-4 applies, then it shows") == []
    assert value_pattern("NO_SHOW").search("a No-show appointment")
    assert not value_pattern("SCHEDULED").search("an appointment scheduled at 10:00")
    assert value_pattern("NO_SHOW", code=True).search("status: 'no_show'")


# ---------------------------------------------------------------- story-split: soft check
def _split_env(
    tmp_path: Path, stories: list[dict[str, Any]], reqs: list[dict[str, Any]]
) -> CheckEnv:
    (tmp_path / "context").mkdir(exist_ok=True)
    (tmp_path / "context/data-model.md").write_text(DATA_MODEL, encoding="utf-8")
    _write_front(tmp_path, "in/req.md", {"schema": "intent.v1", "requirements": reqs})
    return CheckEnv(
        {"schema": "stories.v1", "stories": stories},
        "",
        tmp_path,
        ["in/req.md"],
        {},
        {"intent": "in/req.md"},
    )


def test_split_every_status_in_a_story_about_statuses_hms31(tmp_path: Path) -> None:
    """HMS-31 split a1 F-1: REQ-11 'unchanged' checked for Scheduled and Cancelled only."""
    stories = [
        _story(
            "S-3",
            ["REQ-11"],
            "Given a Scheduled appointment, when opened, then actions are as before",
            "Given a Cancelled appointment, when opened, then the reason is as before",
        )
    ]
    reqs = [
        {
            "id": "REQ-11",
            "status": "known",
            "statement": "Actions for each appointment status are unchanged.",
        }
    ]
    status, gate, detail = _outcome(
        _split_env(tmp_path, stories, reqs), "story-split", "story-split.status-values"
    )
    assert (status, gate) == ("fail", "soft")
    assert detail == "COMPLETED, NO_SHOW (from context/data-model.md) named by none of S-3"


def test_split_status_check_only_for_reqs_about_these_statuses(tmp_path: Path) -> None:
    """Not about the data model's appointment statuses: a REQ without the word or a value, and
    HMS-28's doctor "status filter" (a doctor's Active/Inactive status)."""
    stories = [
        _story(
            "S-1", ["REQ-1"], "Given a Cancelled appointment, when opened, then the reason shows"
        ),
        _story(
            "S-3",
            ["REQ-12"],
            "Given status Inactive, when filtered, then only Inactive doctors show",
        ),
    ]
    reqs = [
        {"id": "REQ-1", "status": "known", "statement": "The list shows the cancellation reason."},
        {"id": "REQ-12", "status": "known", "statement": "The status filter works as before."},
    ]
    env = _split_env(tmp_path, stories, reqs)
    assert _outcome(env, "story-split", "story-split.status-values")[0] == "pass"
    reqs[0]["statement"] = "Cancelled appointments show their reason."  # names a value: about them
    env = _split_env(tmp_path, stories, reqs)
    status, _, detail = _outcome(env, "story-split", "story-split.status-values")
    assert status == "fail" and detail.startswith("SCHEDULED, COMPLETED, NO_SHOW (from")
    (tmp_path / "context/data-model.md").unlink()
    assert _outcome(env, "story-split", "story-split.status-values")[0] == "skip"


def test_lists_after() -> None:
    from tsl.harness.skillchecks import owned_lists_after

    assert owned_lists_after(DATA_MODEL, "status") == [
        (["SCHEDULED", "COMPLETED", "CANCELLED", "NO_SHOW"], "appointment")
    ]
    text = "Status is SCHEDULED,\nCOMPLETED, CANCELLED or NO_SHOW. Statuses are Scheduled, Completed and No-show."
    assert lists_after(text, "status") == [["SCHEDULED", "COMPLETED", "CANCELLED", "NO_SHOW"]]
    assert lists_after("The doctor list shows Code, Name and Status.", "status") == []


def test_named_set_forms() -> None:
    text = "\n".join(
        [
            "- S-2 AC1/AC3: counts (S-4 AC1-AC2)",
            "- S-1: column after Status (AC1), reason shown (AC2),",
            "  exactly 60 characters whole (AC4).",
            "- S-3: show '-' (AC1 to AC3)",
            "- S-5/AC01 and REQ-7",
            "- list items carry the reason (S-1, S-6)",
            "- (AC5) alone names no story",
        ]
    )
    items = [f"S-{s}/AC{a}" for s in range(1, 7) for a in range(1, 6)] + ["REQ-7", "REQ-8"]
    assert named_set(items, "/", text) == {
        "S-1/AC1", "S-1/AC2", "S-1/AC4", "S-2/AC1", "S-2/AC3", "S-3/AC1", "S-3/AC2",
        "S-3/AC3", "S-4/AC1", "S-4/AC2", "S-5/AC1", "REQ-7",
    }  # fmt: skip


# ------------------------------------------------------------------ declarations, inputs
def test_plugin_declarations_are_valid() -> None:
    assert (
        validate_declared(
            _checks("unit-test"), {"change", "stories", "test_strategy", "test_layout"}
        )
        == []
    )
    assert validate_declared(_checks("story-split"), {"intent", "glossary"}) == []


def test_validate_rejects_incomplete_new_kinds() -> None:
    doc = {
        "skill": "unit-test",
        "checks": [
            {"id": "unit-test.a", "kind": "named-in", "each": "$.stories[*]"},
            {"id": "unit-test.b", "kind": "values-named", "each": "$.x[*]", "text": "$.t", "values": {"file": "f", "after": "s"}, "when": {"input": "nope", "each": "$.r[*]"}},
            {"id": "unit-test.c", "kind": "values-in-code", "each": "$.s[*]", "items": "$.a[*]", "files": "("},
        ],
    }  # fmt: skip
    errs = validate_declared(doc, {"stories"})
    assert "unit-test.a: kind named-in needs sections" in errs
    assert "unit-test.b: when.input nope is not an input of the skill" in errs
    assert any(e.startswith("unit-test.c: files is not a valid regex") for e in errs)


def test_added_lines_and_code_added_read_the_step_diff(tmp_path: Path) -> None:
    """The lines a code step added, per file, whatever the user's diff.noprefix setting."""
    assert added_lines(
        "diff --git a/x b/x\n--- a/x\n+++ b/x\n@@ -1 +1,2 @@\n old\n+new\n"
        "diff --git a/y b/y\n--- a/y\n+++ /dev/null\n@@ -1 +0,0 @@\n-gone\n"
    ) == {"x": "new"}
    repo = tmp_path / "r"
    repo.mkdir()

    def git(*a: str) -> str:
        return subprocess.run(
            ["git", "-C", str(repo), *a], capture_output=True, text=True, check=True
        ).stdout.strip()

    git("init", "-q")
    git("config", "user.email", "t@example.com")
    git("config", "user.name", "t")
    git("config", "diff.noprefix", "true")
    (repo / "a.test.ts").write_text("old\n")
    git("add", "-A")
    git("commit", "-qm", "base")
    base = git("rev-parse", "HEAD")
    (repo / "a.test.ts").write_text("old\nmake(21)\n")
    git("add", "-A")
    tree = git("write-tree")
    ci = SimpleNamespace(
        product_changes=[{"repo": "r", "base_sha": base, "tree_sha": tree}], clones={"r": repo}
    )
    get = code_added(ci)  # type: ignore[arg-type]
    assert get is not None and get() == {"a.test.ts": "make(21)"}
    assert code_added(SimpleNamespace(product_changes=None, clones={})) is None  # type: ignore[arg-type]


@pytest.mark.parametrize("kind", ["named-in", "values-named", "values-in-code"])
def test_a_broken_declaration_fails_the_check_not_tsl(tmp_path: Path, kind: str) -> None:
    env = CheckEnv({}, "", tmp_path, [], {}, {}, code_added=lambda: {})
    doc = {"checks": [{"id": "unit-test.x", "kind": kind, "gate": "soft"}]}
    out = run_declared(env, doc)
    assert out[0].status == "fail" and out[0].detail.startswith("check error")
