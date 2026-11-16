"""/tsl-gate Mod (hooks/register.tsx): argument parsing and display, run under Node with a fake host.

The Mod only passes arguments to `tsl gate`; a wrong parse could sign another gate, so the parse is
tested here. Skipped where Node cannot run TypeScript directly (needs Node 22.6 or newer).
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from conftest import PLUGIN

NODE = shutil.which("node")
FLAGS = ["--experimental-strip-types", "--no-warnings"]

HARNESS = Path(__file__).with_name("tsl_gate_mod_harness.ts")


def _node_runs_typescript(tmp: Path) -> bool:
    if not NODE:
        return False
    probe = tmp / "probe.ts"
    probe.write_text("const x: number = 1\nconsole.log(x)\n", encoding="utf-8")
    p = subprocess.run([NODE, *FLAGS, str(probe)], capture_output=True, text=True, check=False)
    return p.returncode == 0 and p.stdout.strip() == "1"


def test_tsl_gate_mod_parses_and_renders(tmp_path: Path) -> None:
    if not _node_runs_typescript(tmp_path):
        pytest.skip("node with TypeScript type stripping is not available")
    src = (PLUGIN / "hooks" / "register.tsx").read_text(encoding="utf-8")
    assert "import type { Register } from 'claude-code'" in src
    src = src.replace("import type { Register } from 'claude-code'", "type Register = any")
    for fn in ("parseArgs", "render"):
        assert f"\nfunction {fn}(" in src
        src = src.replace(f"\nfunction {fn}(", f"\nexport function {fn}(")
    (tmp_path / "reg.ts").write_text(src, encoding="utf-8")
    shutil.copy(HARNESS, tmp_path / "t.ts")
    cmd = [NODE or "node", *FLAGS, "t.ts"]
    p = subprocess.run(cmd, cwd=tmp_path, capture_output=True, text=True, check=False)
    assert p.returncode == 0, p.stderr[-2000:]
    assert "all checks passed" in p.stdout
