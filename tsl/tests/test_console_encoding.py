"""tsl prints its status marks on a console whose code page is not UTF-8."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_error_output_survives_a_cp1252_console(tmp_path: object) -> None:
    env = {**os.environ, "PYTHONIOENCODING": "cp1252", "PYTHONUTF8": "0"}
    p = subprocess.run(
        [sys.executable, "-m", "tsl", "next", "run_00000000000000000000000000"],
        capture_output=True,
        env=env,
        cwd=str(tmp_path),
        check=False,
    )
    assert b"UnicodeEncodeError" not in p.stderr
    assert "✖".encode() in p.stdout + p.stderr


def test_plain_success_output_survives_a_redirected_cp1252_stdout(tmp_path: object) -> None:
    """Issue #4: a valid `tsl validate` with stdout sent to a file exited 1 with no output on Windows."""
    plugin = Path(__file__).resolve().parents[2] / "plugins" / "truminds"
    env = {**os.environ, "PYTHONIOENCODING": "cp1252", "PYTHONUTF8": "0"}
    p = subprocess.run(
        [sys.executable, "-m", "tsl", "validate", str(plugin)],
        capture_output=True,
        env=env,
        cwd=str(tmp_path),
        check=False,
    )
    assert p.returncode == 0, p.stderr
    assert b"UnicodeEncodeError" not in p.stderr
    assert "✔".encode() in p.stdout
