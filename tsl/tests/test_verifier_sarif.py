"""SARIF reports keep only the rules their results use (roadmap C3, run HMS-28).

Semgrep listed all 1,074 rules of its ruleset in sast.sarif: 2.0 of the file's 2.4 MB, for 4
results. The file was over citations.MAX_BYTES, so a reviewer's cite into it failed E-REV-05.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from tsl.core.hashing import sha256_file
from tsl.harness.citations import MAX_BYTES
from tsl.harness.verifier import DockerVerifier, compact_sarif


def _rule(rid: str, pad: int = 0) -> dict[str, Any]:
    return {"id": rid, "shortDescription": {"text": rid}, "help": {"text": "x" * pad}}


def _sarif(rules: list[dict[str, Any]], results: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "version": "2.1.0",
        "runs": [{"tool": {"driver": {"name": "t", "rules": rules}}, "results": results}],
    }


def _result(**ref: Any) -> dict[str, Any]:
    loc = {"physicalLocation": {"artifactLocation": {"uri": "/src/api/src/app.ts"}}}
    return {"message": {"text": "m"}, "locations": [loc], **ref}


def _write(path: Path, doc: dict[str, Any]) -> Path:
    path.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    return path


def _run(path: Path) -> dict[str, Any]:
    run: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))["runs"][0]
    return run


def test_rules_without_results_are_dropped_results_kept(tmp_path: Path) -> None:
    """Semgrep form: results name their rule by ruleId only."""
    results = [_result(ruleId="r2"), _result(ruleId="r4"), _result(ruleId="r2")]
    p = _write(tmp_path / "sast.sarif", _sarif([_rule(f"r{i}") for i in range(6)], results))
    assert compact_sarif(p) is True
    run = _run(p)
    assert [r["id"] for r in run["tool"]["driver"]["rules"]] == ["r2", "r4"]
    assert run["results"] == results
    assert run["properties"]["truminds_rules_dropped"] == 4


def test_rule_index_is_renumbered_to_the_kept_rules(tmp_path: Path) -> None:
    """ESLint form: ruleId and ruleIndex; a reportingDescriptorReference (rule.index) too."""
    rules = [_rule("a"), _rule("b"), _rule("c"), _rule("d")]
    results = [
        _result(ruleId="d", ruleIndex=3),
        _result(ruleId="b", ruleIndex=1),
        _result(rule={"id": "d", "index": 3}),
    ]
    p = _write(tmp_path / "lint.sarif", _sarif(rules, results))
    assert compact_sarif(p) is True
    run = _run(p)
    kept = [r["id"] for r in run["tool"]["driver"]["rules"]]
    assert kept == ["b", "d"]
    for r in run["results"]:
        rid = r.get("ruleId") or r["rule"]["id"]
        idx = r["ruleIndex"] if "ruleIndex" in r else r["rule"]["index"]
        assert kept[idx] == rid, r


def test_no_results_keeps_no_rules(tmp_path: Path) -> None:
    p = _write(tmp_path / "secrets.sarif", _sarif([_rule("g1"), _rule("g2")], []))
    assert compact_sarif(p) is True
    assert _run(p)["tool"]["driver"]["rules"] == []


def test_a_report_whose_rules_are_all_used_is_not_rewritten(tmp_path: Path) -> None:
    p = _write(tmp_path / "lint.sarif", _sarif([_rule("a")], [_result(ruleId="a")]))
    before = p.read_bytes()
    assert compact_sarif(p) is False
    assert p.read_bytes() == before


@pytest.mark.parametrize(
    "text",
    [
        "",
        "not json",
        "[1, 2]",
        '{"runs": "x"}',
        '{"runs": [{"tool": null}]}',
        '{"runs": [{"tool": {"driver": {"rules": [{"id": "a"}]}}, "results": 5}]}',
    ],
)
def test_a_file_that_is_not_sarif_is_left_alone(tmp_path: Path, text: str) -> None:
    p = tmp_path / "sast.sarif"
    p.write_text(text, encoding="utf-8")
    assert compact_sarif(p) is False
    assert p.read_text(encoding="utf-8") == text


def test_hms28_sized_report_becomes_citeable(tmp_path: Path) -> None:
    """1,074 rules with long help texts and 4 results: over MAX_BYTES before, far under after."""
    rules = [_rule(f"semgrep.rule.{i}", pad=2000) for i in range(1074)]
    results = [_result(ruleId=f"semgrep.rule.{i}") for i in (7, 300, 300, 1000)]
    p = _write(tmp_path / "sast.sarif", _sarif(rules, results))
    assert p.stat().st_size > MAX_BYTES
    assert compact_sarif(p) is True
    assert p.stat().st_size < 20_000
    assert len(_run(p)["tool"]["driver"]["rules"]) == 3


def test_verifier_hashes_the_compacted_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The report hash in the verifier result is the hash of the file a reviewer cites."""
    monkeypatch.setattr(DockerVerifier, "available", lambda self: True)
    monkeypatch.setattr(DockerVerifier, "probe", lambda self: None)
    monkeypatch.setattr("tsl.harness.verifier.available_memory_mb", lambda: None)
    out = tmp_path / "a1"
    big = _sarif([_rule(f"r{i}") for i in range(50)], [_result(ruleId="r3")])
    steps = iter(["prepare", "sast"])

    def fake_run(cmd: list[str], **kw: Any) -> subprocess.CompletedProcess[bytes]:
        if next(steps) == "sast":
            _write(out / "sast.sarif", big)
        return subprocess.CompletedProcess(cmd, 0, b"", b"")

    monkeypatch.setattr(subprocess, "run", fake_run)
    profile = {
        "id": "node-22@1",
        "image": "img@sha256:" + "1" * 64,
        "steps": {
            "prepare": {"cmd": "npm ci", "timeout_s": 60},
            "sast": {"cmd": "semgrep", "timeout_s": 60, "parse": "sarif", "report": "sast.sarif"},
        },
    }
    res = DockerVerifier().run(profile, tmp_path, out, with_coverage=False)
    (sast,) = res.steps
    assert [r["id"] for r in _run(out / "sast.sarif")["tool"]["driver"]["rules"]] == ["r3"]
    assert sast.report_sha256 == sha256_file(out / "sast.sarif")


def test_a_sub_rule_result_keeps_its_parent_rule(tmp_path: Path) -> None:
    """SARIF hierarchical ids: a result for js/xss/reflected keeps the rule js/xss."""
    rules = [_rule("js/xss"), _rule("js/xs"), _rule("py/sql")]
    p = _write(tmp_path / "sast.sarif", _sarif(rules, [_result(ruleId="js/xss/reflected")]))
    assert compact_sarif(p) is True
    assert [r["id"] for r in _run(p)["tool"]["driver"]["rules"]] == ["js/xss"]


def test_a_run_pointing_at_rules_another_way_is_left_whole(tmp_path: Path) -> None:
    """rule.toolComponent (indexes into tool.extensions) or a notification's associatedRule:
    renumbering could break them, so nothing is dropped."""
    rules = [_rule("a"), _rule("b")]
    ext = _sarif(rules, [_result(rule={"id": "x", "index": 0, "toolComponent": {"index": 0}})])
    note = _sarif(rules, [_result(ruleId="b", ruleIndex=1)])
    note["runs"][0]["invocations"] = [
        {"toolConfigurationNotifications": [{"associatedRule": {"index": 1}}]}
    ]
    for name, doc in (("ext.sarif", ext), ("note.sarif", note)):
        p = _write(tmp_path / name, doc)
        before = p.read_bytes()
        assert compact_sarif(p) is False, name
        assert p.read_bytes() == before, name


def test_a_report_that_cannot_be_rewritten_is_kept_as_written(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A container-owned report on Linux CI: the rewrite fails, the verifier goes on."""

    def refuse(path: Path, text: str) -> None:
        raise PermissionError(13, "Permission denied", str(path))

    monkeypatch.setattr("tsl.harness.verifier.atomic_write", refuse)
    p = _write(tmp_path / "sast.sarif", _sarif([_rule("a"), _rule("b")], [_result(ruleId="a")]))
    before = p.read_bytes()
    assert compact_sarif(p) is False
    assert p.read_bytes() == before
