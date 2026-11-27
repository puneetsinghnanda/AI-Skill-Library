"""The test world's users never share an id seed (roadmap D3: CI green on three OSes).

A seed taken from hash(user) changed with Python's per-process hash salt, and now and then two
users drew the same key id: tests failed E-KEY-03 at random on macOS and Windows CI.
"""

from __future__ import annotations

import pytest

from helpers import USERS, World, id_seed


def test_the_seed_is_fixed_not_salted() -> None:
    # Fixed values: a seed that followed the hash salt would differ between runs.
    assert (id_seed("eng"), id_seed("tl")) == (2582995467, 1317962622)


def test_every_test_user_has_its_own_seed() -> None:
    users = sorted({*USERS, "adm"})  # adm is made by the admin tests
    assert len({id_seed(u) for u in users}) == len(users)


def test_the_world_refuses_two_users_with_one_seed(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("helpers.id_seed", lambda user: 7)
    with pytest.raises(AssertionError, match="share an id seed"):
        world.rt("biz")
