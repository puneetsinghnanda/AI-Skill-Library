"""Mods module (hooks/register.tsx), run under Node with a fake host.

- /tsl-gate only passes arguments to `tsl gate`; a wrong parse could sign another gate, so the
  parse is tested here.
- The progress panel must never block the session and never show a wrong run: the reading of
  tsl's answer, the rows it draws, the refresh triggers and the failure cases are tested here.
  How the engine draws the rows is checked with `claude plugin test`, which CI cannot run.

Skipped where Node cannot run TypeScript directly (needs Node 22.6 or newer).
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from conftest import PLUGIN

NODE = shutil.which("node")
FLAGS = ["--experimental-strip-types", "--no-warnings"]

HERE = Path(__file__).parent

# What the engine provides, for Node: the state helpers over a plain Map on the fake host.
FAKE_ENGINE = """type Register = any
type RenderElement = any
type Panel = any
type Progress = any
const atom = (ref: any, initial: any, _o?: any) => ({ key: ref.key, initial })
const read = async ($: any, a: any) => ($.__store.has(a.key) ? $.__store.get(a.key) : a.initial)
const update = async ($: any, a: any, fn: any) => {
  const v = fn(await read($, a))
  $.__store.set(a.key, v)
  return v
}
"""

IMPORTS = (
    "import { atom, read, update } from 'claude-code'\n",
    "import type { Register, RenderElement } from 'claude-code'\n",
    "import type { Panel, Progress } from '../types'\n",
)

EXPORTS = ("parseArgs", "render", "parseProgress", "isTslCommand", "isUpdateCommand", "panelRows")


def _node_runs_typescript(tmp: Path) -> bool:
    if not NODE:
        return False
    probe = tmp / "probe.ts"
    probe.write_text("const x: number = 1\nconsole.log(x)\n", encoding="utf-8")
    p = subprocess.run([NODE, *FLAGS, str(probe)], capture_output=True, text=True, check=False)
    return p.returncode == 0 and p.stdout.strip() == "1"


def _run(tmp: Path, harness: str) -> subprocess.CompletedProcess[str]:
    if not _node_runs_typescript(tmp):
        pytest.skip("node with TypeScript type stripping is not available")
    src = (PLUGIN / "hooks" / "register.tsx").read_text(encoding="utf-8")
    for line in IMPORTS:
        assert line in src, line
        src = src.replace(line, "")
    src = FAKE_ENGINE + src
    for fn in EXPORTS:
        assert f"\nfunction {fn}(" in src, fn
        src = src.replace(f"\nfunction {fn}(", f"\nexport function {fn}(")
    (tmp / "reg.ts").write_text(src, encoding="utf-8")
    shutil.copy(HERE / harness, tmp / "t.ts")
    cmd = [NODE or "node", *FLAGS, "t.ts"]
    return subprocess.run(cmd, cwd=tmp, capture_output=True, text=True, check=False)


def test_tsl_gate_mod_parses_and_renders(tmp_path: Path) -> None:
    p = _run(tmp_path, "tsl_gate_mod_harness.ts")
    assert p.returncode == 0, p.stderr[-2000:]
    assert "all checks passed" in p.stdout


def test_progress_panel_reads_draws_and_never_blocks(tmp_path: Path) -> None:
    p = _run(tmp_path, "tsl_panel_mod_harness.ts")
    assert p.returncode == 0, p.stderr[-3000:]
    assert "progress panel: all checks passed" in p.stdout
