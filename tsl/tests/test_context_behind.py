"""E-CTX-10: a fresh pack that is behind the product code says so, instead of a bare "fresh"."""

from __future__ import annotations

from typing import Any

from tsl.context.freshness import behind_warnings


def _fs(state: str, behind: dict[str, int], files: dict[str, int]) -> dict[str, Any]:
    return {
        "state": state,
        "reasons": [],
        "state_block": {"commits_behind": behind, "drift_files": files},
    }


def test_fresh_pack_behind_the_code_warns_with_counts() -> None:
    [w] = behind_warnings(_fs("fresh", {"sample-system": 12}, {"sample-system": 27}))
    assert w["code"] == "E-CTX-10"
    assert "sample-system by 12 commits and 27 files" in w["message"]


def test_current_pack_has_no_warning() -> None:
    assert behind_warnings(_fs("fresh", {"sample-system": 0}, {"sample-system": 0})) == []


def test_stale_pack_keeps_its_own_warning_only() -> None:
    # Over the limits the pack is stale and E-CTX-02 already says so.
    assert behind_warnings(_fs("stale", {"sample-system": 80}, {"sample-system": 90})) == []
