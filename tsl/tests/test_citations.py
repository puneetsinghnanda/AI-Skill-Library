"""Citation grammar, resolution, matching and the dropped-finding rule (SDD-03 §8)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from helpers import git
from tsl.core.config import effective_bands
from tsl.harness import citations as cit
from tsl.harness.decide import DecideInput, evaluate

REPOS = {"orders-api"}


@pytest.mark.parametrize(
    ("raw", "ok"),
    [
        ("context/data-model.md#orders", True),
        ("orders-api:src/routes/orders.js#L40-L52", True),
        ("orders-api:src/routes/orders.js#L40", True),
        ("orders-api:src/routes/orders.js#sym:getOrder", True),
        ("orders-api:package.json#key:dependencies.express", True),
        ("design.fig#node:12-34", True),
        ("context/generated/db-schema.json#table:orders", True),
        ("unknown-repo:src/a.js#L1", False),
        ("/etc/passwd#L1", False),
        ("context/../secrets.md#x", False),
        ("context\\win.md#x", False),
        ("context/a.md", False),
        ("context/a.md#Not_A_Slug", False),
        ("orders-api:src/a.js#L10-L300", False),
        ("context/a b.md#x", False),
    ],
)
def test_grammar(raw: str, ok: bool) -> None:
    assert (cit.parse(raw, REPOS) is not None) == ok


def test_quote_matching() -> None:
    span = "router.get('/:id', getOrder);\n  return db.query('SELECT * FROM order_archive WHERE id = $1')"
    assert cit.quote_matches("db.query('SELECT * FROM order_archive", span)
    assert cit.quote_matches("db.query(  'SELECT *   FROM order_archive", span)  # whitespace
    assert cit.quote_matches("db.query('SELECT * FROM order_archiv", span)  # tiny drift
    assert not cit.quote_matches("reads the events table for history", span)  # reworded
    assert not cit.quote_matches("", span)


def test_element_matching() -> None:
    assert cit.element_matches(["order_events"], "DELETE FROM order_events WHERE")
    assert not cit.element_matches(["order_events"], "DELETE FROM order_events_old")
    assert cit.elements_of({"text": "Kept `24 hours` in `order_events`"}) == [
        "24 hours",
        "order_events",
    ]
    assert cit.elements_of({"element": "x", "text": "`y`"}) == ["x"]


@pytest.fixture
def repo(tmp_path: Path) -> tuple[Path, Path, str]:
    comp = tmp_path / "companion"
    (comp / "context").mkdir(parents=True)
    (comp / "context" / "data-model.md").write_text(
        "# Data model {#data-model}\n\n## Orders {#orders}\nOrders live in `orders`.\n\n"
        "## Retention {#retention}\nOrder events are kept 24 hours.\n"
    )
    (comp / "cfg.yaml").write_text("limits:\n  page_size: 20\n")
    (comp / ".env").write_text("X=1\n")
    clone = tmp_path / "orders-api"
    clone.mkdir()
    git(clone, "init", "-q", "-b", "main")
    lines = [f"// line {i}" for i in range(1, 60)]
    lines[44] = "  return db.query('SELECT * FROM order_archive WHERE id = $1');"
    lines[10] = "function getOrder(req, res) {"
    lines[11] = "  return 1;"
    lines[12] = "}"
    (clone / "src").mkdir()
    (clone / "src" / "orders.js").write_text("\n".join(lines) + "\n")
    git(clone, "add", "-A")
    git(clone, "commit", "-qm", "init")
    sha = git(clone, "rev-parse", "HEAD")
    (clone / "src" / "orders.js").write_text("changed after the pack\n")  # working tree ignored
    return comp, clone, sha


def _verify(
    r: cit.Resolver, raw: str, quote: str | None = None, elements: list[str] | None = None
) -> cit.CiteResult:
    c = cit.parse(raw, REPOS)
    assert c is not None
    return cit.verify(c, quote, elements or [], r)


def test_resolution(repo: tuple[Path, Path, str]) -> None:
    comp, clone, sha = repo
    r = cit.Resolver(comp, {"orders-api": clone}, {"orders-api": sha})
    assert _verify(r, "context/data-model.md#retention", "kept 24 hours").ok
    assert _verify(r, "context/data-model.md#orders", None, ["orders"]).ok
    assert _verify(r, "context/data-model.md#orders", None, []).reason == "unverifiable: no element"
    assert _verify(r, "context/data-model.md#nope", "x").reason == "anchor not found"
    assert _verify(r, "context/missing.md#x", "x").reason == "path not found"
    assert _verify(r, ".env#L1", "X").reason == "read-denied path"
    # product repo is read at the pinned SHA, with +-3 lines of drift tolerance
    assert _verify(r, "orders-api:src/orders.js#L42", "FROM order_archive").ok
    assert not _verify(r, "orders-api:src/orders.js#L30", "FROM order_archive").ok
    assert _verify(r, "orders-api:src/orders.js#L500", "x").reason == "line out of range"
    assert _verify(r, "orders-api:src/history.js#L1", "x").reason == "path not found"
    assert _verify(r, "orders-api:src/orders.js#sym:getOrder", "return 1").ok
    assert _verify(r, "cfg.yaml#key:limits.page_size", "20").ok
    assert _verify(r, "design.fig#node:1-2", "anything").format_only
    no_sha = cit.Resolver(comp, {"orders-api": clone}, {})
    assert _verify(no_sha, "orders-api:src/orders.js#L42", "x").reason == "repo not available"


def _decide(
    comp: Path,
    clone: Path,
    sha: str,
    findings: list[dict[str, Any]],
    claims: list[dict[str, Any]] | None = None,
) -> Any:
    review = {
        "status": "ok",
        "rubric_score": 5.0,
        "rubric_items": [{"id": "R1", "score": 5}],
        "findings": findings,
        "claims_checked": [],
        "questions": [],
    }
    gates: list[dict[str, Any]] = [
        {"id": g, "pass": True, "status": "pass", "codes": [], "detail": ""}
        for g in ("H1", "H2", "H3", "H4", "H5", "H6", "H7")
    ]
    return evaluate(
        DecideInput(
            checks={"gates": gates, "soft": [], "product_changes": None},
            review=review,
            front={"claims": claims or []},
            rubric={"criteria": [{"id": "R1", "weight": 1}]},
            limits={"checks": 2, "review": 2, "verifier": 3},
            used={"checks": 0, "review": 0, "verifier": 0},
            thresholds=effective_bands(None, None),
            s5="fresh",
            requires_fresh_pack=True,
            is_code=False,
            change_limits={"lines": 400, "files": 15, "sensitive_paths": []},
            resolver=cit.Resolver(comp, {"orders-api": clone}, {"orders-api": sha}),
            repos=REPOS,
        )
    )


def test_findings_kept_and_dropped(repo: tuple[Path, Path, str]) -> None:
    comp, clone, sha = repo

    def f(fid: str, ref: str, quote: str, sev: str = "minor") -> dict[str, Any]:
        return {
            "id": fid,
            "severity": sev,
            "category": "correctness",
            "text": "t",
            "cites": [{"ref": ref, "quote": quote}],
        }

    findings = [
        f("F-1", "orders-api:src/orders.js#L40-L52", "db.query('SELECT * FROM order_archive"),
        f("F-2", "orders-api:src/history.js#L10", "anything"),
        f("F-3", "context/data-model.md#retention", "kept for 90 days"),
        f("F-4", "bad ref", "x"),
        {
            **f("F-5", "context/data-model.md#retention", "kept 24 hours"),
            "cites": [
                {"ref": "context/data-model.md#retention", "quote": "kept 24 hours"},
                {"ref": "context/data-model.md#orders", "quote": "invented"},
            ],
        },
    ]
    d = _decide(comp, clone, sha, findings)
    assert [k["id"] for k in d.kept] == ["F-1"]
    reasons = {x["id"]: x["reason"] for x in d.dropped}
    assert reasons["F-2"] == "path not found"
    assert reasons["F-3"] == "quote not found"
    assert reasons["F-4"].startswith("bad citation format")
    assert reasons["F-5"] == "quote not found"  # every citation must verify
    assert d.signals["S1"] == 0.2  # 1 kept of 5 findings, no claims


def test_claims_verified_and_unsupported(repo: tuple[Path, Path, str]) -> None:
    comp, clone, sha = repo
    claims: list[dict[str, Any]] = [
        {
            "id": "C1",
            "text": "Events kept `24 hours`",
            "cites": ["context/data-model.md#retention"],
        },
        {"id": "C2", "text": "Kept `90 days`", "cites": ["context/data-model.md#retention"]},
        {"id": "C3", "text": "No citation"},
    ]
    d = _decide(comp, clone, sha, [], claims)
    assert (d.claims_total, d.claims_verified) == (3, 1)
    assert d.signals["S1"] == round(1 / 3, 4)
