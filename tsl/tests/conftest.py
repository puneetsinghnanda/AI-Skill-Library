from __future__ import annotations

import os
from pathlib import Path

import pytest

from helpers import World, make_world


@pytest.fixture(autouse=True)
def _git_identity(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Git needs an identity for commits in temp repos; nothing outside tmp is touched."""
    for k, v in {
        "GIT_AUTHOR_NAME": "Test Engineer",
        "GIT_AUTHOR_EMAIL": "eng@example.com",
        "GIT_COMMITTER_NAME": "Test Engineer",
        "GIT_COMMITTER_EMAIL": "eng@example.com",
        "GIT_CONFIG_NOSYSTEM": "1",
        "HOME": str(tmp_path / "home"),
    }.items():
        monkeypatch.setenv(k, v)
    (tmp_path / "home").mkdir(exist_ok=True)
    gitconfig = tmp_path / "home" / ".gitconfig"
    gitconfig.write_text('[init]\n\tdefaultBranch = main\n[protocol "file"]\n\tallow = always\n')
    os.environ.pop("TSL_SESSION_ID", None)


@pytest.fixture
def world(tmp_path: Path) -> World:
    return make_world(tmp_path)


@pytest.fixture
def bare_world(tmp_path: Path) -> World:
    return make_world(tmp_path, signed_pack=False)
