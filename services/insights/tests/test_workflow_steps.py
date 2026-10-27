"""Workflow steps in the catalogue follow the file, even when it changed without a version bump."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.catalogue.sync import SyncResult, _workflows
from app.config import Settings
from tests.conftest import ROOT

SOURCE = ROOT / "plugins" / "truminds" / "workflows" / "brownfield-change.workflow.yaml"


def _write(root: Path, d: dict[str, Any]) -> None:
    folder = root / "plugins" / "truminds" / "workflows"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "nobump.workflow.yaml").write_text(yaml.safe_dump(d, sort_keys=False))


def _steps(owner_db: Engine, wid: str, ver: str) -> list[str]:
    with owner_db.connect() as c:
        return list(
            c.execute(
                text(
                    "SELECT step_id FROM workflow_steps WHERE workflow_id = :w AND version = :v "
                    "ORDER BY seq"
                ),
                {"w": wid, "v": ver},
            ).scalars()
        )


def test_steps_follow_a_workflow_changed_without_a_version_bump(
    owner_db: Engine, migrated: Settings, tmp_path: Path
) -> None:
    d = yaml.safe_load(SOURCE.read_text(encoding="utf-8"))
    d["id"] = "nobump-test"
    skills = {str(s["skill"]).split("@")[0] for s in d["steps"] if "skill" in s}
    with owner_db.begin() as conn:
        for sk in skills:
            conn.execute(
                text(
                    "INSERT INTO skills (id, agent_role, title, summary, phase) "
                    "VALUES (:i, 'developer', :i, 'test', 'build') ON CONFLICT DO NOTHING"
                ),
                {"i": sk},
            )
    _write(tmp_path, d)
    with owner_db.begin() as conn:
        _workflows(conn, tmp_path, migrated, skills, SyncResult("t"))
    assert "tplan" in _steps(owner_db, "nobump-test", d["version"])

    # Same version, one step removed: the stored steps follow the file.
    d["steps"] = [s for s in d["steps"] if s.get("id") != "tplan"]
    for s in d["steps"]:
        if s.get("pr"):
            s["after"] = [a for a in s["after"] if a != "tplan"]
    _write(tmp_path, d)
    with owner_db.begin() as conn:
        _workflows(conn, tmp_path, migrated, skills, SyncResult("t"))
    steps = _steps(owner_db, "nobump-test", d["version"])
    assert "tplan" not in steps and steps[-1] == "pr"

    # Unchanged file: a second sync changes nothing.
    with owner_db.begin() as conn:
        _workflows(conn, tmp_path, migrated, skills, SyncResult("t"))
    assert _steps(owner_db, "nobump-test", d["version"]) == steps
