"""tsl companion check | archive (SDD-12 §6.4, §8.2) and tsl harness eval (SDD-03 §16)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

import helpers
from e2e_steps import do_req_step, start_run
from helpers import World, git, intent_artifact, ticket_snapshot
from tsl.identity.signing import b64url_decode, signature_ok


def _commit(w: World, msg: str) -> None:
    git(w.companion, "add", "-A")
    git(w.companion, "commit", "-qm", msg)


def _check(w: World, *extra: str) -> tuple[int, dict[str, Any]]:
    code, env, _, err = w.cli(["companion", "check", *extra, "--json"])
    assert env is not None, err
    return code, env


@pytest.fixture
def ran(world: World) -> tuple[World, str, dict[str, Any]]:
    run_id = start_run(world)
    res = do_req_step(world, run_id)
    assert res["code"] == 0, res["env"]
    return world, run_id, res


def test_check_passes_after_a_real_run(ran: tuple[World, str, dict[str, Any]]) -> None:
    w, _, _ = ran
    code, env = _check(w)
    assert code == 0, env["data"]["findings"]
    assert env["data"]["result"] == "pass" and env["data"]["files_checked"] > 10
    assert env["data"]["pack"]["state"] == "fresh"


def test_record_changed_after_commit(ran: tuple[World, str, dict[str, Any]]) -> None:
    w, _, res = ran
    v = w.companion / res["env"]["data"]["verification_path"]
    rec = json.loads(v.read_text())
    rec["band"] = "Medium"
    v.write_text(json.dumps(rec))
    _commit(w, "edit a record")
    code, env = _check(w)
    assert (code, env["code"]) == (2, "E-COMP-03")
    assert env["data"]["findings"][0]["path"].endswith(".verification.json")


def test_schema_invalid(ran: tuple[World, str, dict[str, Any]]) -> None:
    w, run_id, _ = ran
    (w.companion / f"runs/{run_id}/state.json").write_text('{"schema": "run-state.v1"}')
    _commit(w, "break state")
    code, env = _check(w)
    assert (code, env["code"]) == (2, "E-COMP-01")


def test_forbidden_content_is_reported_without_the_value(world: World) -> None:
    fake = "AKIA" + "Q3VZ7KMB2XW4PLRT"
    (world.companion / "notes.md").write_text(f"# Notes\n\nline two\nkey {fake}\n")
    (world.companion / "secrets").mkdir()
    (world.companion / "secrets" / "x.txt").write_text("nothing\n")
    _commit(world, "notes")
    code, env = _check(world)
    assert (code, env["code"]) == (2, "E-COMP-04")
    assert fake not in json.dumps(env)
    hits = {(f["path"], f["line"]) for f in env["data"]["findings"]}
    assert ("notes.md", 4) in hits and ("secrets/x.txt", 0) in hits


def test_file_too_large(world: World) -> None:
    (world.companion / "big.txt").write_text("a" * (5 * 1024 * 1024 + 1))
    _commit(world, "big")
    code, env = _check(world)
    assert (code, env["code"]) == (2, "E-COMP-05")


def test_direct_push_to_protected_path_and_run_isolation(world: World) -> None:
    base = git(world.companion, "rev-parse", "HEAD")
    p = world.companion / "tsl.yaml"
    p.write_text(p.read_text() + "\n")
    _commit(world, "edit tsl.yaml directly")
    code, env = _check(world, "--base", base, "--event", "push")
    assert (code, env["code"]) == (2, "E-COMP-02")
    code, env = _check(world, "--base", base, "--event", "pull_request")
    assert code == 0  # pull requests may change protected paths
    base2 = git(world.companion, "rev-parse", "HEAD")
    for rid in ("run_01J9ZK2M4Q8X7T3B5N6R0VWYC1", "run_01J9ZK2M4Q8X7T3B5N6R0VWYC2"):
        d = world.companion / "runs" / rid
        d.mkdir(parents=True)
        (d / "note.txt").write_text("x\n")
    _commit(world, "two runs in one commit")
    code, env = _check(world, "--base", base2)
    assert (code, env["code"]) == (2, "E-COMP-02")
    assert "2 run folders" in env["data"]["findings"][0]["detail"]
    code, env = _check(world, "--event", "merge_group")
    assert (code, env["code"]) == (1, "E-USE-01")


def _admin(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    users = json.loads(json.dumps(helpers.USERS))
    users["adm"] = {
        "pseudonym": "adm-90ce",
        "upn": "adm@example.com",
        "oid": "oid-adm",
        "app_roles": ["Admin"],
        "grants": [{"role": "admin", "scope": "org"}],
    }
    monkeypatch.setattr(helpers, "USERS", users)
    world.login("adm")


def test_archive(ran: tuple[World, str, dict[str, Any]], monkeypatch: pytest.MonkeyPatch) -> None:
    w, run_id, _ = ran
    code, env, _, _ = w.cli(["companion", "archive", "--json"], user="eng")
    assert (code, env and env["code"]) == (3, "E-AUTH-04")
    _admin(w, monkeypatch)
    code, env, _, _ = w.cli(["companion", "archive", "--json"], user="adm")
    assert env is not None and (code, env["code"]) == (3, "E-COMP-06")
    assert env["data"]["runs"] == [run_id]
    code, env, _, err = w.cli(
        ["companion", "archive", "--abandon-runs", "--reason", "engagement_ended", "--json"],
        user="adm",
    )
    assert code == 0, (env, err)
    assert env is not None and env["data"]["abandoned"] == [run_id]
    arch = json.loads((w.companion / "ARCHIVE.json").read_text())
    facts = w.insights.facts(arch["key_id"])
    assert facts and signature_ok(arch, b64url_decode(facts["public_key"]))
    assert arch["records"] >= 3 and arch["archived_by"] == "adm-90ce"
    from tsl.schemas.registry import errors as schema_errors

    assert schema_errors("companion-archive.v1", arch) == []  # SDD-12 §8.2
    state = json.loads((w.companion / f"runs/{run_id}/state.json").read_text())
    assert (state["status"], state["end_reason"]) == ("COMPLETED", "archived")
    assert "archive/final" in git(w.companion_remote, "tag")
    assert not (w.companion / "runs/active/ABC-142__brownfield-change.lock").exists()
    ev = [e for e in w.rt("adm").outbox().events() if e["type"] == "companion.lifecycle"]
    assert ev[-1]["body"] == {
        "system": "SYS-ORD",
        "from": "ACTIVE",
        "to": "ARCHIVED",
        "reason_code": "engagement_ended",
    }


# ------------------------------------------------------------------------------- harness eval
ENV: dict[str, Any] = {
    "schema": "intent.v1",
    "run_id": "run_01J9ZK2M4Q8X7T3B5N6R0VWYCD",
    "step": "req",
    "attempt": 1,
    "skill": "requirement-review@1.0.0",
    "inputs": [],
    "pack_sha": {},
}
REVIEW = {
    "schema": "review.v1",
    "status": "ok",
    "rubric_score": 5.0,
    "rubric_items": [{"id": f"RR-R{i}", "score": 5, "reason": "ok"} for i in range(1, 7)],
    "findings": [],
    "claims_checked": [],
    "questions": [],
}
BASE_DOC = (
    "# Intent {#intent}\n\n## Data retention {#data-retention}\nOrder events are kept 24 hours.\n"
)


def _case(
    root: Path,
    cid: str,
    kind: str,
    expect: dict[str, Any],
    *,
    drop: str | None = None,
    review: dict[str, Any] | None = None,
) -> None:
    d = root / cid
    (d / "context").mkdir(parents=True)
    (d / "context" / "intent-baseline.md").write_text(BASE_DOC)
    (d / "inputs").mkdir()
    (d / "inputs" / "ticket.md").write_text(ticket_snapshot(ENV["run_id"]))
    (d / "artifact.md").write_text(
        intent_artifact(dict(ENV), "inputs/ticket.md", drop_section=drop)
    )
    if review is not None:
        (d / "review.json").write_text(json.dumps(review))
    (d / "case.yaml").write_text(
        yaml.safe_dump(
            {
                "schema": "harness-case.v1",
                "id": cid,
                "skill": "requirement-review@1.0.0",
                "kind": kind,
                "expect": expect,
            }
        )
    )


def _labelled_set(root: Path) -> None:
    _case(
        root,
        "clean-01",
        "gate",
        {"gates": {"H1": "pass", "H2": "pass", "H4": "pass"}, "outcome": "PASS", "band": "High"},
        review=REVIEW,
    )
    _case(
        root,
        "h2-missing-unknown-01",
        "gate",
        {"gates": {"H2": "fail"}, "outcome": "RETRY"},
        drop="Unknown",
        review=REVIEW,
    )
    fab = "context/history.md#order-history"
    finding = {
        "id": "F-1",
        "severity": "minor",
        "category": "completeness",
        "text": "x",
        "cites": [{"ref": fab, "quote": "history is kept forever"}],
    }
    _case(
        root,
        "cite-fabricated-01",
        "citation",
        {"outcome": "ESCALATE", "fabricated_cites": [fab]},
        review={**REVIEW, "findings": [finding]},
    )
    _case(
        root,
        "decide-low-score-01",
        "decide",
        {"outcome": "ESCALATE", "band": "Low"},
        review={
            **REVIEW,
            "rubric_score": 2.0,
            "rubric_items": [{"id": f"RR-R{i}", "score": 2, "reason": "weak"} for i in range(1, 7)],
        },
    )
    _case(
        root,
        "reviewer-planted-01",
        "reviewer",
        {
            "outcome": "RETRY",
            "planted_defects": [
                {
                    "id": "D1",
                    "severity": "major",
                    "path": "context/intent-baseline.md",
                    "lines": [3, 4],
                }
            ],
        },
    )


def test_harness_eval_on_target(world: World, tmp_path: Path) -> None:
    root = tmp_path / "harness-evals" / "cases"
    _labelled_set(root)
    code, env, _, _err = world.cli(["harness", "eval", "--code-only", "--dir", str(root), "--json"])
    assert code == 0, env and (env["data"]["misses"], env["data"]["mismatches"])
    assert env is not None
    m = env["data"]["measures"]
    assert m["gates"]["H2"] == {"tp": 1, "fp": 0, "fn": 0, "precision": 1.0, "recall": 1.0}
    assert m["decide_accuracy"] == 1.0 and m["fabrication_catch_rate"] == 1.0
    assert env["data"]["skipped"] == ["reviewer-planted-01"]


def test_harness_eval_reviewer_scoring(world: World, tmp_path: Path) -> None:
    root = tmp_path / "cases"
    _labelled_set(root)
    good = {
        "id": "F-1",
        "severity": "major",
        "category": "correctness",
        "text": "x",
        "cites": [
            {"ref": "context/intent-baseline.md#L3-L4", "quote": "Order events are kept 24 hours"}
        ],
    }
    (root / "reviewer-planted-01" / "review.json").write_text(
        json.dumps({**REVIEW, "findings": [good]})
    )
    code, env, _, err = world.cli(["harness", "eval", "--dir", str(root), "--json"])
    assert code == 0, (env, err)
    assert env is not None and env["data"]["measures"]["reviewer_recall"] == 1.0
    assert env["data"]["measures"]["reviewer_precision"] == 1.0


def test_harness_eval_below_target(world: World, tmp_path: Path) -> None:
    root = tmp_path / "cases"
    _labelled_set(root)
    meta = root / "h2-missing-unknown-01" / "case.yaml"
    case = yaml.safe_load(meta.read_text())
    case["expect"] = {"gates": {"H2": "pass"}, "outcome": "RETRY"}  # mislabelled on purpose
    meta.write_text(yaml.safe_dump(case))
    code, env, _, _ = world.cli(["harness", "eval", "--code-only", "--dir", str(root), "--json"])
    assert env is not None and (code, env["code"]) == (2, "E-HARN-01")
    assert any("H2 precision" in x for x in env["data"]["misses"])


def test_harness_eval_without_cases(world: World, tmp_path: Path) -> None:
    code, env, _, _ = world.cli(["harness", "eval", "--dir", str(tmp_path / "none"), "--json"])
    assert env is not None and (code, env["code"]) == (3, "E-ENV-01")
