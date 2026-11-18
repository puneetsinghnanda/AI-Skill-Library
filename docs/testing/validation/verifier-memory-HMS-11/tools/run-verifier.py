"""Run tsl's DockerVerifier as the unit-test step does (with coverage) and log each step's start and length.

Usage (from the folder that holds AI-Skill-Library):
  uv run --project AI-Skill-Library/tsl python memory-diagnosis-yash/tools/run-verifier.py \
      AI-Skill-Library/plugins/truminds <product-repo> <out-dir>
Writes only to <out-dir>: no run records are touched. Pair it with sample-linux.py for memory, and
analyse-verifier-run.py to line the samples up with the steps.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from tsl.core.jsonio import read_yaml
from tsl.harness import verifier as v

plugin, product, out = (Path(x) for x in sys.argv[1:4])
out.mkdir(parents=True, exist_ok=True)
prof = read_yaml(plugin / "verifiers" / "node-22@1" / "profile.yaml")
events: list[dict[str, object]] = []
real_run = subprocess.run


def timed_run(cmd, *a, **kw):  # type: ignore[no-untyped-def]
    step = None
    if isinstance(cmd, list) and cmd[:2] == ["docker", "run"]:
        step = next((s for s, spec in prof["steps"].items() if spec["cmd"] == cmd[-1]), "?")
    t0 = datetime.now(timezone.utc)
    m0 = time.monotonic()
    try:
        return real_run(cmd, *a, **kw)
    finally:
        if step:
            events.append({"step": step, "start": t0.isoformat(), "seconds": round(time.monotonic() - m0, 2)})


v.subprocess.run = timed_run  # type: ignore[assignment]
print("docker flags:", " ".join(v.docker_command(prof, "test", Path("/w"), Path("/o"))[2:-4]), flush=True)
src = v.export_source(product)
try:
    res = v.DockerVerifier().run(prof, src, out / "verifier", with_coverage=True)
finally:
    shutil.rmtree(src, ignore_errors=True)
summary = {
    "image": res.image_digest,
    "steps": [{"name": s.name, "status": s.status, "exit": s.exit_code, "ms": s.duration_ms} for s in res.steps],
    "events": events,
}
(out / "verifier-run.json").write_text(json.dumps(summary, indent=1))
print(json.dumps(summary["steps"]))
