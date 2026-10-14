"""Core contracts: error catalogue vs registry, envelope schema, version pin, CLI globals."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

import tsl
from helpers import World
from tsl.core.envelope import make
from tsl.core.errors import CATALOGUE, TslError, render
from tsl.core.hashing import sha256_bytes, sha256_text
from tsl.core.ids import IdFactory
from tsl.core.paths import safe_ticket
from tsl.schemas.registry import errors, schemas_root

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = (ROOT / "docs" / "architecture" / "registry.md").read_text(encoding="utf-8")
SDD03 = (ROOT / "docs" / "design" / "SDD-03-harness.md").read_text(encoding="utf-8")


def _registry_rows() -> dict[str, str]:
    rows = {}
    for m in re.finditer(r"^\| (E-[A-Z0-9]+-\d+) \| [^|]+ \| ([^|]+) \|", REGISTRY, re.M):
        rows[m.group(1)] = m.group(2).strip()
    return rows


def test_every_cli_code_in_registry_is_in_the_catalogue() -> None:
    rows = _registry_rows()
    cli = {c: e for c, e in rows.items() if re.match(r"^\d{1,2}\b", e) or e.startswith("deny")}
    missing = sorted(c for c in cli if c not in CATALOGUE)
    assert missing == []


def test_catalogue_exit_codes_match_registry() -> None:
    for code, exit_ in _registry_rows().items():
        m = re.match(r"^(\d{1,2})\b", exit_)
        if m and code in CATALOGUE and code != "E-HOOK-01":
            assert CATALOGUE[code].exit == int(m.group(1)), code


def test_every_catalogue_code_is_registered() -> None:
    for code in CATALOGUE:
        assert code in REGISTRY or code in SDD03, f"{code} not in registry or SDD-03 §14.1"


def test_catalogue_entries_are_complete() -> None:
    for code, d in CATALOGUE.items():
        assert d.exit in (0, 1, 2, 3, 4, 5, 10), code
        assert d.message and d.next, code
        assert len(render(d.message)) <= 300


def test_tsl_error_formats_and_truncates() -> None:
    e = TslError("E-RUN-04", run_id="run_X")
    assert e.exit == 3 and "run_X" in e.message
    assert TslError("E-USE-01", "x" * 400).message == "x" * 300
    with pytest.raises(KeyError):
        TslError("E-NOPE-01")


def test_envelope_validates_against_tsl_output() -> None:
    env = make("E-LOCK-01", 3, "locked", "/truminds:resume run_X", {"run_id": "run_X"}, None)
    obj = json.loads(env.to_json())
    assert errors("tsl-output.v1", obj) == []
    assert obj["ok"] is False and obj["tsl_version"] == tsl.__version__
    ok = json.loads(
        make("OK", 0, "fine", None, {}, [{"code": "E-NET-01", "message": "q"}]).to_json()
    )
    assert ok["ok"] is True and errors("tsl-output.v1", ok) == []


def test_version_equals_plugin_version() -> None:
    pj = json.loads((ROOT / "plugins/truminds/.claude-plugin/plugin.json").read_text())
    assert tsl.__version__ == pj["version"]


def test_version_flag_fast_path() -> None:
    p = subprocess.run(
        [sys.executable, "-m", "tsl", "--version"], capture_output=True, text=True, check=False
    )
    assert p.returncode == 0 and p.stdout.strip() == f"tsl {tsl.__version__}"


def test_schemas_found() -> None:
    assert (schemas_root() / "index.json").is_file()


def test_hash_is_lf_normalised() -> None:
    assert sha256_bytes(b"a\r\nb\r") == sha256_bytes(b"a\nb\n") == sha256_text("a\nb\n")


def test_ids_are_ulids_and_seeded() -> None:
    from helpers import START
    from tsl.core.clock import FrozenClock

    f1, f2 = IdFactory(FrozenClock(START), seed=7), IdFactory(FrozenClock(START), seed=7)
    a, b = f1.new("run"), f2.new("run")
    assert a == b and re.fullmatch(r"run_[0-9A-HJKMNP-TV-Z]{26}", a)
    assert f1.new("run") != a


def test_safe_ticket() -> None:
    assert safe_ticket("abc-142/x y") == "ABC-142_X_Y"


def test_unknown_command_is_usage_error(world: World) -> None:
    code, env, _, _ = world.cli(["no-such-command", "--json"])
    assert code == 1 and env is not None and env["code"] == "E-USE-01"


def test_not_in_companion_repo(world: World, tmp_path: Path) -> None:
    empty = tmp_path / "nowhere"
    empty.mkdir()
    code, env, _, _ = world.cli(["state", "show", "--json"], repo=empty)
    assert code == 1 and env is not None and env["code"] == "E-REPO-01"


def test_internal_error_has_log_id_and_no_traceback(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    import tsl.state.service as svc

    def boom(*a: object, **k: object) -> None:
        raise RuntimeError("secret-ish detail")

    monkeypatch.setattr(svc, "show", boom)
    code, env, out, _ = world.cli(["state", "show", "--json"])
    assert code == 1 and env is not None and env["code"] == "E-INT-01"
    assert "Traceback" not in out and "secret-ish" not in out
    assert env["data"]["log_id"] in (world.rt().home.logs / "tsl.log").read_text()


def test_json_flag_anywhere_and_human_mode(world: World) -> None:
    code, env, _, _ = world.cli(["state", "--json", "show"])
    assert code == 0 and env is not None and env["data"]["runs"] == []
    code, _, out, _ = world.cli(["state", "show"])
    assert code == 0 and "0 run(s)" in out


def test_help_for_every_group(world: World) -> None:
    for group in (
        "keys",
        "state",
        "review",
        "context",
        "eval",
        "improve",
        "events",
        "harness",
        "companion",
    ):
        code, _, out, _ = world.cli([group, "--help"])
        assert code == 0 and "Usage" in out, group


def test_log_redaction() -> None:
    from tsl.core.log import redact

    text = redact(
        {"token": "abc", "msg": "Bearer eyJhbGciOi.eyJzdWIi.sig and -----BEGIN PRIVATE KEY-----x"}
    )
    assert "abc" not in json.dumps(text) and "eyJhbGciOi" not in json.dumps(text)


def test_jsonpath_filters_both_styles() -> None:
    # SDD-03 §5.3 kind checks use `?(@.k!='v')`; eval assertions use `?k=='v'`
    from tsl.harness.jsonpath import PathError, select

    d = {"a": [{"change": "new", "m": 1}, {"change": "old", "m": 2}]}
    assert select(d, "$.a[?(@.change!='new')].m") == [2]
    assert select(d, "$.a[?(@.change=='new')].m") == [1]
    assert select(d, "a[?change=='new'].m") == [1]
    with pytest.raises(PathError):
        select(d, "$.a[?(@.change=='new'].m")
