"""The reviewer instructions spell out review.v1, and a review built from them records."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from e2e_steps import SESSION, do_req_step, start_run
from helpers import World
from tsl.review.service import INSTRUCTIONS
from tsl.schemas.registry import errors, load

PLUGIN_AGENT = "plugins/truminds/agents/reviewer.md"


def _template_keys(text: str) -> list[str]:
    return re.findall(r'^  "([a-z_0-9]+)":', text, re.M)


def _enum_words(prop: dict[str, Any]) -> list[str]:
    return [str(x) for x in prop["enum"]]


def test_instructions_name_every_review_v1_key_and_enum() -> None:
    schema = load("review.v1")
    assert _template_keys(INSTRUCTIONS) == schema["required"]
    props = schema["properties"]
    finding = props["findings"]["items"]["properties"]
    question = props["questions"]["items"]["properties"]
    claim = props["claims_checked"]["items"]["properties"]
    for words in (
        schema["$defs"]["severity"]["enum"],
        _enum_words(finding["category"]),
        _enum_words(claim["verdict"]),
        _enum_words(question["ask_role"]),
    ):
        assert "|".join(words) in INSTRUCTIONS, words
    for key in (*finding, *question, *claim, "status_reason", "could_not_review"):
        assert key in INSTRUCTIONS, key


def test_reviewer_agent_mirrors_the_instructions() -> None:
    agent = (Path(__file__).resolve().parents[2] / PLUGIN_AGENT).read_text(encoding="utf-8")
    start = INSTRUCTIONS.index("{\n")
    end = INSTRUCTIONS.index("\n}", start) + 2
    assert INSTRUCTIONS[start:end] in agent


def test_review_built_from_the_instructions_validates_and_records(world: World) -> None:
    run_id = start_run(world)
    art = do_req_step(world, run_id, until="written")["artifact"]
    code, env, _, err = world.cli(["review", "prepare", art, "--json"], session=SESSION)
    assert code == 0 and env is not None, err
    md = env["data"]["package"]
    data = json.loads(md.split("```DATA\n", 1)[1].split("\n```", 1)[0])
    review = {
        "schema": "review.v1",
        "run_id": data["run_id"],
        "step": data["step"],
        "attempt": data["attempt"],
        "artifact_sha256": data["artifact_sha256"],
        "package_sha256": data["package_sha256"],
        "status": "ok",
        "reviewer": data["reviewer"],
        "rubric_score": 4.0,
        "rubric_items": [{"id": i, "score": 4, "reason": "clear"} for i in data["rubric_items"]],
        "findings": [
            {
                "id": "F-1",
                "severity": "minor",
                "category": "completeness",
                "text": "The retention period is not stated.",
                "cites": [{"ref": f"{art}#requirements", "quote": "export orders as CSV"}],
            }
        ],
        "claims_checked": [{"claim_id": "C1", "verdict": "supported"}],
        "questions": [
            {
                "id": "Q-1",
                "text": "How long are exports kept?",
                "ask_role": "product_owner",
                "blocking": False,
                "finding_ref": "F-1",
            }
        ],
    }
    assert list(review) == _template_keys(INSTRUCTIONS)
    assert errors("review.v1", review) == []
    code, env, _, err = world.cli(
        ["review", "record", art, "--json"], session=SESSION, stdin=json.dumps(review)
    )
    assert code == 0 and env is not None, (env, err)
    assert env["data"]["status"] == "ok"
