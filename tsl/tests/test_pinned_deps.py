"""pydantic and pydantic-core are pinned to the tested versions (roadmap C5).

`uv tool install` ignores uv.lock, so a version range in pyproject.toml installs the newest release.
On Windows, App Control blocked a new pydantic-core DLL and every tsl command failed on import.
"""

from __future__ import annotations

import re
import tomllib
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PINNED = ("pydantic", "pydantic-core")


def _declared() -> dict[str, str]:
    """Dependency name -> version specifier, from pyproject.toml."""
    deps = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"][
        "dependencies"
    ]
    out: dict[str, str] = {}
    for dep in deps:
        m = re.fullmatch(r"([A-Za-z0-9_.-]+)\s*(.*)", dep.strip())
        assert m, dep
        out[m.group(1).lower()] = m.group(2).strip()
    return out


def _locked() -> dict[str, str]:
    """Package name -> version, from uv.lock."""
    lock = tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))
    return {p["name"]: p["version"] for p in lock["package"] if "version" in p}


def test_pins_are_exact_and_equal_to_the_lock() -> None:
    declared, locked = _declared(), _locked()
    for name in PINNED:
        spec = declared.get(name)
        assert spec is not None and re.fullmatch(r"==[0-9][0-9A-Za-z.]*", spec), (
            f"{name} must be pinned with == in pyproject.toml, found {spec!r}"
        )
        assert spec[2:] == locked.get(name), (
            f"{name}: pyproject.toml pins {spec[2:]}, uv.lock has {locked.get(name)}; run `uv lock` and test"
        )


def test_core_pin_is_the_one_the_pinned_pydantic_requires() -> None:
    # pydantic requires one exact pydantic-core; a pair that disagrees cannot be installed.
    core = _declared()["pydantic-core"][2:]
    requires = metadata.requires("pydantic") or []
    wanted = [
        r for r in requires if re.match(r"pydantic[-_]core\b", r, re.I) and "extra ==" not in r
    ]
    assert wanted, requires
    assert any(f"=={core}" in r.replace(" ", "") for r in wanted), (
        f"pydantic {metadata.version('pydantic')} requires {wanted}, pyproject.toml pins pydantic-core=={core}"
    )
