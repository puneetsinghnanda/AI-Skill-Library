"""The test world's users never share an id seed (roadmap D3: CI green on three OSes).

The seed was hash(user) % 1000, which Python salts per process: now and then two users drew the
same key id at the same frozen instant and tests failed E-KEY-03 on macOS and Windows CI.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from helpers import USERS, id_seed

TEST_USERS = sorted({*USERS, "adm"})  # adm is made by the admin tests


def test_every_test_user_has_its_own_seed() -> None:
    seeds = {u: id_seed(u) for u in TEST_USERS}
    assert len(set(seeds.values())) == len(seeds), seeds


def test_the_seed_does_not_depend_on_the_hash_salt() -> None:
    code = "import sys; from helpers import id_seed; print(id_seed('eng'))"
    env = {**os.environ, "PYTHONPATH": os.pathsep.join(sys.path)}
    here = Path(__file__).resolve().parent
    out = {
        subprocess.run(
            [sys.executable, "-c", code],
            env={**env, "PYTHONHASHSEED": salt},
            cwd=here,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        for salt in ("0", "335", "360")
    }
    assert out == {str(id_seed("eng"))}
