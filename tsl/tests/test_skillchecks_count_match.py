"""The `count-match` kind (SDD-03 §5.2) against status-report's checks, and the rule that a kind
with no check in tsl fails instead of skipping (gates count `skip` as a pass)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tsl.core.jsonio import read_yaml
from tsl.harness.skillchecks import KINDS, RUNS_ELSEWHERE, CheckEnv, _kind_check, run_declared

ROOT = Path(__file__).resolve().parents[2]
STATUS_CHECKS = ROOT / "plugins" / "truminds" / "skills" / "status-report" / "checks.yaml"
# 5 runs: 2 running, 1 paused for input, 0 paused for approval, 2 completed.
STATES = ["RUNNING", "RUNNING", "PAUSED_INPUT", "COMPLETED", "COMPLETED"]
COUNTS = {"runs": 5, "running": 2, "paused_input": 1, "paused_approval": 0, "completed": 2}


def _runs(root: Path, states: list[str] = STATES) -> Path:
    for n, status in enumerate(states, 1):
        p = root / "runs" / f"run_{n:02d}" / "state.json"
        p.parent.mkdir(parents=True)
        p.write_text(json.dumps({"schema": "run-state.v1", "status": status}), encoding="utf-8")
    return root


def _status(root: Path, counts: dict[str, Any]) -> dict[str, str]:
    env = CheckEnv({"schema": "status.v1", "counts": counts}, "", root, [], {})
    out = run_declared(env, dict(read_yaml(STATUS_CHECKS)))
    assert len(out) == 5 and {o.gate for o in out} == {"H2"}
    return {o.id.split(".")[1]: f"{o.status}: {o.detail}".rstrip(": ") for o in out}


def test_status_report_counts_that_equal_the_state_files_pass(tmp_path: Path) -> None:
    assert set(_status(_runs(tmp_path), COUNTS).values()) == {"pass"}


def test_status_report_fails_a_count_the_state_files_contradict(tmp_path: Path) -> None:
    got = _status(_runs(tmp_path), {**COUNTS, "running": 3})
    assert got["running-match"] == (
        "fail: $.counts.running is 3, but 2 files match where status == 'RUNNING'"
    )
    assert got["runs-match"] == "pass"


def test_status_report_fails_a_run_count_that_misses_a_file(tmp_path: Path) -> None:
    got = _status(_runs(tmp_path), {**COUNTS, "runs": 4})
    assert got["runs-match"] == "fail: $.counts.runs is 4, but 5 files match"


def test_status_report_with_no_runs_counts_zero(tmp_path: Path) -> None:
    zero = dict.fromkeys(COUNTS, 0)
    assert set(_status(tmp_path, zero).values()) == {"pass"}


def _check(**over: Any) -> dict[str, Any]:
    c = {"id": "status-report.x", "kind": "count-match", "gate": "H2", "select": "$.n"}
    return {**c, "count_files": "runs/*/state.json", **over}


@pytest.mark.parametrize(
    ("front", "check", "detail"),
    [
        ({"n": "2"}, _check(), "$.n must select one whole number"),
        ({"n": True}, _check(), "$.n must select one whole number"),
        ({}, _check(), "$.n must select one whole number"),
        ({"n": 1}, _check(where="status = RUNNING"), "is not `field == 'value'`"),
        ({"n": 1}, _check(count_files="../runs/*/state.json"), "must stay inside the repo"),
    ],
)
def test_count_match_fails_clearly_on_bad_input(
    tmp_path: Path, front: dict[str, Any], check: dict[str, Any], detail: str
) -> None:
    status, got = _kind_check(CheckEnv(front, "", _runs(tmp_path), [], {}), check)
    assert status == "fail" and detail in got


def test_count_match_fails_on_a_state_file_that_is_not_json(tmp_path: Path) -> None:
    _runs(tmp_path)
    (tmp_path / "runs" / "run_03" / "state.json").write_text("{not json", encoding="utf-8")
    env = CheckEnv({"n": 2}, "", tmp_path, [], {})
    status, detail = _kind_check(env, _check(where="status == 'RUNNING'"))
    assert (status, detail) == ("fail", "runs/run_03/state.json is not valid JSON")


def test_count_match_where_not_equal(tmp_path: Path) -> None:
    env = CheckEnv({"n": 3}, "", _runs(tmp_path), [], {})
    assert _kind_check(env, _check(where="status != 'COMPLETED'")) == ("pass", "")


def test_only_kinds_that_run_elsewhere_skip() -> None:
    assert RUNS_ELSEWHERE <= KINDS
    for kind in sorted(KINDS):
        status, detail = _kind_check(CheckEnv({}, "", ROOT, [], {}), {"id": "x.y", "kind": kind})
        if kind in RUNS_ELSEWHERE:
            assert status == "skip", kind
        else:
            assert status == "fail" and "has no check in tsl" not in detail, (kind, detail)


def test_a_kind_without_a_check_in_tsl_fails_instead_of_skipping() -> None:
    status, detail = _kind_check(CheckEnv({}, "", ROOT, [], {}), {"id": "x.y", "kind": "new-kind"})
    assert (status, detail) == ("fail", "kind new-kind has no check in tsl")
