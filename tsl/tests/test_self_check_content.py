"""Content self-check rules (harness/content.py, roadmap A3) on cases from the team's runs.

Each case is cut down from a reviewer finding that cost a `split` or `ut` retry on 0.1.7
(HMS-23 to HMS-33). Pure functions: no run, no repo."""

from __future__ import annotations

from typing import Any

from tsl.harness import content as C

STATUSES = ["SCHEDULED", "COMPLETED", "CANCELLED", "NO_SHOW"]


def _story(sid: str, trace: list[str], *acs: str) -> dict[str, Any]:
    return {
        "id": sid,
        "title": f"Story {sid}",
        "trace": trace,
        "acceptance_criteria": [{"id": f"AC{i}", "text": t} for i, t in enumerate(acs, 1)],
    }


def _req(rid: str, statement: str, status: str = "known") -> dict[str, Any]:
    return {"id": rid, "status": status, "statement": statement}


def _split(stories: list[dict[str, Any]], reqs: list[dict[str, Any]], **kw: Any) -> C.Facts:
    f = C.Facts("stories.v1", {"stories": stories}, "", intent={"requirements": reqs})
    f.status_sets = kw.get("status_sets", [STATUSES])
    f.answers = kw.get("answers", [])
    return f


def _ids(items: list[dict[str, str]]) -> list[str]:
    return [i["id"] for i in items]


def _detail(items: list[dict[str, str]], iid: str) -> str:
    return " || ".join(i["detail"] for i in items if i["id"] == iid)


# ------------------------------------------------------------------------------- parsing
def test_status_sets_come_from_a_status_sentence_and_drop_subsets() -> None:
    data_model = (
        "An appointment links one doctor and one patient. Status is SCHEDULED,\n"
        "COMPLETED, CANCELLED or NO_SHOW; a cancellation reason exists exactly when CANCELLED."
    )
    intent = "Statuses are Scheduled, Completed and No-show for this list."
    assert C.status_sets([data_model, intent]) == [STATUSES]
    assert C.status_sets(["The doctor list shows Code, Name and Status."]) == []


def test_status_names_in_prose_need_a_capital_but_not_in_code() -> None:
    assert C.statuses_in("Given a No-show and a Scheduled appointment", STATUSES) == [
        "SCHEDULED",
        "NO_SHOW",
    ]
    assert C.statuses_in("Given an appointment scheduled for 10:00", STATUSES) == []
    assert C.status_pattern("NO_SHOW", code=True).search("status: 'no_show'")


def test_ac_refs_read_every_form_the_runs_used() -> None:
    text = "\n".join(
        [
            "- S-2 AC1/AC3: counts (S-4 AC1-AC2)",
            "- S-1: column after Status (AC1), reason shown (AC2),",
            "  exactly 60 characters whole (AC4).",
            "- S-3: Scheduled, Completed, No-show show '-' (AC1 to AC3)",
            "- list items carry the reason (S-1, S-3)",
            "- (AC5) alone names no story",
        ]
    )
    assert C.ac_refs(text) == {
        ("S-2", "AC1"),
        ("S-2", "AC3"),
        ("S-4", "AC1"),
        ("S-4", "AC2"),
        ("S-1", "AC1"),
        ("S-1", "AC2"),
        ("S-1", "AC4"),
        ("S-3", "AC1"),
        ("S-3", "AC2"),
        ("S-3", "AC3"),
    }


def test_listed_terms() -> None:
    statement = "The Works on filter combines with search and the department, specialization and status filters."
    assert "specialization" in C.listed_terms(statement)
    assert C.listed_terms("Counts follow the doctor and patient filters.") == ["doctor", "patient"]
    assert C.listed_terms("going back or opening a copied link shows it") == []


def test_values_of_an_ac() -> None:
    assert C.values_of(
        "Given 21 matching appointments (S-2 AC1), when page 2 opens at 09:30, then the 21st shows"
    ) == ["09:30", "21"]
    assert C.values_of("Given one appointment, when REQ-4 applies, then it shows") == []


# --------------------------------------------------------------------------- story-split
def test_split_status_partition_with_only_one_status_seeded_hms23() -> None:
    """HMS-23 split a1 F-1: S-2 AC1 seeds only Scheduled appointments."""
    f = _split(
        [
            _story(
                "S-2", ["REQ-4"], "Given 2 Scheduled appointments today, when ..., then booked is 2"
            )
        ],
        [_req("REQ-4", "Booked and free slots are counted by the same logic as the day schedule.")],
    )
    fix, check = C.story_split(f)
    assert fix == []
    d = _detail(check, "S-2")
    assert "SCHEDULED" in d and "COMPLETED, CANCELLED, NO_SHOW have none" in d


def test_split_no_status_item_when_the_reqs_do_not_partition() -> None:
    f = _split(
        [
            _story(
                "S-1", ["REQ-2"], "Given a Cancelled appointment, when ..., then its reason shows"
            )
        ],
        [_req("REQ-2", "The column comes after the Status column.")],
    )
    assert "S-1" not in _ids(C.story_split(f)[1])


def test_split_boundary_and_order_on_the_req_hms23() -> None:
    """HMS-23 split a1 F-2: 'starts after now' with no AC at exactly now."""
    f = _split(
        [
            _story(
                "S-2", ["REQ-6"], "Given free slots at 10:00 and 10:15, when ..., then 10:15 shows"
            )
        ],
        [_req("REQ-6", "The next free slot is the earliest free slot that starts after now.")],
    )
    d = _detail(C.story_split(f)[1], "REQ-6")
    assert 'boundary ("after now")' in d and 'order ("next")' in d


def test_split_no_boundary_or_order_for_position_or_truncation() -> None:
    f = _split(
        [_story("S-1", ["REQ-2", "REQ-5", "REQ-8"], "Given a reason, when ..., then it shows")],
        [
            _req("REQ-2", "The column comes after the Status column, next to the total."),
            _req("REQ-5", "A long reason shows its first 60 characters."),
            _req("REQ-8", "The four counts add up to the total."),
        ],
        status_sets=[],
    )
    d = " ".join(i["detail"] for i in C.story_split(f)[1])
    assert "boundary" not in d and "order" not in d


def test_split_listed_filter_missing_from_the_acs_hms28() -> None:
    """HMS-28 split a1 F-3: REQ-7 names specialization; S-3 has no AC for it."""
    f = _split(
        [
            _story(
                "S-3",
                ["REQ-7"],
                "Given search 'Rao' and Monday, when ..., then only Dr Rao shows",
                "Given department Cardiology and Monday, when ..., then ...",
                "Given status Inactive and Monday, when ..., then ...",
            )
        ],
        [
            _req(
                "REQ-7",
                "The Works on filter combines with search and the department, specialization and status filters.",
            )
        ],
        status_sets=[],
    )
    d = _detail(C.story_split(f)[1], "REQ-7")
    assert "`specialization`" in d and "`department`" not in d
    assert "an item matches twice" in d  # HMS-28 F-2: a join lists a doctor twice


def test_split_default_value_hms26() -> None:
    """HMS-26 split a1 F-1: the AC uses the default zone, so a hard-coded zone passes."""
    f = _split(
        [_story("S-1", ["REQ-9"], "Given timeZone Asia/Kolkata at 01:00, when ..., then ...")],
        [_req("REQ-9", "Dates are shown in the hospital time zone read from Settings.")],
        status_sets=[],
    )
    assert "non-default value" in _detail(C.story_split(f)[1], "REQ-9")


def test_split_local_date_only_without_clock_times() -> None:
    reqs = [_req("REQ-4", "The range counts whole hospital-local days.")]
    no_time = _split(
        [_story("S-2", ["REQ-4"], "Given one on the last day, when ..., then counted")], reqs
    )
    with_time = _split(
        [_story("S-2", ["REQ-4"], "Given one at 23:45 on the last day, when ...")], reqs
    )
    assert "local date" in _detail(C.story_split(no_time)[1], "REQ-4")
    assert "local date" not in _detail(C.story_split(with_time)[1], "REQ-4")


def test_split_answers_name_the_options_not_chosen_hms23() -> None:
    """HMS-23 split a1 F-1: the AC passes the rejected A-02 option 'Scheduled only'."""
    answers = [
        {
            "id": "A-02",
            "step": "req",
            "question": "Which of today's appointments count as booked?",
            "options": "Same as day schedule code | Scheduled only | Scheduled, Completed, No-show",
            "answer": "Same as day schedule code",
        }
    ]
    f = _split([_story("S-1", ["REQ-1"], "Given ..., when ..., then ...")], [], answers=answers)
    d = _detail(C.story_split(f)[1], "A-02")
    assert '"Scheduled only"' in d and "not-chosen option" in d and "AC" in d


def test_split_unknown_and_untraced_reqs_get_no_item() -> None:
    f = _split(
        [_story("S-1", ["REQ-1"], "Given ..., when ..., then ...")],
        [_req("REQ-2", "Counts are unchanged.", "unknown"), _req("REQ-3", "Counts are unchanged.")],
    )
    assert _ids(C.story_split(f)[1]) == []


def test_check_items_are_capped() -> None:
    reqs = [_req(f"REQ-{i}", "The rest of the page is unchanged.") for i in range(1, 40)]
    stories = [_story("S-1", [r["id"] for r in reqs], "Given ..., when ..., then ...")]
    check = C.story_split(_split(stories, reqs, status_sets=[]))[1]
    assert len(check) == C.MAX_CHECK and check[-1]["id"] == "more"


# ----------------------------------------------------------------------------- unit-test
def _ut(body: str, trace: list[str], stories: list[dict[str, Any]], **kw: Any) -> C.Facts:
    f = C.Facts("ut-result.v1", {"trace": trace}, body, stories={"stories": stories})
    f.status_sets = kw.get("status_sets", [STATUSES])
    f.change = kw.get("change")
    f.tests = kw.get("tests")
    f.answers = kw.get("answers", [])
    return f


UT_BODY = """# Unit tests: HMS-31
## Summary
Tests for the appointment page.
## Tests
- web/src/__tests__/AppointmentDetailPage.test.tsx:
  - REQ-11: a Scheduled appointment keeps its actions (S-4 AC1).
  - REQ-11: a Cancelled appointment keeps its reason (S-4 AC3).
  - REQ-1 error: a failed request shows the error.
## Known
- S-4: covered.
## Unknown
None
"""
S4 = _story(
    "S-4",
    ["REQ-11"],
    "Given a Scheduled appointment, when ..., then unchanged",
    "Given a Completed appointment, when ..., then unchanged",
    "Given a Cancelled appointment, when ..., then unchanged",
    "Given a No-show appointment, when ..., then unchanged",
)


def test_ut_every_ac_is_named_on_a_tests_line_hms31() -> None:
    """HMS-31 ut a1 F-2: S-4 listed as covered; AC2 (Completed) and AC4 (No-show) untested."""
    fix, _ = C.unit_test(_ut(UT_BODY, ["REQ-11"], [S4]))
    assert _ids(fix) == ["S-4"]
    assert fix[0]["kind"] == "content"
    assert fix[0]["detail"].startswith("S-4 AC2, S-4 AC4: no Tests line names it")


def test_ut_an_ac_listed_under_unknown_is_excused() -> None:
    body = UT_BODY.replace(
        "## Unknown\nNone", "## Unknown\n- U-1: S-4 AC2 and S-4 AC4 need a browser."
    )
    assert C.unit_test(_ut(body, ["REQ-11"], [S4]))[0] == []


def test_ut_req_dropped_from_trace_hms28() -> None:
    """HMS-28 ut a1 F-1: REQ-12 traced by S-5 has no test and is dropped from trace."""
    s5 = _story("S-5", ["REQ-12"], "Given ..., when ..., then ...")
    body = UT_BODY.replace("(S-4 AC1)", "(S-4 AC1, S-5 AC1)")
    fix, _ = C.unit_test(_ut(body, ["REQ-11"], [S4, s5]))
    assert "REQ-12" in _ids(fix)
    assert "REQ-12" not in _ids(C.unit_test(_ut(body, ["REQ-11", "REQ-12"], [S4, s5]))[0])


def test_ut_status_and_values_missing_from_the_test_code_hms30() -> None:
    """HMS-30 ut a1 F-1: S-2 AC1 needs the 21st row; the fixture has 5 (no 21 anywhere)."""
    s2 = _story(
        "S-2",
        ["REQ-4"],
        "Given 21 matching Scheduled appointments, when page 2 opens, then the 21st shows",
    )
    body = UT_BODY.replace("(S-4 AC1)", "(S-4 AC1, S-2 AC1)")
    tests = C.TestCode(
        {"api/test/x.test.ts": "it('REQ-4 page 2', () => {})"},
        "const rows = make(5, { status: 'SCHEDULED' });",
    )
    check = C.unit_test(_ut(body, ["REQ-4", "REQ-11"], [s2, S4], tests=tests))[1]
    assert "21" in _detail(check, "S-2 AC1")
    d4 = _detail(check, "S-4")
    assert "COMPLETED, CANCELLED, NO_SHOW" in d4  # HMS-31 ut F-2: partitions not in the code
    tests.added = "const rows = make(21, {status: 'SCHEDULED'}); 'COMPLETED' 'cancelled' NoShow"
    check = C.unit_test(_ut(body, ["REQ-4", "REQ-11"], [s2, S4], tests=tests))[1]
    assert "S-2 AC1" not in _ids(check) and "S-4" not in _ids(check)


def test_ut_changed_file_with_no_test_and_req_names_hms24() -> None:
    """HMS-24 ut a1 F-1: the page wiring in DoctorDetailPage.tsx had no test."""
    change = {
        "code": [
            {
                "files": [
                    "web/src/pages/DoctorDetailPage.tsx",
                    "api/src/repositories/patientRepo.ts",
                    "web/src/types.ts",
                    "api/test/patients.test.ts",
                ]
            }
        ]
    }
    tests = C.TestCode(
        {"api/test/patients.test.ts": "import { patientRepo } ...\nit('REQ-1 ...')"}, ""
    )
    check = C.unit_test(_ut(UT_BODY, ["REQ-1", "REQ-11"], [S4], change=change, tests=tests))[1]
    ids = _ids(check)
    assert "web/src/pages/DoctorDetailPage.tsx" in ids
    assert "api/src/repositories/patientRepo.ts" not in ids and "web/src/types.ts" not in ids
    assert "REQ-11" in ids and "REQ-1" not in ids  # tests are named after REQs here


def test_ut_error_path_and_answers() -> None:
    body = UT_BODY.replace("  - REQ-1 error: a failed request shows the error.\n", "")
    answers = [
        {
            "id": "A-02",
            "step": "design",
            "question": "Where?",
            "options": "",
            "answer": "Own queries",
        }
    ]
    check = C.unit_test(_ut(body, ["REQ-11"], [S4], answers=answers))[1]
    assert "Tests" in _ids(check)
    assert _ids(check)[-1] == "A-02" and "Name the test" in _detail(check, "A-02")
    assert "Tests" not in _ids(C.unit_test(_ut(UT_BODY, ["REQ-11"], [S4]))[1])


def test_odd_input_gives_no_items_and_no_error() -> None:
    for schema in ("stories.v1", "ut-result.v1"):
        f = C.Facts(schema, {"stories": "x", "trace": None}, "", intent={"requirements": [1]})
        f.stories = {"stories": [{"id": 3}]}
        assert C.items(f) == ([], [])
    assert C.items(C.Facts("intent.v1", {}, "")) == ([], [])


def test_test_code_reads_the_steps_test_files_whatever_the_git_diff_prefix(tmp_path: Any) -> None:
    """unit-test's test files since the last checkpoint: full text, and only the added lines.
    A user's diff.noprefix must not hide the file names."""
    import subprocess
    from types import SimpleNamespace

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
    (repo / "api/test").mkdir(parents=True)
    (repo / "api/test/a.test.ts").write_text("it('REQ-1 old', () => {})\n")
    (repo / "api/src").mkdir(parents=True)
    (repo / "api/src/a.ts").write_text("export const a = 1\n")
    git("add", "-A")
    git("commit", "-qm", "base")
    base = git("rev-parse", "HEAD")
    (repo / "api/test/a.test.ts").write_text(
        "it('REQ-1 old', () => {})\nit('REQ-2 new', () => 21)\n"
    )
    (repo / "api/test/b.test.ts").write_text("it('REQ-3', () => 'NO_SHOW')\n")
    (repo / "api/src/a.ts").write_text("export const a = 2\n")
    ctx = SimpleNamespace(
        state={"branch": {"r": {"base_sha": base}}},
        comp=SimpleNamespace(product_clone=lambda name: repo),
    )
    tc = C.test_code(ctx)
    assert sorted(tc.files) == ["api/test/a.test.ts", "api/test/b.test.ts"]
    assert "REQ-1 old" in tc.files["api/test/a.test.ts"]
    assert "REQ-2 new" in tc.added and "NO_SHOW" in tc.added
    assert "REQ-1 old" not in tc.added and "export const" not in tc.added
