"""The `enum-file` check kind (SDD-03 §5.2) and its one user, accessibility-review.wcag-map (#7)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from tsl.core.jsonio import read_yaml
from tsl.harness.skillchecks import CheckEnv, allowlist, run_declared, validate_declared

ROOT = Path(__file__).resolve().parents[2]
SKILLS = ROOT / "plugins" / "truminds" / "skills"
WCAG = "wcag21-aa-criteria.txt"
# Criterion id -> level, from the shipped list, so test findings carry the criterion's real level.
# Criteria not in the list get "AA"; the check fails them on the id anyway.
LEVEL = allowlist(WCAG) or {}


def _checks(skill: str) -> dict[str, Any]:
    return dict(read_yaml(SKILLS / skill / "checks.yaml"))


def _outcome(check: dict[str, Any], front: dict[str, Any]) -> Any:
    env = CheckEnv(front, "", ROOT, [], {})
    [out] = run_declared(env, {"skill": "accessibility-review", "checks": [check]})
    return out


def _wcag_map() -> dict[str, Any]:
    [c] = [c for c in _checks("accessibility-review")["checks"] if c["id"].endswith("wcag-map")]
    return dict(c)


def _a11y(*wcag: str) -> dict[str, Any]:
    findings = [
        {"id": f"AF-{i}", "wcag": w, "level": LEVEL.get(w, "AA"), "cites": [f"d.fig#node:1:{i}"]}
        for i, w in enumerate(wcag, 1)
    ]
    return {"schema": "a11y.v1", "findings": findings}


def test_wcag_allowlist_ships_the_49_level_a_and_aa_criteria() -> None:
    ids = allowlist(WCAG)
    assert ids is not None, f"{WCAG} is not shipped in tsl"
    assert len(ids) == 49
    assert {"1.1.1", "1.4.3", "1.4.10", "2.5.4", "4.1.3"} <= ids.keys()  # A, AA and new in 2.1
    assert not {"1.4.6", "2.2.3", "3.1.5"} & ids.keys()  # level AAA
    assert "4.1.1" not in ids  # obsolete in the WCAG 2.1 errata; markup only
    assert sorted(ids.values()) == ["A"] * 29 + ["AA"] * 20
    assert (ids["1.1.1"], ids["1.4.3"], ids["2.1.4"], ids["4.1.3"]) == ("A", "AA", "A", "AA")


@pytest.mark.parametrize("wcag", ["1.4.3", "1.4.10", "4.1.2"])
def test_wcag_map_passes_for_a_level_a_or_aa_criterion(wcag: str) -> None:
    out = _outcome(_wcag_map(), _a11y("1.1.1", wcag))
    assert (out.gate, out.status) == ("H2", "pass"), out.detail


@pytest.mark.parametrize(
    ("wcag", "why"),
    [
        ("9.9.9", "no such criterion"),
        ("1.4.6", "level AAA"),
        ("2.5.5", "level AAA, new in 2.1"),
        ("4.1.1", "obsolete, and about markup a design review never sees"),
    ],
)
def test_wcag_map_fails_for_a_criterion_outside_wcag_21_a_and_aa(wcag: str, why: str) -> None:
    out = _outcome(_wcag_map(), _a11y("1.4.3", wcag))
    assert (out.gate, out.status) == ("H2", "fail"), why
    assert wcag in out.detail and WCAG in out.detail


@pytest.mark.parametrize(("wcag", "level", "real"), [("1.4.3", "A", "AA"), ("1.1.1", "AA", "A")])
def test_wcag_map_fails_when_the_level_is_not_the_criterions_level(
    wcag: str, level: str, real: str
) -> None:
    front = _a11y("1.4.10", wcag)
    front["findings"][1]["level"] = level
    out = _outcome(_wcag_map(), front)
    assert (out.gate, out.status) == ("H2", "fail")
    assert out.detail == f"{wcag}: level {level!r}, but {WCAG} lists {real!r}"


def test_enum_file_without_value_checks_plain_values() -> None:
    """A check that selects plain values (no `value`/`tag`) still works, e.g. $.findings[*].wcag."""
    check = {k: v for k, v in _wcag_map().items() if k not in ("value", "tag")}
    check["select"] = "$.findings[*].wcag"
    assert _outcome(check, _a11y("1.4.3")).status == "pass"
    assert _outcome(check, _a11y("9.9.9")).status == "fail"


def test_enum_file_never_skips() -> None:
    """Before #7 the kind fell through to `skip`, which gates count as a pass."""
    assert _outcome(_wcag_map(), _a11y("9.9.9")).status != "skip"


def test_enum_file_fails_when_the_allowlist_is_not_shipped() -> None:
    check = {**_wcag_map(), "file": "no-such-list.txt"}
    out = _outcome(check, _a11y("1.4.3"))
    assert out.status == "fail"
    assert "no-such-list.txt is not shipped" in out.detail


def test_enum_file_fails_clearly_without_a_file() -> None:
    check = {k: v for k, v in _wcag_map().items() if k != "file"}
    out = _outcome(check, _a11y("1.4.3"))
    assert (out.status, out.detail) == ("fail", "enum-file check needs a `file`")


@pytest.mark.parametrize(
    "name",
    ["../rules/" + WCAG, "rules/" + WCAG, "/etc/passwd", "secrets.v1.yaml", WCAG + "\n", ""],
)
def test_allowlist_reads_only_txt_files_in_the_rules_folder(name: str) -> None:
    assert allowlist(name) is None


def test_validate_rejects_an_enum_file_check_whose_allowlist_is_missing() -> None:
    doc = _checks("accessibility-review")
    assert validate_declared(doc) == []
    doc["checks"] = [{**_wcag_map(), "file": "no-such-list.txt"}]
    assert validate_declared(doc) == [
        "accessibility-review.wcag-map: allowlist no-such-list.txt is not shipped in tsl"
    ]


def test_validate_rejects_an_enum_file_check_without_a_file() -> None:
    doc = _checks("accessibility-review")
    doc["checks"] = [{k: v for k, v in _wcag_map().items() if k != "file"}]
    assert validate_declared(doc) == [
        "accessibility-review.wcag-map: enum-file check needs a `file`"
    ]
