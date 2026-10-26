"""tsl prints its status marks on a console whose code page is not UTF-8."""

from __future__ import annotations

import os
import subprocess
import sys


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
