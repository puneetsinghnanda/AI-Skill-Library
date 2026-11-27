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
    assert "engineer" not in run  # the report never reads who ran it


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
    # attempts only, as for a D1 run; the run loop is the export's total less the attempts
    assert s["tokens"]["output"] == 35
    assert s["loop_tokens"]["output"] == 99 - 35
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
    assert doc["per_step"]["0.1.8"]["all"][0]["tokens_out_median"] == 5000
    assert doc["per_step"]["0.1.8"]["Linux"][0]["runs"] == 1

    assert br.main([*argv, "--release", "9.9"]) == 1


@pytest.mark.parametrize(
    ("target", "os_name"),
    [
        ("C:/dev/companion/runs/x/state.json", "Windows"),
        ("C:\\dev\\companion\\x.md", "Windows"),
        ("/c/Users/eng/dev/companion/x.md", "Windows"),  # Git Bash
        ("/mnt/c/Users/eng/dev/companion/x.md", "Windows"),  # WSL on the Windows drive
        ("cd /c/Users/eng/dev && tsl verify x", "Windows"),  # a Bash command line
        ("/Users/eng/dev/companion/x.md", "macOS"),
        ("tsl verify '/Users/eng/dev/x.md'", "macOS"),
        ("/home/eng/companion/x.md", "Linux"),
        ("tsl next run_x --json", "unknown"),
    ],
)
def test_infer_os(target: str, os_name: str) -> None:
    assert br.infer_os(json.dumps({"target": target}) + "\n") == os_name


def test_timeouts_are_slips() -> None:
    fb = {"kind": "verifier", "gate_failures": [{"id": "H3", "detail": "lint timed out"}]}
    assert br.retry_reason(fb, "retry_verifier") == "lint"
    fb = {"kind": "verifier", "gate_failures": [{"id": "H3", "detail": "docker info failed"}]}
    assert br.retry_reason(fb, "retry_verifier") == "verifier"


def test_release_order_and_units() -> None:
    assert sorted(["0.1.10", "0.1.8", "0.1.7", "0.2.0"], key=br.release_key) == [
        "0.1.7",
        "0.1.8",
        "0.1.10",
        "0.2.0",
    ]
    assert br._k(999950) == "1.0M"
    assert br._k(999) == "999"
    assert br._k(1500) == "1.5k"


def test_no_start_time_is_not_recorded(companion: Path) -> None:
    p = companion / f"runs/{RUN}/state.json"
    st = json.loads(p.read_text(encoding="utf-8"))
    del st["steps"][0]["attempts"][0]["started_at"]
    p.write_text(json.dumps(st), encoding="utf-8")
    s = br.run_summary(br.load_run(br.Source(companion), {"run_id": RUN}))
    assert s["steps"]["split"]["ai_ms"] is None and s["ai_ms"] is None
    assert s["steps"]["ut"]["ai_ms"] == 25 * 60000
    run = br.load_run(br.Source(companion), {"run_id": RUN})
    row = br.group_steps([run], {RUN: s})[0]
    assert row["ai_min_median"] is None and row["ai_runs"] == 0


def test_release_filter_uses_pinned_tsl(companion: Path, tmp_path: Path, capsys: Any) -> None:
    st = tmp_path / "set.json"
    st.write_text(json.dumps({"runs": [{"run_id": RUN}, {"run_id": RUN2}]}), encoding="utf-8")
    argv = ["--companion", str(companion), "--set", str(st), "--metrics-dir", str(tmp_path / "x")]
    assert br.main([*argv, "--release", "0.1.7", "--format", "json"]) == 0
    doc = json.loads(capsys.readouterr().out)
    assert [r["run_id"] for r in doc["runs"]] == [RUN]


def test_bad_export_and_bad_bytes_do_not_crash(companion: Path, tmp_path: Path) -> None:
    exp = tmp_path / "metrics"
    _write(exp, f"{RUN}.json", "{not json")
    (companion / f"runs/{RUN}/tool-log.jsonl").write_bytes(b"\xff\xfe C:/dev \n")
    run = br.load_run(br.Source(companion), {"run_id": RUN}, exp)
    s = br.run_summary(run)
    assert s["tokens"] is None and s["loop_tokens"] is None
    assert run["os"] == "unknown"
