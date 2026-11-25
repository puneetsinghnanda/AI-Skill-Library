"""pydantic and pydantic-core are pinned to the tested versions (roadmap C5).

`uv tool install` ignores uv.lock, so a version range in pyproject.toml installs the newest release.
On Windows, App Control blocked a new pydantic-core DLL and every tsl command failed on import.
CI's `uv sync --locked` already fails when pyproject.toml and uv.lock disagree; these tests keep
the pins exact and the pair installable.
"""

from __future__ import annotations

import re
import tomllib
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PINNED = ("pydantic", "pydantic-core")
EXACT = re.compile(r"==\s*([0-9][0-9A-Za-z.]*)")


def _pins() -> dict[str, str]:
    """Name -> exact version for PINNED, from pyproject.toml; a non-exact spec maps to ''."""
    deps = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    out: dict[str, str] = {}
    for dep in deps["dependencies"]:
        m = re.fullmatch(r"([A-Za-z0-9_.-]+)\s*(.*)", dep.strip())
        assert m, dep
        name = m.group(1).lower().replace("_", "-")
        if name in PINNED:
            exact = EXACT.fullmatch(m.group(2).strip())
            out[name] = exact.group(1) if exact else ""
    return out


def test_pins_are_exact() -> None:
    pins = _pins()
    for name in PINNED:
        assert pins.get(name), f"{name} must be pinned with == in pyproject.toml, found none"


def test_the_pinned_pair_is_installed_and_installable() -> None:
    pins = _pins()
    # The installed pydantic is the pinned one, so its requirements below are the pin's.
    assert metadata.version("pydantic") == pins["pydantic"], (
        f"installed pydantic {metadata.version('pydantic')}, pinned {pins['pydantic']}: run uv sync"
    )
    assert metadata.version("pydantic-core") == pins["pydantic-core"]
    # pydantic requires one exact pydantic-core; a pair that disagrees cannot be installed.
    wanted = [
        r
        for r in metadata.requires("pydantic") or []
        if re.match(r"pydantic[-_]core\b", r, re.I) and "extra ==" not in r
    ]
    assert len(wanted) == 1, wanted
    exact = EXACT.search(wanted[0])
    assert exact and exact.group(1) == pins["pydantic-core"], (
        f"pydantic {pins['pydantic']} requires {wanted[0]}, "
        f"pyproject.toml pins pydantic-core=={pins['pydantic-core']}"
    )
