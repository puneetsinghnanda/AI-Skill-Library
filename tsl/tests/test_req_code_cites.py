"""C2: requirement-review may cite product code (`<repo>:<path>#L<n>`), as its SKILL.md says.

Runs HMS-28 and HMS-33 lost a req retry to RR-C05 rejecting exactly such cites.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tsl.harness.skillchecks import CheckEnv, c_cites_present

REPOS = frozenset({"sample-system"})


def _front(*cites: str) -> dict[str, Any]:
    return {"claims": [{"id": "C3", "text": "x", "cites": list(cites)}]}


def _check(front: dict[str, Any], root: Path, repos: frozenset[str] = REPOS) -> str | None:
    return c_cites_present(CheckEnv(front, "", root, [], {}, repos=repos), {})


def test_product_code_cite_passes(tmp_path: Path) -> None:
    front = _front("sample-system:db/migrations/20261016T090100__create_doctors.sql#L4")
    assert _check(front, tmp_path) is None


def test_product_code_cite_as_dict_passes(tmp_path: Path) -> None:
    ref = {"ref": "sample-system:web/src/pages/DashboardPage.tsx#L12", "quote": "x"}
    assert _check({"claims": [{"id": "C7", "text": "x", "cites": [ref]}]}, tmp_path) is None


def test_unknown_repo_is_still_rejected(tmp_path: Path) -> None:
    detail = _check(_front("other-repo:web/src/pages/DashboardPage.tsx#L12"), tmp_path)
    assert "not a declared input" in str(detail)


def test_bare_code_path_is_still_rejected(tmp_path: Path) -> None:
    detail = _check(_front("web/src/pages/DashboardPage.tsx#L12"), tmp_path)
    assert "not a declared input" in str(detail)


def test_without_repos_code_cites_are_rejected_as_before(tmp_path: Path) -> None:
    front = _front("sample-system:web/src/pages/DashboardPage.tsx#L12")
    assert "not a declared input" in str(_check(front, tmp_path, frozenset()))


def test_context_cite_still_passes(tmp_path: Path) -> None:
    assert _check(_front("context/glossary.md#order"), tmp_path) is None


# --- a proposed default must cite what it rests on (RR-C08 default_sourced) ---------------

RUN = "run_01M820V4J0VSJHKNZZ5VK0BT2Y"
TICKET = f"artifacts/HMS-31/{RUN}/ticket.md#L25"


def _questions(evidence: list[str], default: str | None = "Name as is") -> dict[str, Any]:
    q = {"id": "Q-01", "ask": "tech lead", "why": "w", "evidence": evidence, "default": default}
    return {"questions": [q], "unknowns": [{"id": "U-1", "question": "Q-01"}]}


def _linked(front: dict[str, Any], root: Path, sourced: bool = True) -> str | None:
    from tsl.harness.skillchecks import c_questions_linked

    w = {"default_sourced": True} if sourced else {}
    return c_questions_linked(CheckEnv(front, "", root, [], {}, repos=REPOS), w)


def test_default_resting_on_the_ticket_alone_fails(tmp_path: Path) -> None:
    assert "no evidence in the product code" in str(_linked(_questions([TICKET]), tmp_path))


def test_default_citing_product_code_passes(tmp_path: Path) -> None:
    code = "sample-system:web/src/pages/DoctorDetailPage.tsx#L72"
    assert _linked(_questions([TICKET, code]), tmp_path) is None


def test_default_citing_the_prd_passes(tmp_path: Path) -> None:
    assert _linked(_questions(["sample-system:docs/PRD.md#L192"]), tmp_path) is None


def test_default_citing_context_passes(tmp_path: Path) -> None:
    assert _linked(_questions(["context/intent-baseline.md#constraints"]), tmp_path) is None


def test_default_citing_an_earlier_answer_passes(tmp_path: Path) -> None:
    assert _linked(_questions([f"runs/{RUN}/ide-answers.md#a-01"]), tmp_path) is None


def test_question_without_default_needs_no_source(tmp_path: Path) -> None:
    front = _questions([TICKET], default=None)
    front["questions"][0]["blocking"] = True
    assert _linked(front, tmp_path) is None


def test_without_the_option_ticket_only_default_passes_as_before(tmp_path: Path) -> None:
    assert _linked(_questions([TICKET]), tmp_path, sourced=False) is None
