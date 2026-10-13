"""Catalogue sync: a marketplace release tree -> catalogue tables (SDD-08 §6.4, SDD-10 §8.2).

The source is a checked-out release tree (``CATALOGUE_SOURCE_DIR`` or ``python -m app.admin
catalogue sync --path``). Each file is validated against its schema; a bad file skips that item
(``insights_catalogue_items_skipped_total``, alert AL-19) and the rest still sync, in one
transaction. Old versions are kept; existing pod versions are never edited.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import Connection, text

from app.config import Settings
from app.db import tx
from app.ingest.schemas import first_error, load
from app.obs import metrics
from app.timeutil import utcnow

log = logging.getLogger("insights.catalogue")
MAX_ONE_PAGER = 20 * 1024


@dataclass
class SyncResult:
    tag: str
    skills: int = 0
    workflows: int = 0
    pods: int = 0
    skipped: list[str] = field(default_factory=list)


def _split(ref: str) -> tuple[str, str]:
    name, _, rng = ref.partition("@")
    return name.strip(), rng.strip() or "*"


def _changelog(path: Path, version: str) -> str | None:
    if not path.exists():
        return None
    m = re.search(
        rf"^##\s+{re.escape(version)}\s*$(.*?)(?=^##\s|\Z)",
        path.read_text(encoding="utf-8"),
        re.M | re.S,
    )
    if not m:
        return None
    txt = " ".join(
        line.strip().lstrip("- ") for line in m.group(1).strip().splitlines() if line.strip()
    )
    return txt[:500] or None


def _version_of(path: Path, pattern: str) -> str:
    if path.exists():
        m = re.search(pattern, path.read_text(encoding="utf-8"))
        if m:
            return m.group(1)
    return "0.0.0"


def _skip(res: SyncResult, kind: str, item: str, why: str) -> None:
    metrics.CATALOGUE_SKIPPED.labels(kind=kind).inc()
    res.skipped.append(f"{kind}:{item}")
    log.warning("catalogue item skipped", extra={"code": f"{kind}:{item}: {why}"[:180]})


def _skills(conn: Connection, root: Path, s: Settings, tag: str, res: SyncResult) -> set[str]:
    v = load(s.schemas_dir).file_validator("skill-metadata.v1")
    known: set[str] = set()
    for f in sorted((root / "plugins" / "truminds" / "skills").glob("*/skill.yaml")):
        try:
            d = yaml.safe_load(f.read_text(encoding="utf-8"))
        except yaml.YAMLError:
            _skip(res, "skill", f.parent.name, "yaml")
            continue
        err = first_error(v, d)
        if err:
            _skip(res, "skill", f.parent.name, err)
            continue
        sid, ver = str(d["id"]), str(d["version"])
        conn.execute(
            text(
                "INSERT INTO skills (id, agent_role, title, summary, phase, domains, "
                "owner_pseudonym, current_version) "
                "VALUES (:id, :ar, :t, :s, :ph, :dom, :own, :v) ON CONFLICT (id) DO UPDATE SET "
                "agent_role = EXCLUDED.agent_role, "
                "title = EXCLUDED.title, summary = EXCLUDED.summary, phase = EXCLUDED.phase, "
                "domains = EXCLUDED.domains, "
                "owner_pseudonym = EXCLUDED.owner_pseudonym, current_version = "
                "EXCLUDED.current_version"
            ),
            {
                "id": sid,
                "ar": d["agent"],
                "t": d.get("title") or sid,
                "s": d.get("summary") or "",
                "ph": d.get("phase"),
                "dom": list(d.get("domains") or []),
                "own": d.get("owner"),
                "v": ver,
            },
        )
        conn.execute(
            text(
                "INSERT INTO skill_versions (skill_id, version, status, inputs, outputs, "
                "context_sections, size_budget_tokens, "
                "allowed_tools, portal, changelog, release_tag, published_at) VALUES (:id, :v, "
                ":st, "
                ""
                "CAST(:i AS jsonb), "
                "CAST(:o AS jsonb), CAST(:c AS jsonb), :sb, :tools, CAST(:p AS jsonb), :cl, "
                ":tag, "
                "now()) "
                "ON CONFLICT (skill_id, version) DO UPDATE SET status = EXCLUDED.status, "
                "release_tag = EXCLUDED.release_tag"
            ),
            {
                "id": sid,
                "v": ver,
                "st": d["status"],
                "i": json.dumps(d.get("inputs") or []),
                "o": json.dumps(d.get("outputs") or []),
                "c": json.dumps(d.get("context_sections") or []),
                "sb": d.get("size_budget_tokens"),
                "tools": list(d.get("allowed_tools") or []),
                "p": json.dumps(d.get("portal") or {}),
                "cl": _changelog(f.parent / "CHANGELOG.md", ver),
                "tag": tag,
            },
        )
        known.add(sid)
        res.skills += 1
    return known | set(conn.execute(text("SELECT id FROM skills")).scalars())


# RD-6 (registry §11): the two competing workflow-name sets. Catalogue sync skips a workflow
# whose id is in the set that was NOT chosen; ids in neither set (new workflows) are accepted.
WORKFLOW_NAMES: dict[str, frozenset[str]] = {
    "doc3": frozenset(
        {"brownfield-change", "greenfield-feature", "defect-fix", "ux-review", "estimate"}
    ),
    "doc1": frozenset(
        {
            "brownfield-feature",
            "defect-triage",
            "greenfield-architecture",
            "greenfield-bootstrap",
        }
    ),
}


def non_canonical_workflow(wid: str, choice: str) -> bool:
    return any(wid in names for key, names in WORKFLOW_NAMES.items() if key != choice)


def _workflows(
    conn: Connection, root: Path, s: Settings, skills: set[str], res: SyncResult
) -> None:
    v = load(s.schemas_dir).file_validator("workflow.v1")
    for f in sorted((root / "plugins" / "truminds" / "workflows").glob("*.yaml")):
        try:
            d = yaml.safe_load(f.read_text(encoding="utf-8"))
        except yaml.YAMLError:
            _skip(res, "workflow", f.name, "yaml")
            continue
        err = first_error(v, d)
        if err:
            _skip(res, "workflow", f.name, err)
            continue
        if non_canonical_workflow(str(d["id"]), s.rd6_workflow_names):
            _skip(res, "workflow", f.name, f"non-canonical name under RD-6={s.rd6_workflow_names}")
            continue
        steps: list[tuple[int, str, str, str | None, str | None, str | None]] = []
        for i, st in enumerate(d.get("steps") or [], start=1):
            if "gate" in st:
                steps.append((i, str(st["gate"]), "gate", None, None, st.get("role")))
            elif st.get("pr"):
                steps.append((i, "pr", "pr", None, None, None))
            else:
                sk, rng = _split(str(st["skill"]))
                steps.append((i, str(st["id"]), "skill", sk, rng, None))
        if any(x[3] and x[3] not in skills for x in steps):
            _skip(res, "workflow", f.name, "references an unknown skill")
            continue
        wid, ver = str(d["id"]), str(d["version"])
        conn.execute(
            text(
                "INSERT INTO workflows (id, title, current_version) VALUES (:i, :t, :v) "
                "ON CONFLICT (id) DO UPDATE SET title = EXCLUDED.title, current_version = "
                "EXCLUDED.current_version"
            ),
            {"i": wid, "t": d.get("title") or wid, "v": ver},
        )
        new = conn.execute(
            text(
                "INSERT INTO workflow_versions (workflow_id, version, definition, step_count, "
                "published_at) "
                "VALUES (:i, :v, CAST(:d AS jsonb), :n, now()) ON CONFLICT DO NOTHING RETURNING "
                "version"
            ),
            {"i": wid, "v": ver, "d": json.dumps(d, default=str), "n": len(steps)},
        ).scalar()
        if new:
            for w_seq, w_step, w_kind, w_skill, w_rng, w_role in steps:
                conn.execute(
                    text(
                        "INSERT INTO workflow_steps (workflow_id, version, seq, step_id, kind, "
                        "skill_id, skill_range, gate_role) "
                        "VALUES (:w, :v, :q, :s, :k, :sk, :r, :g)"
                    ),
                    {
                        "w": wid,
                        "v": ver,
                        "q": w_seq,
                        "s": w_step,
                        "k": w_kind,
                        "sk": w_skill,
                        "r": w_rng,
                        "g": w_role,
                    },
                )
        res.workflows += 1


def _pods(
    conn: Connection, root: Path, s: Settings, skills: set[str], commit: str, res: SyncResult
) -> None:
    v = load(s.schemas_dir).file_validator("pod.v1")
    for f in sorted((root / "pods").glob("*/pod.yaml")):
        try:
            d = yaml.safe_load(f.read_text(encoding="utf-8"))
        except yaml.YAMLError:
            _skip(res, "pod", f.parent.name, "yaml")
            continue
        err = first_error(v, d)
        if err:
            _skip(res, "pod", f.parent.name, err)
            continue
        one = f.parent / str(d.get("one_pager") or "one-pager.md")
        md = one.read_text(encoding="utf-8") if one.exists() else ""
        if len(md.encode()) > MAX_ONE_PAGER:
            _skip(res, "pod", f.parent.name, "one-pager.md over 20 KB")
            continue
        agent_skills = [
            (a["key"], _split(str(x))) for a in d.get("agents") or [] for x in a.get("skills") or []
        ]
        if any(sk not in skills for _k, (sk, _r) in agent_skills):
            _skip(res, "pod", f.parent.name, "references an unknown skill")
            continue
        pid, ver = str(d["id"]), str(d["version"])
        conn.execute(
            text(
                "INSERT INTO pods (id, title, kind, status, owner_pseudonym, current_version) "
                "VALUES (:i, :t, :k, :s, :o, :v) "
                "ON CONFLICT (id) DO UPDATE SET title = EXCLUDED.title, kind = EXCLUDED.kind, "
                "status = EXCLUDED.status, "
                "owner_pseudonym = EXCLUDED.owner_pseudonym, current_version = "
                "EXCLUDED.current_version"
            ),
            {
                "i": pid,
                "t": d["title"],
                "k": d["kind"],
                "s": d["status"],
                "o": d.get("owner"),
                "v": ver,
            },
        )
        new = conn.execute(
            text(
                "INSERT INTO pod_versions (pod_id, version, status, definition, source_sha, "
                "published_at) "
                "VALUES (:i, :v, :s, CAST(:d AS jsonb), :sha, now()) ON CONFLICT DO NOTHING "
                "RETURNING version"
            ),
            {
                "i": pid,
                "v": ver,
                "s": d["status"],
                "d": json.dumps({**d, "one_pager_md": md}, default=str),
                "sha": commit,
            },
        ).scalar()
        if new:
            for a in d.get("agents") or []:
                conn.execute(
                    text(
                        "INSERT INTO pod_agents (pod_id, version, agent_key, role, display_name, "
                        ""
                        "engineers) "
                        "VALUES (:p, :v, :k, :r, :n, :e)"
                    ),
                    {
                        "p": pid,
                        "v": ver,
                        "k": a["key"],
                        "r": a["role"],
                        "n": a["display_name"],
                        "e": a.get("engineers", 1),
                    },
                )
                cross = {
                    str(c.get("skill"))
                    for c in a.get("cross_role_skills") or []
                    if isinstance(c, dict)
                }
                for ref in a.get("skills") or []:
                    sk, rng = _split(str(ref))
                    conn.execute(
                        text(
                            "INSERT INTO pod_agent_skills (pod_id, version, agent_key, skill_id, "
                            ""
                            "skill_range, cross_role) "
                            "VALUES (:p, :v, :k, :s, :r, :c) ON CONFLICT DO NOTHING"
                        ),
                        {"p": pid, "v": ver, "k": a["key"], "s": sk, "r": rng, "c": sk in cross},
                    )
            for ref in d.get("workflows") or []:
                wid, rng = _split(str(ref))
                conn.execute(
                    text(
                        "INSERT INTO pod_workflows (pod_id, version, workflow_id, "
                        "workflow_range) "
                        "VALUES (:p, :v, :w, :r) ON CONFLICT DO NOTHING"
                    ),
                    {"p": pid, "v": ver, "w": wid, "r": rng},
                )
        res.pods += 1


def sync(
    s: Settings,
    root: Path,
    tag: str,
    commit_sha: str,
    released_at: datetime | None = None,
    notes: list[dict[str, Any]] | None = None,
) -> SyncResult:
    if not re.match(r"^v\d+\.\d+\.\d+$", tag):
        raise ValueError("tag must look like vX.Y.Z")
    res = SyncResult(tag)
    plugin_version = _version_of(
        root / "plugins" / "truminds" / ".claude-plugin" / "plugin.json",
        r'"version"\s*:\s*"([^"]+)"',
    )
    tsl_version = _version_of(
        root / "tsl" / "src" / "tsl" / "__init__.py", r'__version__\s*=\s*"([^"]+)"'
    )
    with tx("app", s) as conn:
        conn.execute(
            text(
                "INSERT INTO catalogue_releases (tag, plugin_version, tsl_version, commit_sha, "
                "released_at, synced_at, notes) "
                "VALUES (:t, :p, :ts, :c, :r, now(), CAST(:n AS jsonb)) ON CONFLICT (tag) DO "
                "UPDATE "
                ""
                "SET synced_at = now(), "
                "notes = EXCLUDED.notes"
            ),
            {
                "t": tag,
                "p": plugin_version,
                "ts": tsl_version,
                "c": commit_sha,
                "r": released_at or utcnow(),
                "n": json.dumps(notes or []),
            },
        )
        skills = _skills(conn, root, s, tag, res)
        _workflows(conn, root, s, skills, res)
        _pods(conn, root, s, skills, commit_sha, res)
    metrics.CATALOGUE_LAST_SYNC.set(utcnow().timestamp())
    metrics.CATALOGUE_UNSYNCED.set(0)
    return res
