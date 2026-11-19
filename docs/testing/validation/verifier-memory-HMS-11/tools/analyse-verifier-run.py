"""Line up sample-linux.py output with run-verifier.py step times: peak memory per step.

Usage: python3 analyse-verifier-run.py <samples-dir> <run-verifier out-dir>
"""

from __future__ import annotations

import csv
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

samples, run = Path(sys.argv[1]), Path(sys.argv[2])
ev = json.loads((run / "verifier-run.json").read_text())["events"]


def ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


wins = [(e["step"], ts(e["start"]), ts(e["start"]) + timedelta(seconds=e["seconds"])) for e in ev]


def step_of(t: datetime) -> str | None:
    for s, a, b in wins:
        if a <= t <= b + timedelta(seconds=0.3):
            return s
    return None


def num(x: str | None) -> float:
    return float(x) if x not in ("", None) else 0.0


C = list(csv.DictReader(open(samples / "containers.csv")))
M = list(csv.DictReader(open(samples / "machine.csv")))
print(f"{'step':9} {'secs':>5} {'peak MB':>8} {'%4GB':>5} {'anon':>6} {'file':>6} {'tmpfs':>6} {'host avail min GB':>18}")
for s, a, b in wins:
    cs = [c for c in C if step_of(ts(c["time_utc"])) == s]
    ms = [num(m["mem_available_gb"]) for m in M if a <= ts(m["time_utc"]) <= b]
    pk = max((num(c["peak_mb"]) for c in cs), default=0)

    def mx(k: str) -> float:
        return max((num(c[k]) for c in cs), default=0)

    low = f"{min(ms):18.2f}" if ms else f"{'-':>18}"
    print(f"{s:9} {(b - a).total_seconds():5.1f} {pk:8.0f} {pk / 4096 * 100:4.0f}% {mx('anon_mb'):6.0f} {mx('file_mb'):6.0f} {mx('shmem_mb'):6.0f} {low}")
before = [num(m["mem_available_gb"]) for m in M if ts(m["time_utc"]) < wins[0][1]]
during = [num(m["mem_available_gb"]) for m in M if wins[0][1] <= ts(m["time_utc"]) <= wins[-1][2]]
print("host available before:", round(max(before), 2) if before else "?", "GB; lowest during:", min(during) if during else "?")
