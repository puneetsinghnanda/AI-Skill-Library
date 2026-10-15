"""tsl state start --ticket-file writes the run's ticket snapshot (SDD-01 §5.1, O-07)."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import yaml

from e2e_steps import SESSION, next_action
from helpers import World, git
from tsl.schemas.registry import errors

LOCK = "runs/active/ABC-142__brownfield-change.lock"
SAMPLE = (
    "---\r\nschema: ticket-snapshot.v1\r\nrun_id: run_01JC00ABC14200000000000000\r\n"
    "ticket: ABC-142\r\nsource: file\r\nfetched_at: '2026-10-01T09:00:00Z'\r\n"
    "title: 'Show 30 days of order history'\r\nissue_type: Story\r\n---\r\n"
    "# ABC-142 Show 30 days of order history\r\n\r\nNewest first.\r\n"
)


def _start(w: World, *extra: str, ticket: str = "ABC-142") -> tuple[int, dict[str, Any]]:
    code, env, _, err = w.cli(
        ["state", "start", "brownfield-change", ticket, *extra, "--json"],
        session=SESSION,
    )
    assert env is not None, err
    return code, env


def _snapshot(w: World, run_id: str) -> tuple[dict[str, Any], str]:
    text = (w.companion / f"artifacts/ABC-142/{run_id}/ticket.md").read_text(encoding="utf-8")
    _, fm, body = text.split("---\n", 2)
    return yaml.safe_load(fm), body


def test_ticket_file_with_front_matter_is_snapshotted_and_pushed(world: World) -> None:
    src = world.base / "ABC-142.md"
    raw = b"\xef\xbb\xbf" + SAMPLE.encode()
    src.write_bytes(raw)
    code, env = _start(world, "--ticket-file", str(src))
    assert code == 0, env
    run_id = env["data"]["run_id"]
    rel = f"artifacts/ABC-142/{run_id}/ticket.md"
    assert env["data"]["ticket_snapshot"] == rel
    fm, body = _snapshot(world, run_id)
    assert errors("ticket-snapshot.v1", fm) == []
    assert fm["run_id"] == run_id and fm["ticket"] == "ABC-142" and fm["source"] == "file"
    assert fm["title"] == "Show 30 days of order history" and fm["issue_type"] == "Story"
    assert fm["source_sha256"] == hashlib.sha256(raw).hexdigest()
    assert body == "# ABC-142 Show 30 days of order history\n\nNewest first.\n"
    # committed with the lock in the start commit, so it reaches the companion's origin
    assert git(world.companion_remote, "show", f"main:{rel}").startswith("---\nschema:")
    code, nxt = next_action(world, run_id)
    assert code == 0, nxt
    ticket = next(i for i in nxt["data"]["inputs"] if i["path"] == rel)
    assert ticket["schema"] == "ticket-snapshot.v1" and ticket["sha256"]


def test_plain_markdown_takes_its_title_from_the_first_heading(world: World) -> None:
    src = world.base / "t.md"
    src.write_text("# Show order history\n\nNewest first.\n", encoding="utf-8")
    code, env = _start(world, "--ticket-file", str(src))
    assert code == 0, env
    fm, body = _snapshot(world, env["data"]["run_id"])
    assert errors("ticket-snapshot.v1", fm) == []
    assert fm["title"] == "Show order history" and "issue_type" not in fm
    assert body == "# Show order history\n\nNewest first.\n"


def _refused(world: World, src: Path, ticket: str = "ABC-142") -> dict[str, Any]:
    code, env = _start(world, "--ticket-file", str(src), ticket=ticket)
    assert code != 0 and env["code"] == "E-USE-01", env
    assert not (world.companion / LOCK).exists()
    assert LOCK not in git(world.companion_remote, "ls-tree", "-r", "--name-only", "main")
    return env


def test_bad_ticket_files_are_refused_before_the_lock(world: World) -> None:
    other = world.base / "other.md"
    other.write_text("---\nticket: ABC-150\n---\n# Other\n", encoding="utf-8")
    assert "ABC-150" in _refused(world, other)["message"]
    empty = world.base / "empty.md"
    empty.write_text("---\ntitle: x\n---\n\n", encoding="utf-8")
    _refused(world, empty)
    binary = world.base / "bin.md"
    binary.write_bytes(b"# x\n\0\0")
    _refused(world, binary)
    big = world.base / "big.md"
    big.write_text("# x\n" + "a" * 300_000, encoding="utf-8")
    _refused(world, big)
    broken = world.base / "broken.md"
    broken.write_text("---\ntitle: [unclosed\n---\n# x\n", encoding="utf-8")
    _refused(world, broken)
    _refused(world, world.base / "missing.md")


def test_empty_ticket_file_argument_means_none(world: World) -> None:
    # /truminds:run passes "$2", which is empty when the engineer gives no file
    code, env = _start(world, "--ticket-file", "")
    assert code == 0, env
    assert env["data"]["ticket_snapshot"] is None
    run_id = env["data"]["run_id"]
    assert not (world.companion / f"artifacts/ABC-142/{run_id}/ticket.md").exists()


def test_ticket_text_with_a_secret_or_personal_data_is_refused(world: World) -> None:
    # the snapshot is committed and pushed, so it gets the same H4 scan as an artifact
    leaky = world.base / "leaky.md"
    leaky.write_text("# x\nContact jane.doe@realmail.com about it.\n", encoding="utf-8")
    env = _refused(world, leaky)
    assert "line 2" in env["message"] and "realmail" not in env["message"]
    ok = world.base / "ok.md"
    ok.write_text("# x\nWrite to orders@example.com.\n", encoding="utf-8")
    code, env = _start(world, "--ticket-file", str(ok))
    assert code == 0, env
