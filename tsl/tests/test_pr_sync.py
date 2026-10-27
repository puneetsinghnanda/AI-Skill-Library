"""tsl pr-sync: report run PRs merged or closed on GitHub that the webhook missed."""

from __future__ import annotations

import json
from typing import Any

from helpers import World
from tsl.github.client import PullRequest

RUN = "run_01M5XRKT5GS1J5S7SNA59XFVA2"
REPO = "example-org/sample-orders"


def _run_with_pr(world: World, number: int) -> None:
    d = world.companion / "runs" / RUN
    d.mkdir(parents=True, exist_ok=True)
    state = {
        "run_id": RUN,
        "prs": [{"repo": "sample-orders", "number": number, "url": "u", "draft": True}],
    }
    (d / "state.json").write_text(json.dumps(state))
    world.github.prs[(REPO, number)] = PullRequest(number, "u", True, "", "", [])


def _closed_events(world: World) -> list[dict[str, Any]]:
    return [e for e in world.rt().outbox().events() if e["type"] == "pr.closed"]


def test_merged_pr_is_reported_once(world: World) -> None:
    _run_with_pr(world, 2)
    code, env, _, err = world.cli(["pr-sync", "--json"])
    assert code == 0, err
    assert env is not None and env["data"]["sent"] == 0  # still open: nothing to report
    pr = world.github.prs[(REPO, 2)]
    pr.state, pr.merged, pr.closed_at = "closed", True, "2026-10-27T10:00:00Z"
    code, env, _, err = world.cli(["pr-sync", RUN, "--json"])
    assert code == 0, err
    assert env is not None and env["data"]["sent"] == 1
    [ev] = _closed_events(world)
    assert ev["run_id"] == RUN
    assert ev["body"] == {
        "repo": "sample-orders",
        "number": 2,
        "merged": True,
        "closed_at": "2026-10-27T10:00:00Z",
    }
    code, env, _, _ = world.cli(["pr-sync", "--json"])
    assert env is not None and env["data"]["sent"] == 0 and len(_closed_events(world)) == 1


def test_closed_then_merged_reports_both(world: World) -> None:
    _run_with_pr(world, 3)
    pr = world.github.prs[(REPO, 3)]
    pr.state, pr.closed_at = "closed", "2026-10-27T09:00:00Z"
    world.cli(["pr-sync", "--json"])
    pr.merged, pr.closed_at = True, "2026-10-27T11:00:00Z"
    world.cli(["pr-sync", "--json"])
    assert [e["body"]["merged"] for e in _closed_events(world)] == [False, True]


def test_github_down_fails_cleanly(world: World) -> None:
    _run_with_pr(world, 4)
    world.github.unreachable = True
    code, env, _, _ = world.cli(["pr-sync", "--json"])
    assert code != 0 and env is not None and env["code"] == "E-GIT-01"
