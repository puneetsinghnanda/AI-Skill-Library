from __future__ import annotations

from helpers import World


def test_world_builds_signed_pack(world: World) -> None:
    code, env, out, err = world.cli(["context", "status", "--json"], user="eng")
    assert env is not None, (out, err)
    assert code == 0, env
    assert env["data"]["state"] == "fresh"
