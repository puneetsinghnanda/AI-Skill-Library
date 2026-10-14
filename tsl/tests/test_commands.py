"""Happy path and main error codes of each command (SDD-04 §6). Network goes through fakes."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest
import yaml

from e2e_steps import SESSION, do_req_step, next_action, start_run
from helpers import World, git, review_json
from tsl.schemas.registry import errors

ROOT = Path(__file__).resolve().parents[2]
REAL_SKILL = ROOT / "plugins" / "truminds" / "skills" / "requirement-review"


def _approve_text(w: World, run_id: str) -> None:
    p = w.companion / f"runs/{run_id}/approvals.md"
    p.write_text(
        p.read_text().replace(
            "decision:          # approve | reject | changes | abort", "decision: approve"
        )
    )
    git(w.companion, "commit", "-qam", "approve")
    git(w.companion, "push", "-q", "origin", "main")


# ------------------------------------------------------------------------------- doctor
def test_doctor(world: World) -> None:
    code, env, _, _ = world.cli(["doctor", "--json"])
    assert env is not None
    ids = {c["id"]: c["status"] for c in env["data"]["checks"]}
    assert {"python", "git", "version", "login", "key", "service", "outbox", "repo"} <= set(ids)
    assert ids["login"] == "pass" and ids["key"] == "pass" and ids["version"] == "pass"
    assert code in (0, 3)
    if code == 3:
        assert env["code"] == "E-ENV-01"
    code, env, _, _ = world.cli(["doctor", "--plugin-version", "9.9.9", "--json"])
    assert code == 3 and env is not None and env["code"] == "E-ENV-01"


# ------------------------------------------------------------------------------- init
def _empty_remote(w: World) -> None:
    remote = w.base / "remotes" / "example-org" / "cl-03-sys-ord-companion.git"
    remote.parent.mkdir(parents=True, exist_ok=True)
    git(w.base, "init", "-q", "--bare", "-b", "main", str(remote))


def test_init_happy_and_errors(world: World) -> None:
    _empty_remote(world)
    out_dir = world.base / "clones"
    spec = "sample-orders=git@github.example:example-org/sample-orders.git,verifier=node-20@1"
    args = [
        "init",
        "--system",
        "SYS-ORD",
        "--product-repo",
        spec,
        "--clone-dir",
        str(out_dir),
        "--json",
    ]
    code, env, _, _ = world.cli(args, user="eng")
    assert code == 3 and env is not None and env["code"] == "E-AUTH-04"
    code, env, _, err = world.cli(args, user="tl")
    assert code == 0, (env, err)
    assert env is not None and "tsl.yaml" in env["data"]["files"]
    target = out_dir / "cl-03-sys-ord-companion"
    cfg = yaml.safe_load((target / "tsl.yaml").read_text())
    assert errors("tsl-config.v1", cfg) == []
    assert (target / ".gitattributes").read_text() == "* text=auto eol=lf\n"
    # the remote is no longer empty
    shutil.rmtree(target)
    code, env, _, _ = world.cli(args, user="tl")
    assert code == 3 and env is not None and env["code"] == "E-INIT-02"
    code, env, _, _ = world.cli(
        ["init", "--system", "SYS-ORD", "--product-repo", "bad", "--json"], user="tl"
    )
    assert code == 1 and env is not None and env["code"] == "E-USE-01"


def test_init_needs_consent_and_registration(world: World) -> None:
    _empty_remote(world)
    spec = "sample-orders=git@github.example:o/sample-orders.git,verifier=node-20@1"
    args = [
        "init",
        "--system",
        "SYS-ORD",
        "--product-repo",
        spec,
        "--clone-dir",
        str(world.base / "c2"),
        "--json",
    ]
    world.insights.systems["SYS-ORD"]["consent"]["scope"] = ["code_processing"]
    for p in (world.rt("tl").home.cache / "systems").glob("*.json"):
        p.unlink()
    code, env, _, _ = world.cli(args, user="tl")
    assert code == 3 and env is not None and env["code"] == "E-CONS-01"
    code, env, _, _ = world.cli(
        ["init", "--system", "SYS-NONE", "--product-repo", spec, "--json"], user="tl"
    )
    assert code == 3 and env is not None and env["code"] == "E-INIT-01"


# ------------------------------------------------------------------------------- validate
def test_validate(world: World, tmp_path: Path) -> None:
    code, env, _, _ = world.cli(
        ["validate", str(world.plugin / "skills" / "requirement-review"), "--json"]
    )
    assert code == 0 and env is not None and env["data"]["results"][0]["ok"]
    code, env, _, _ = world.cli(["validate", str(REAL_SKILL), "--json"])
    assert code == 0, env
    loose = yaml.safe_load((world.companion / "tsl.yaml").read_text())
    loose["change_limits"] = {"lines": 900}
    bad = tmp_path / "x" / "tsl.yaml"
    bad.parent.mkdir()
    bad.write_text(yaml.safe_dump(loose))
    code, env, _, _ = world.cli(["validate", str(bad), "--json"])
    assert code == 2 and env is not None and env["code"] == "E-CFG-01"
    future = tmp_path / "future.json"
    future.write_text(json.dumps({"schema": "run-state.v9"}))
    code, env, _, _ = world.cli(["validate", str(future), "--json"])
    assert code == 2 and env is not None and env["code"] in ("E-SCH-01", "E-CFG-01")


def test_validate_lock_writes_workflow_lock(world: World) -> None:
    wf = world.plugin / "workflows" / "brownfield-change.workflow.yaml"
    code, env, _, err = world.cli(["validate", str(wf), "--lock", "--json"])
    assert code == 0, (env, err)
    lock = json.loads((wf.parent / "brownfield-change.lock.json").read_text())
    assert errors("workflow-lock.v1", lock) == []


# ------------------------------------------------------------------------------- verify / review / decide
def test_verify_inputs_and_artifact(world: World) -> None:
    run_id = start_run(world)
    res = do_req_step(world, run_id, until="written")
    art = res["artifact"]
    code, env, _, _ = world.cli(["verify", art, "--json"], session=SESSION)
    assert code == 0 and env is not None
    assert {g["id"] for g in env["data"]["gates"]} >= {"H1", "H2", "H4", "H5"}
    checks = json.loads((world.companion / env["data"]["checks_path"]).read_text())
    assert errors("checks.v1", checks) == []
    code, env, _, _ = world.cli(
        ["verify", "--inputs", "--run", run_id, "--step", "split", "--json"], session=SESSION
    )
    assert code == 3 and env is not None and env["code"] in ("E-RUN-09", "E-RUN-05")


def test_verify_without_pack(bare_world: World) -> None:
    code, env, _, _ = bare_world.cli(["verify", "--inputs", "--json"], session=SESSION)
    assert env is not None and env["code"] in ("E-CTX-01", "E-RUN-04", "E-RUN-09", "E-USE-01")
    assert code in (1, 3)


def test_review_errors(world: World) -> None:
    run_id = start_run(world)
    _c, nenv = next_action(world, run_id)
    art = nenv["data"]["artifact_path"]
    (world.companion / art).parent.mkdir(parents=True, exist_ok=True)
    (world.companion / art).write_text("---\nschema: intent.v1\n---\n# x\n")
    code, env, _, _ = world.cli(["review", "prepare", art, "--json"], session=SESSION)
    assert code == 3 and env is not None and env["code"] == "E-REV-01"
    (world.companion / art).unlink()
    res = do_req_step(world, run_id, until="prepared")
    pkg = res["package"]
    code, env, _, _ = world.cli(
        ["review", "record", art, "--json"], session=SESSION, stdin="this is not json"
    )
    assert code == 2 and env is not None and env["code"] == "E-REV-02"
    stale = json.loads(review_json(pkg).split("```json\n")[1].split("\n```")[0])
    stale["artifact_sha256"] = "0" * 64
    code, env, _, _ = world.cli(
        ["review", "record", art, "--json"], session=SESSION, stdin=json.dumps(stale)
    )
    assert code == 2 and env is not None and env["code"] == "E-REV-03"
    no_cite = json.loads(
        review_json(
            pkg,
            findings=[
                {"id": "F-1", "severity": "minor", "category": "style", "text": "x", "cites": []}
            ],
        )
        .split("```json\n")[1]
        .split("\n```")[0]
    )
    code, env, _, _ = world.cli(
        ["review", "record", art, "--json"], session=SESSION, stdin=json.dumps(no_cite)
    )
    assert code == 2 and env is not None and env["code"] == "E-REV-02"
    # decide without a review is refused; the skill must record --unavailable instead
    code, env, _, _ = world.cli(["decide", art, "--json"], session=SESSION)
    assert code == 3 and env is not None and env["code"] == "E-RUN-05"
    code, env, _, _ = world.cli(
        ["review", "record", art, "--unavailable", "reviewer crashed", "--json"], session=SESSION
    )
    assert code == 0 and env is not None
    assert any(w["code"] == "E-REV-04" for w in env["warnings"])
    code, env, _, _ = world.cli(["decide", art, "--json"], session=SESSION)
    assert code == 4 and env is not None and env["code"] == "E-RUN-02"
    assert env["data"]["band"] == "Low" and "reviewer-missing" in env["data"]["caps"]


def test_decide_refuses_changed_artifact(world: World) -> None:
    run_id = start_run(world)
    res = do_req_step(world, run_id, until="recorded")
    p = world.companion / res["artifact"]
    p.write_text(p.read_text() + "\nedited after checks\n")
    code, env, _, _ = world.cli(["decide", res["artifact"], "--json"], session=SESSION)
    assert code == 3 and env is not None and env["code"] == "E-DEC-02"


def test_decide_without_key_writes_nothing(world: World) -> None:
    run_id = start_run(world)
    res = do_req_step(world, run_id, until="recorded")
    world.rt().keystore.items.clear()  # type: ignore[attr-defined]
    code, env, _, _ = world.cli(["decide", res["artifact"], "--json"], session=SESSION)
    assert code == 10 and env is not None and env["code"] in ("E-AUTH-02", "E-KEY-01")
    assert not (world.companion / res["artifact"].replace(".md", ".verification.json")).exists()


# ------------------------------------------------------------------------------- approve / pr
def test_self_approval_refused(world: World) -> None:
    run_id = start_run(world, user="tl")
    res = do_req_step(world, run_id, user="tl")
    assert res["code"] == 0, res["env"]
    _c, nenv = next_action(world, run_id, "tl")
    assert nenv["code"] == "E-RUN-02"
    code, env, _, _ = world.cli(["approve", run_id, "G-req", "--json"], user="tl")
    assert code == 3 and env is not None and env["code"] == "E-RUN-05"  # no decision written yet
    _approve_text(world, run_id)
    code, env, _, _ = world.cli(["approve", run_id, "G-req", "--json"], user="tl")
    assert code == 3 and env is not None and env["code"] == "E-AUTH-06"


def test_pr_refuses_incomplete_or_tampered_records(world: World) -> None:
    run_id = start_run(world)
    code, env, _, _ = world.cli(["pr", run_id, "--json"], session=SESSION)
    assert code == 3 and env is not None and env["code"] == "E-RUN-05"
    res = do_req_step(world, run_id)
    assert res["code"] == 0
    code, env, _, _ = world.cli(["pr", run_id, "--json"], session=SESSION)
    assert env is not None and (code, env["code"]) == (3, "E-RUN-05"), env  # gate pending
    assert world.github.created == []
    # tamper with the signed record: pr must refuse even once every step is done
    from tsl.core.repo import Companion
    from tsl.orchestrator.run import RunCtx
    from tsl.services.pr import _check_records

    vpath = world.companion / res["env"]["data"]["verification_path"]
    rec = json.loads(vpath.read_text())
    rec["band"] = "High" if rec["band"] != "High" else "Medium"
    vpath.write_text(json.dumps(rec))
    from tsl.core.errors import TslError

    with world.using() as rt, pytest.raises(TslError) as e:
        _check_records(rt, RunCtx(rt, Companion(world.companion), run_id))
    assert e.value.code == "E-RUN-05" and "does not verify" in e.value.message


def test_github_client_cannot_merge() -> None:
    from tsl.github import client

    names = [n.lower() for n in dir(client.HttpGitHubClient) + dir(client.GitHubClient)]
    assert not [n for n in names if "merge" in n]
    src = Path(client.__file__).read_text()
    assert "/merge" not in src


# ------------------------------------------------------------------------------- context
def test_context_commands(world: World) -> None:
    code, env, _, _ = world.cli(["context", "status", "--json"])
    assert code == 0 and env is not None and env["data"]["state"] == "fresh"
    code, env, _, _ = world.cli(["context", "build", "--check", "--json"])
    assert code == 0 and env is not None and env["data"]["changed"] is False
    code, env, _, _ = world.cli(["context", "sign", "--json"], user="eng")
    assert code == 3 and env is not None and env["code"] == "E-AUTH-04"
    code, env, _, _ = world.cli(["context", "deny-term", "Example Client", "--json"])
    assert code == 0 and env is not None and len(env["data"]["sha256"]) == 64
    code, env, _, _ = world.cli(["context", "draft-prepare", "data-model", "--json"])
    assert code == 0 and env is not None
    d = env["data"]
    assert d["path"] == "context/data-model.md" and d["budget_tokens"] == 8000
    assert any("table:orders" in f["ids"] for f in d["facts"])
    code, env, _, _ = world.cli(["context", "draft-prepare", "nope", "--json"])
    assert code == 1 and env is not None and env["code"] == "E-USE-01"


def test_context_lint_and_sign_rules(world: World) -> None:
    p = world.companion / "context" / "glossary.md"
    p.write_text(
        p.read_text().replace("status: reviewed", "status: drafted")
        + "\nSources: context/generated/db-schema.json#table:nope\n"
    )
    code, env, _, _ = world.cli(["context", "build", "--check", "--sections", "glossary", "--json"])
    assert code == 2 and env is not None and env["code"] == "E-CTX-07"
    assert all("glossary" in x for x in env["data"]["lint"])
    code, env, _, _ = world.cli(
        ["context", "build", "--check", "--sections", "architecture", "--json"]
    )
    assert code == 0, env
    p.write_text(
        p.read_text().replace("\nSources: context/generated/db-schema.json#table:nope\n", "\n")
    )
    code, env, _, _ = world.cli(["context", "build", "--json"], user="tl")
    assert code == 0, env
    code, env, _, _ = world.cli(["context", "sign", "--json"], user="tl")
    assert code == 2 and env is not None and env["code"] == "E-CTX-04"


def test_context_draft_prepare_needs_pack(bare_world: World) -> None:
    code, env, _, _ = bare_world.cli(["context", "draft-prepare", "glossary", "--json"])
    assert code == 3 and env is not None and env["code"] == "E-CTX-01"


# ------------------------------------------------------------------------------- eval
def _outputs_from_intent(world: World, plan: dict[str, Any]) -> None:
    """Simulate Claude writing one output per case (code scoring only)."""
    from test_improve import write_outputs

    write_outputs(plan, set())


def test_eval_plan_run_check(world: World) -> None:
    code, env, _, err = world.cli(["eval", "plan", "requirement-review", "--json"])
    assert code == 0, (env, err)
    assert env is not None and len(env["data"]["cases"]) == 10
    plan = env["data"]
    code, env, _, _ = world.cli(
        ["eval", "check", "requirement-review", "--case", "EC-01", "--json"]
    )
    assert code == 2 and env is not None and env["code"] == "E-EVAL-01"  # no output yet
    _outputs_from_intent(world, plan)
    code, env, _, _ = world.cli(["eval", "run", "requirement-review", "--json"])
    assert env is not None, env
    result = json.loads(Path(env["data"]["result_path"]).read_text())
    assert errors("eval-result.v1", result) == []
    assert result["cases_total"] == 10 and result["key_id"] == env["data"]["key_id"]
    assert code == 0 and env["data"]["pass_rate"] == 1.0, env["data"]["per_case"]
    ev = [e for e in world.rt().outbox().events() if e["type"] == "eval.recorded"]
    assert ev[-1]["body"]["pass_rate"] == 1.0
    code, env, _, _ = world.cli(
        ["eval", "check", "requirement-review", "--case", "EC-01", "--json"]
    )
    assert code == 0, env
    code, env, _, _ = world.cli(
        ["eval", "plan", "requirement-review", "--version", "9.9.9", "--json"]
    )
    assert code == 1 and env is not None and env["code"] == "E-USE-01"


def test_eval_plan_on_the_real_skill(world: World) -> None:
    dst = world.plugin / "skills" / "requirement-review"
    shutil.rmtree(dst)
    shutil.copytree(REAL_SKILL, dst)
    code, env, _, err = world.cli(["eval", "plan", "requirement-review", "--json"])
    assert code == 0, (env, err)
    assert env is not None and len(env["data"]["cases"]) >= 10
    for c in env["data"]["cases"]:
        assert any(Path(c["input_dir"]).iterdir())


def test_eval_plan_too_few_cases(world: World) -> None:
    cases = world.plugin / "skills" / "requirement-review" / "evals" / "cases"
    for d in sorted(cases.iterdir())[3:]:
        shutil.rmtree(d)
    code, env, _, _ = world.cli(["eval", "plan", "requirement-review", "--json"])
    assert code == 1 and env is not None and env["code"] == "E-CFG-01"


# ------------------------------------------------------------------------------- migrate
def test_migrate_dry_run(world: World) -> None:
    code, env, _, _ = world.cli(["migrate", "--to", "v1", "--dry-run", "--json"])
    assert code == 0 and env is not None and env["data"]["files"] == []
    code, env, _, _ = world.cli(["migrate", "--to", "two", "--json"])
    assert code == 1 and env is not None and env["code"] == "E-USE-01"


def test_verify_inputs_missing_ticket(world: World) -> None:
    run_id = start_run(world)
    _c, nenv = next_action(world, run_id)
    art = nenv["data"]["artifact_path"]
    code, env, _, _ = world.cli(["verify", art, "--inputs", "--json"], session=SESSION)
    assert env is not None and (code, env["code"]) == (2, "E-IN-01")


def test_context_freshness_and_tamper(world: World) -> None:
    # SDD-06 §7.1 measures freshness in commits; a change under a critical path makes it stale
    auth = world.product / "api" / "src" / "auth"
    auth.mkdir(parents=True)
    (auth / "token.js").write_text("module.exports = {};\n")
    git(world.product, "add", "-A")
    git(world.product, "commit", "-qm", "auth")
    git(world.product, "push", "-q", "origin", "main")
    code, env, _, _ = world.cli(["context", "status", "--json"])
    assert code == 0 and env is not None and env["data"]["state"] == "stale"
    assert env["warnings"][0]["code"] == "E-CTX-02"
    sig = world.companion / "context" / "pack.signature.json"
    rec = json.loads(sig.read_text())
    rec["signed_by"] = "tl-0000"
    sig.write_text(json.dumps(rec))
    code, env, _, _ = world.cli(["context", "status", "--json"])
    assert env is not None and (code, env["code"]) == (3, "E-CTX-03")


def test_context_build_blocks_secrets(world: World) -> None:
    p = world.companion / "context" / "conventions.md"
    p.write_text(p.read_text() + "\nThe deploy key is " + "AKIA" + "Q3VZ7KMB2XW4PLRT" + ".\n")
    code, env, _, _ = world.cli(["context", "build", "--check", "--json"])
    assert env is not None and (code, env["code"]) == (2, "E-CTX-06")


def _set_context(w: World, ctx: dict[str, Any]) -> None:
    p = w.companion / "tsl.yaml"
    cfg = yaml.safe_load(p.read_text())
    cfg["context"] = {**cfg["context"], **ctx}
    p.write_text(yaml.safe_dump(cfg, sort_keys=False))
    git(w.companion, "commit", "-qam", "tsl.yaml context")
    git(w.companion, "push", "-q", "origin", "main")


def _push_product(w: World, files: dict[str, str], msg: str = "change") -> None:
    for rel, text in files.items():
        p = w.product / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    git(w.product, "add", "-A")
    git(w.product, "commit", "-qm", msg)
    git(w.product, "push", "-q", "origin", "main")


def test_context_build_never_reads_answer_keys(world: World) -> None:
    # TST-01 §4.3, sample-system README: the answer key is never extracted into a pack,
    # whatever tsl.yaml says (built-in exclusion, not configurable).
    _push_product(
        world,
        {
            ".answers/defects.yaml": "SD-01: order history drops the last 30 seconds\n",
            ".answers/canary/api.canary.test.ts": "describe('SD-01 canary', () => {\n"
            "  it('history misses 23:59:30', () => {});\n});\n",
            ".answers/migrations/900_hint.sql": "CREATE TABLE answer_hint (id int);\n",
            "api/.answers/notes.md": "nested answer key\n",
        },
        "answer key",
    )
    code, env, _, _ = world.cli(["context", "build", "--json"], user="tl")
    assert code == 0, env
    gen = world.companion / "context" / "generated"
    for f in gen.glob("*.json"):
        text = f.read_text()
        assert ".answers" not in text and "SD-01" not in text and "answer_hint" not in text, f
    manifest = json.loads((world.companion / "context" / "manifest.json").read_text())
    assert manifest["sources"][0]["files_excluded"] >= 4
    from tsl.context.repoview import excluded

    for path in (".answers", ".answers/x.md", "examples/sample-system/.answers/defects.yaml"):
        assert excluded(path, [])
    assert excluded("examples/sample-system-key/defects.yaml", [])


def test_context_config_limits_extractors_redaction(world: World) -> None:
    # SDD-06 §7.2: max_commits_behind, limits, extractors and redaction come from tsl.yaml
    import hashlib

    term = hashlib.sha256(b"orders newest").hexdigest()
    _set_context(
        world,
        {
            "max_commits_behind": 1,
            "limits": {"section_tokens": 6000},
            "extractors": {"migrations": ["api/migrations/001_*.sql"], "tests": ["**/*.spec.js"]},
            "redaction": {"extra_exclude": ["web/**"], "deny_term_hashes": [term]},
        },
    )
    code, env, _, _ = world.cli(["context", "build", "--json"], user="tl")
    assert code == 0, env
    manifest = json.loads((world.companion / "context" / "manifest.json").read_text())
    assert manifest["limits"]["section_tokens"] == 6000
    assert manifest["limits"]["judgement_tokens"] == 40000
    gen = world.companion / "context" / "generated"
    db = (gen / "db-schema.json").read_text()
    assert "table:orders" in db and "order_events" not in db  # only 001_* matched
    layout = (gen / "test-layout.json").read_text()
    assert "orders.test.js" not in layout  # only *.spec.js counts now
    assert "web/" not in (gen / "module-map.json").read_text()  # extra_exclude
    assert manifest["redaction"]["paths_excluded"] >= 2
    # a deny term in a judgement section is a blocking hit (SDD-06 §9.3)
    p = world.companion / "context" / "conventions.md"
    p.write_text(p.read_text() + "\nWe list Orders Newest first.\n")
    code, env, _, _ = world.cli(["context", "build", "--check", "--json"])
    assert env is not None and (code, env["code"]) == (2, "E-CTX-06")
    p.write_text(p.read_text().replace("\nWe list Orders Newest first.\n", "\n"))
    # tighter F5: two commits under the scope make the signed pack stale
    code, env, _, _ = world.cli(["context", "build", "--json"], user="tl")
    assert code == 0, env
    code, env, _, _ = world.cli(["context", "sign", "--json"], user="tl")
    assert code == 0, env
    git(world.companion, "push", "-q", "origin", "main")
    _push_product(world, {"api/src/a.js": "1\n"}, "one")
    _push_product(world, {"api/src/b.js": "2\n"}, "two")
    code, env, _, _ = world.cli(["context", "status", "--json"])
    assert code == 0 and env is not None and env["data"]["state"] == "stale"
    assert "commits_behind" in env["data"]["reasons"]


def test_context_max_age_days_is_deprecated(world: World, tmp_path: Path) -> None:
    from tsl.core.config import load_config

    p = tmp_path / "tsl.yaml"
    cfg = yaml.safe_load((world.companion / "tsl.yaml").read_text())
    cfg["context"]["max_age_days"] = 30
    p.write_text(yaml.safe_dump(cfg))
    loaded, warnings = load_config(p)
    assert loaded.max_commits_behind == 50
    assert [w["code"] for w in warnings] == ["E-DEP-01"]
