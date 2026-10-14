"""Regression: ULID run ids inside citation paths are not secrets (SKL-V12 false positive)."""

from tsl.harness import detectors


def test_run_id_path_near_key_word_is_not_a_secret() -> None:
    text = (
        "statement: signed with a key from the vault.\n"
        "cites:\n- artifacts/ABC-476/run_01JB2C3D4E5F6G7H8J9KMNPQRS/ticket.md#L12\n"
    )
    assert not [h for h in detectors.scan(text) if h.rule_id == "SEC-ENT-01"]


def test_real_high_entropy_token_near_key_is_still_flagged() -> None:
    text = "api key: Zx9Qw7Lm3Kp8Rt2Vb6Nc4Hd1Fg5Js0Ty\n"
    assert [h for h in detectors.scan(text) if h.rule_id == "SEC-ENT-01"]


def test_repo_plugin_validates_with_tsl() -> None:
    """The shipped plugin must pass `tsl validate`, not only its own structure tests."""
    import json
    import subprocess
    import sys
    from pathlib import Path

    plugin = Path(__file__).resolve().parents[2] / "plugins" / "truminds"
    if not plugin.is_dir():
        import pytest

        pytest.skip("plugin not present next to tsl")
    out = subprocess.run(
        [sys.executable, "-m", "tsl", "--json", "validate", str(plugin)],
        capture_output=True,
        text=True,
        check=False,
    )
    env = json.loads(out.stdout)
    assert env["ok"], env["message"]
