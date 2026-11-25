"""pydantic and pydantic-core are pinned to the tested versions (roadmap C5).

`uv tool install` ignores uv.lock, so a version range in pyproject.toml installs the newest release.
On Windows, App Control blocked a new pydantic-core DLL and every tsl command failed on import.
CI's `uv sync --locked` already fails when pyproject.toml and uv.lock disagree; these tests keep
the pins exact and the pair installable.
"""

from __future__ import annotations

import tomllib
from importlib import metadata
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

ROOT = Path(__file__).resolve().parents[1]
PINNED = ("pydantic", "pydantic-core")


def _exact(req: Requirement) -> str | None:
    """The version of a single `==` specifier (no wildcard), else None."""
    specs = list(req.specifier)
    if len(specs) == 1 and specs[0].operator in ("==", "===") and "*" not in specs[0].version:
        return specs[0].version
    return None


def _base(req: Requirement) -> bool:
    """A requirement of the plain install, not of an extra such as pydantic[email]."""
    return req.marker is None or req.marker.evaluate({"extra": ""})


def _pins() -> dict[str, str | None]:
    """Name -> exact pinned version for PINNED in pyproject.toml (None when not exact)."""
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    reqs = [Requirement(d) for d in project["dependencies"]]
    return {
        canonicalize_name(r.name): _exact(r) for r in reqs if canonicalize_name(r.name) in PINNED
    }


def test_pins_are_exact() -> None:
    pins = _pins()
    for name in PINNED:
        assert pins.get(name), f"{name} must be pinned with == in pyproject.toml, found {pins}"


def test_the_pinned_pair_is_installed_and_installable() -> None:
    pins = _pins()
    pyd, core = pins.get("pydantic"), pins.get("pydantic-core")
    assert pyd and core, f"pydantic and pydantic-core must be pinned with ==, found {pins}"
    # The installed pydantic is the pinned one, so its requirements below are the pin's.
    assert metadata.version("pydantic") == pyd, (
        f"installed pydantic {metadata.version('pydantic')}, pinned {pyd}: run uv sync"
    )
    assert metadata.version("pydantic-core") == core
    # pydantic requires one exact pydantic-core; a pair that disagrees cannot be installed.
    requires = [Requirement(r) for r in metadata.requires("pydantic") or []]
    wanted = [r for r in requires if canonicalize_name(r.name) == "pydantic-core" and _base(r)]
    assert len(wanted) == 1, wanted
    assert _exact(wanted[0]) == core, (
        f"pydantic {pyd} requires {wanted[0]}, pyproject.toml pins pydantic-core=={core}"
    )
