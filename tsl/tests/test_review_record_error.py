"""A review rerun learns why the last review was refused from its package (roadmap C3).

Run HMS-28, secrev: record refused a review with E-REV-05. The run skill passed the error to the
review skill as arguments; their quotes and braces made Claude Code refuse the skill's shell
command, and messaging the reviewer was not a step tool, so the rerun reviewer never saw the
error and could repeat the same cite. tsl now keeps the error and prepare puts it in the package.
"""

from __future__ import annotations

import json
from typing import Any

from e2e_steps import SESSION, do_req_step, start_run
from helpers import World, review_json
from tsl.core.jsonio import write_json
from tsl.review.service import record_error_path

BAD_QUOTE = "This sentence is nowhere in the baseline"


def _finding(quote: str) -> dict[str, Any]:
    return {
        "id": "F-1",
        "severity": "minor",
        "category": "consistency",
        "text": "Retention differs from the baseline.",
        "cites": [{"ref": "context/intent-baseline.md#goals", "quote": quote}],
    }


def _record(world: World, art: str, stdin: str) -> tuple[int, dict[str, Any]]:
    code, env, _, err = world.cli(["review", "record", art, "--json"], session=SESSION, stdin=stdin)
    assert env is not None, err
    return code, env


def _prepare(world: World, art: str) -> tuple[dict[str, Any], str]:
    code, env, _, err = world.cli(["review", "prepare", art, "--json"], session=SESSION)
    assert code == 0 and env is not None, err
    data = env["data"]
    pkg = json.loads((world.companion / data["package_path"]).read_text(encoding="utf-8"))
    return pkg, str(data["package"])


def test_cite_error_reaches_the_next_reviewer_then_clears(world: World) -> None:
    run_id = start_run(world)
    res = do_req_step(world, run_id, until="prepared")
    art, package = res["artifact"], res["package"]
    err_file = world.companion / record_error_path(run_id, "req")

    code, env = _record(world, art, review_json(package, findings=[_finding(BAD_QUOTE)]))
    assert code == 2 and env["code"] == "E-REV-05", env
    assert err_file.is_file()

    pkg, md = _prepare(world, art)  # prepare validates the package against its schema
    err = pkg["record_error"]
    assert err["code"] == "E-REV-05" and "do not verify" in err["message"], err
    assert [c["item"] for c in err["citations"]] == ["finding F-1"], err
    assert err["citations"][0]["ref"] == "context/intent-baseline.md#goals"
    assert "## Your last review of this attempt was not recorded (E-REV-05)" in md
    assert "- finding F-1: context/intent-baseline.md#goals (" in md

    # The rerun reviewer fixes the cite: the review is recorded and the error is gone.
    code, env = _record(world, art, review_json(pkg, findings=[]))
    assert code == 0, env
    assert not err_file.exists()
    pkg, md = _prepare(world, art)
    assert "record_error" not in pkg and "was not recorded" not in md


def test_schema_error_reaches_the_next_reviewer(world: World) -> None:
    run_id = start_run(world)
    res = do_req_step(world, run_id, until="prepared")
    code, env = _record(world, res["artifact"], "the reviewer answered in prose")
    assert code != 0 and env["code"] == "E-REV-02", env
    pkg, md = _prepare(world, res["artifact"])
    assert pkg["record_error"]["code"] == "E-REV-02"
    assert "citations" not in pkg["record_error"]
    assert "(E-REV-02)" in md and "Fix that, keep the rest of the review" in md


def test_an_earlier_attempts_error_is_not_shown(world: World) -> None:
    run_id = start_run(world)
    res = do_req_step(world, run_id, until="prepared")
    old = {"attempt": 99, "code": "E-REV-05", "message": "old", "citations": []}
    write_json(world.companion / record_error_path(run_id, "req"), old)
    pkg, md = _prepare(world, res["artifact"])
    assert "record_error" not in pkg and "was not recorded" not in md


def test_a_broken_error_file_does_not_stop_prepare(world: World) -> None:
    run_id = start_run(world)
    res = do_req_step(world, run_id, until="prepared")
    broken = world.companion / record_error_path(run_id, "req")
    broken.parent.mkdir(parents=True, exist_ok=True)
    broken.write_text("{", encoding="utf-8")
    pkg, _ = _prepare(world, res["artifact"])
    assert "record_error" not in pkg
