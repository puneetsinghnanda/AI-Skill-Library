#!/usr/bin/env python3
"""Memory sampler for Linux (native Docker, cgroup v2). Counterpart of sample-v2.ps1.

Samples every --interval seconds (default 0.25) until Ctrl+C or --duration:
  <out>/machine.csv     host totals (MemAvailable, used, swap) + run step if --companion/--run-id given
  <out>/containers.csv  every running container: memory.current, memory.peak, anon, file, shmem (tmpfs)
  <out>/procs.csv       processes grouped by role (claude, tsl-hook, tsl, docker-cli, node, python, other top)
                        with count, RSS and PSS sums

memory.peak is the kernel's high-water mark for the container's cgroup, so a short spike between two
samples is still caught (as long as the container lives until one sample after it).

Usage:
  python3 sample-linux.py --out ../samples/linux-<label> [--run-id run_X --companion /path/to/companion]
Stdlib only. Reads /proc and /sys/fs/cgroup; needs no root for your own processes and docker cgroups.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

CG = Path("/sys/fs/cgroup/system.slice")
GB = 1024**3


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def meminfo() -> dict[str, int]:
    out = {}
    for line in Path("/proc/meminfo").read_text().splitlines():
        k, v = line.split(":", 1)
        out[k] = int(v.split()[0]) * 1024
    return out


def read_int(p: Path) -> int | None:
    try:
        return int(p.read_text().split()[0])
    except (OSError, ValueError):
        return None


def mem_stat(p: Path) -> dict[str, int]:
    try:
        return {k: int(v) for k, v in (ln.split() for ln in p.read_text().splitlines())}
    except (OSError, ValueError):
        return {}


def containers() -> list[dict[str, object]]:
    rows = []
    if not CG.is_dir():
        return rows
    for d in CG.glob("docker-*.scope"):
        cid = d.name[len("docker-") : -len(".scope")]
        st = mem_stat(d / "memory.stat")
        rows.append(
            {
                "id": cid[:12],
                "current": read_int(d / "memory.current"),
                "peak": read_int(d / "memory.peak"),
                "max": (d / "memory.max").read_text().strip() if (d / "memory.max").exists() else "",
                "anon": st.get("anon"),
                "file": st.get("file"),
                "shmem": st.get("shmem"),
            }
        )
    return rows


def role(cmd: str, comm: str) -> str:
    c = cmd.lower()
    if "tsl-hook" in c or "hook-run" in c:
        return "tsl-hook"
    argv0 = c.split(" ", 1)[0].rsplit("/", 1)[-1]
    # match the executable only: a path argument such as /tmp/claude-1000/... is not Claude Code
    if comm == "claude" or argv0 == "claude" or "@anthropic-ai/claude-code" in c:
        return "claude"
    if "/bin/tsl" in c or " tsl " in f" {c} " or c.startswith("tsl "):
        return "tsl"
    if comm in ("docker", "com.docker.cli") or c.startswith("docker "):
        return "docker-cli"
    if comm in ("dockerd", "containerd", "containerd-shim", "containerd-shim-runc-v2"):
        return "docker-daemon"
    if comm.startswith("node"):
        return "node"
    if comm.startswith("python"):
        return "python"
    return "other"


def procs() -> list[tuple[str, str, int, int | None]]:
    out = []
    for p in Path("/proc").iterdir():
        if not p.name.isdigit():
            continue
        try:
            comm = (p / "comm").read_text().strip()
            cmd = (p / "cmdline").read_bytes().replace(b"\0", b" ").decode("utf-8", "replace").strip()
            rss = 0
            for line in (p / "status").read_text().splitlines():
                if line.startswith("VmRSS:"):
                    rss = int(line.split()[1]) * 1024
            pss = None
            try:
                for line in (p / "smaps_rollup").read_text().splitlines():
                    if line.startswith("Pss:"):
                        pss = int(line.split()[1]) * 1024
            except OSError:
                pass
        except (OSError, ValueError):
            continue
        if rss:
            out.append((role(cmd, comm), comm, rss, pss))
    return out


def run_step(companion: Path | None, run_id: str | None) -> tuple[str, str, str]:
    if not companion or not run_id:
        return "", "", ""
    try:
        s = json.loads((companion / "runs" / run_id / "state.json").read_text())
        for st in s.get("steps", []):
            if st.get("status") in ("IN_PROGRESS", "RUNNING"):
                return s.get("status", ""), st["id"], str(len(st.get("attempts", [])))
        return s.get("status", ""), "", ""
    except (OSError, ValueError, KeyError):
        return "", "", ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--interval", type=float, default=0.25)
    ap.add_argument("--duration", type=float, default=0, help="seconds; 0 = until Ctrl+C or SIGTERM")
    ap.add_argument("--run-id")
    ap.add_argument("--companion", type=Path)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    stop = {"v": False}
    signal.signal(signal.SIGTERM, lambda *_: stop.update(v=True))
    signal.signal(signal.SIGINT, lambda *_: stop.update(v=True))
    fm = open(out / "machine.csv", "w", newline="")
    fc = open(out / "containers.csv", "w", newline="")
    fp = open(out / "procs.csv", "w", newline="")
    wm, wc, wp = csv.writer(fm), csv.writer(fc), csv.writer(fp)
    wm.writerow(["time_utc", "status", "step", "attempt", "mem_total_gb", "mem_available_gb",
                 "mem_used_gb", "swap_used_gb", "containers"])
    wc.writerow(["time_utc", "container", "current_mb", "peak_mb", "limit", "anon_mb", "file_mb",
                 "shmem_mb"])
    wp.writerow(["time_utc", "role", "count", "rss_mb", "pss_mb", "top_comm"])
    t0 = time.monotonic()
    n = 0
    while not stop["v"] and not (a.duration and time.monotonic() - t0 >= a.duration):
        ts = now()
        mi = meminfo()
        cs = containers()
        status, step, attempt = run_step(a.companion, a.run_id)
        used = mi["MemTotal"] - mi["MemAvailable"]
        swap = mi["SwapTotal"] - mi["SwapFree"]
        wm.writerow([ts, status, step, attempt, round(mi["MemTotal"] / GB, 2),
                     round(mi["MemAvailable"] / GB, 3), round(used / GB, 3), round(swap / GB, 3), len(cs)])
        mb = lambda v: "" if v is None else round(v / 1024**2, 1)  # noqa: E731
        for c in cs:
            wc.writerow([ts, c["id"], mb(c["current"]), mb(c["peak"]), c["max"], mb(c["anon"]),
                         mb(c["file"]), mb(c["shmem"])])
        if n % max(1, int(1 / a.interval)) == 0:  # process table once a second; it is the costly part
            groups: dict[str, list] = {}
            for r, comm, rss, pss in procs():
                g = groups.setdefault(r, [0, 0, 0, {}])
                g[0] += 1
                g[1] += rss
                g[2] += pss or 0
                g[3][comm] = g[3].get(comm, 0) + rss
            for r, (cnt, rss, pss, comms) in sorted(groups.items()):
                top = max(comms, key=comms.get)
                wp.writerow([ts, r, cnt, round(rss / 1024**2, 1), round(pss / 1024**2, 1), top])
        n += 1
        if n % 20 == 0:
            for f in (fm, fc, fp):
                f.flush()
        time.sleep(a.interval)
    for f in (fm, fc, fp):
        f.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
