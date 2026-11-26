"""Tests for benchmarks/bench_report.py (E1). Invented runs only."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import bench_report as br

RUN = "run_01TESTAAAAAAAAAAAAAAAAAAAA"
RUN2 = "run_01TESTBBBBBBBBBBBBBBBBBBBB"


def _att(
    n: int,
    cause: str,
    outcome: str,
    start: str,
    end: str,
    feedback: str | None = None,
    metrics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    a: dict[str, Any] = {
        "n": n,
        "cause": cause,
        "outcome": outcome,
        "band": "High",
        "started_at": f"2026-11-20T{start}:00Z",
        "decided_at": f"2026-11-20T{end}:00Z",
        "feedback": feedback,
    }
    if metrics is not None:
        a["metrics"] = metrics
    return a


def _write(root: Path, rel: str, data: Any) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(data if isinstance(data, str) else json.dumps(data), encoding="utf-8")


def _tok(out: int) -> dict[str, int]:
    return {"input": 10, "output": out, "cache_read": 1000, "cache_write": 100, "calls": 3}


@pytest.fixture()
def companion(tmp_path: Path) -> Path:
    """Two invented runs: a 0.1.7 run on Windows with a review and a lint retry and no
    metrics, and a 0.1.8 run on Linux with D1 metrics and a B2 question wait."""
    root = tmp_path / "companion"
    base = f"runs/{RUN}"
    _write(
        root,
        f"{base}/state.json",
        {
            "run_id": RUN,
            "ticket": "ABC-1",
            "workflow": "brownfield-small@1.0.0",
            "status": "COMPLETED",
            "end_reason": "pr_opened",
            "owner_pseudonym": "eng-0001",
            "pinned": {"tsl": "0.1.7"},
            "created_at": "2026-11-20T10:00:00Z",
            "updated_at": "2026-11-20T11:00:00Z",
            "steps": [
                {
                    "id": "split",
                    "kind": "skill",
                    "status": "DONE",
                    "attempts": [
                        _att(1, "first", "RETRY", "10:00", "10:10"),
                        _att(
                            2,
                            "retry_review",
                            "PASS",
                            "10:10",
                            "10:15",
                            f"{base}/feedback/split.a1.json",
                        ),
                    ],
                },
                {
                    "id": "ut",
                    "kind": "skill",
                    "status": "DONE",
                    "attempts": [
                        _att(1, "first", "RETRY", "10:20", "10:30"),
                        # no feedback path: the reason comes from feedback/ut.a1.json
                        _att(2, "retry_verifier", "PASS-WITH-FINDINGS", "10:30", "10:40"),
                        _att(3, "stale_rerun", "PASS", "10:40", "10:45"),
                    ],
                },
                {"id": "pr", "kind": "pr", "status": "DONE", "attempts": []},
            ],
        },
    )
    _write(root, f"{base}/feedback/split.a1.json", {"kind": "review", "gate_failures": []})
    _write(
        root,
        f"{base}/feedback/ut.a1.json",
        {"kind": "verifier", "gate_failures": [{"id": "H3", "detail": "lint exit 1; log x"}]},
    )
    _write(
        root,
        f"{base}/tool-log.jsonl",
        json.dumps({"target": "C:/dev/companion/runs/x/state.json", "session_id": "s"}) + "\n",
    )
    _write(
        root,
        f"{base}/ide-answers.md",
        "# IDE answers\n\n## A-01\n- step: split\n- answer: yes\n\n## A-02\n- step: ut\n",
    )

    base2 = f"runs/{RUN2}"
    m = {"wait_s": 120, "active_ms": 480000, "source": "transcript", "tokens": _tok(5000)}
    _write(
        root,
        f"{base2}/state.json",
        {
            "run_id": RUN2,
            "ticket": "ABC-1",
            "workflow": "brownfield-small@1.0.0",
            "status": "COMPLETED",
            "pinned": {"tsl": "0.1.8"},
            "created_at": "2026-11-27T10:00:00Z",
            "updated_at": "2026-11-27T10:30:00Z",
            "steps": [
                {
                    "id": "split",
                    "kind": "skill",
                    "status": "DONE",
                    "attempts": [_att(1, "first", "PASS", "10:00", "10:10", metrics=m)],
                },
                {
                    "id": "ut",
                    "kind": "skill",
                    "status": "DONE",
                    "attempts": [_att(1, "first", "PASS", "10:10", "10:20", metrics=m)],
                },
            ],
        },
    )
    _write(
        root,
        f"{base2}/tool-log.jsonl",
        json.dumps({"target": "/home/eng/companion/runs/x", "session_id": "s"}) + "\n",
    )
    return root


def _set(tmp_path: Path) -> Path:
    p = tmp_path / "set.json"
    p.write_text(
        json.dumps(
            {
                "runs": [
                    {"ticket": "ABC-1", "run_id": RUN, "release": "0.1.7", "bench": True},
                    {"ticket": "ABC-1", "run_id": RUN2, "release": "0.1.8", "bench": True},
                ]
            }
        ),
        encoding="utf-8",
    )
    return p


def test_retry_reasons_os_and_not_recorded(companion: Path) -> None:
    run = br.load_run(br.Source(companion), {"run_id": RUN, "release": "0.1.7", "bench": True})
    assert run["os"] == "Windows"
    s = br.run_summary(run)
    assert s["reasons"] == {"review": 1, "lint": 1}
    assert s["retries"] == 2
    assert s["steps"]["ut"]["reruns"] == 1  # stale_rerun is not a retry
    assert s["first_pass"] == 0
    assert s["questions"] == 2
    # 0.1.7: no ide-questions.json and no metrics, so wait and tokens are not recorded
    assert s["wait_s"] is None and s["tokens"] is None
    assert s["ai_ms"] == (15 + 25) * 60000  # wall time of the attempts


def test_d1_metrics_and_linux(companion: Path) -> None:
    run = br.load_run(br.Source(companion), {"run_id": RUN2, "release": "0.1.8"})
    assert run["os"] == "Linux"
    s = br.run_summary(run)
    assert s["retries"] == 0 and s["first_pass"] == 2
    assert s["wait_s"] == 240
    assert s["ai_ms"] == 960000
    assert s["tokens"] == {
        "input": 20,
        "output": 10000,
        "cache_read": 2000,
        "cache_write": 200,
        "calls": 6,
    }


def test_b2_wait_without_d1(companion: Path) -> None:
    _write(
        companion,
        f"runs/{RUN}/ide-questions.json",
        {
            "asks": [
                {
                    "step": "split",
                    "attempt": 1,
                    "asked_at": "2026-11-20T10:02:00Z",
                    "answered_at": "2026-11-20T10:05:00Z",
                }
            ]
        },
    )
    run = br.load_run(br.Source(companion), {"run_id": RUN})
    split = br.step_summary(run["steps"][0])
    assert split["wait_s"] == 180
    assert split["ai_ms"] == (15 * 60 - 180) * 1000


def test_metrics_export_gives_tokens_only(companion: Path, tmp_path: Path) -> None:
    exp = tmp_path / "metrics"
    _write(
        exp,
        f"{RUN}.json",
        {
            "ok": True,
            "data": {
                "metrics": {
                    "attempts": [
                        {"step": s, "attempt": n, "wait_s": 0, "active_ms": 1, "tokens": _tok(7)}
                        for s, n in (("split", 1), ("split", 2), ("ut", 1), ("ut", 2), ("ut", 3))
                    ],
                    "total": {"tokens": _tok(99)},
                }
            },
        },
    )
    run = br.load_run(br.Source(companion), {"run_id": RUN}, exp)
    s = br.run_summary(run)
    assert s["tokens"]["output"] == 99  # the run total, run loop included
    assert s["steps"]["split"]["tokens"]["output"] == 14
    assert s["wait_s"] is None  # an export's 0 wait is not taken as recorded
    assert s["ai_ms"] == (15 + 25) * 60000


def test_git_ref_source(companion: Path) -> None:
    git = ["git", "-C", str(companion)]
    subprocess.run([*git, "init", "-q"], check=True)
    subprocess.run([*git, "add", "-A"], check=True)
    subprocess.run(
        [*git, "-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-qm", "x"],
        check=True,
    )
    (companion / f"runs/{RUN}/state.json").unlink()  # only the ref has it now
    run = br.load_run(br.Source(companion, "HEAD"), {"run_id": RUN})
    assert run["ticket"] == "ABC-1"
    assert br.Source(companion, "HEAD").read("runs/missing.json") is None


def test_markdown_and_json_report(companion: Path, tmp_path: Path, capsys: Any) -> None:
    st = _set(tmp_path)
    argv = ["--companion", str(companion), "--set", str(st), "--metrics-dir", str(tmp_path / "x")]
    assert br.main(argv) == 0
    md = capsys.readouterr().out
    assert "| ABC-1 * | Windows | 0.1.7 |" in md
    assert "| ABC-1 * | Windows | 2 (R) | 3 (L) |" in md
    assert "## Benchmark set by release" in md and "### 0.1.8 (ABC-1)" in md
    assert "1 from a verifier build, lint or test slip" in md

    out = tmp_path / "r.json"
    assert br.main([*argv, "--release", "0.1.8", "--format", "json", "--out", str(out)]) == 0
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert [r["run_id"] for r in doc["runs"]] == [RUN2]
    assert doc["per_step"][0]["tokens_out_median"] == 5000

    assert br.main([*argv, "--release", "9.9"]) == 1
