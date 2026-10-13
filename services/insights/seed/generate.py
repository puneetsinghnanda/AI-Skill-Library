"""Development seed data (SDD-08 §11.3): invented, domain-agnostic, fixed random seed.

Client CL-DEMO, project PRJ-DEMO, systems SYS-ORD (order tracking) and SYS-TKT (ticket desk),
6 pseudonymous users, the catalogue from a local release tree and about 200 runs sent through the
normal ingest path, then projected and the views refreshed. Refuses to run when ENV=prod.

    python seed/generate.py --catalogue ../..      # from services/insights
"""

from __future__ import annotations

import argparse
import random
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import text

from app.auth.entra import EntraClaims
from app.auth.users import resolve_user
from app.catalogue.sync import sync
from app.config import get_settings
from app.crypto import encrypt, ulid
from app.db import tx
from app.ingest.schemas import load
from app.ingest.service import ingest
from app.jobs import partitions, refresh_views
from app.projector.loop import project_all

RNG = random.Random(20260101)
TENANT = "00000000-0000-4000-8000-00000000dead"
USERS = ["Ash", "Bay", "Cedar", "Dune", "Elm", "Fern"]
SYSTEMS = [("SYS-ORD", "orders-api", "digital"), ("SYS-TKT", "tickets-web", "digital")]
OUTCOMES = ["PASS", "PASS", "PASS", "PASS-WITH-FINDINGS", "RETRY", "NEEDS-INPUT", "ESCALATE"]


def _ts(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _ev(type_: str, body: dict[str, Any], run_id: str | None, at: datetime) -> dict[str, Any]:
    e: dict[str, Any] = {
        "event_id": ulid("evt"),
        "type": type_,
        "schema_version": 1,
        "occurred_at": _ts(at),
        "body": body,
    }
    if run_id:
        e["run_id"] = run_id
    return e


def main(argv: list[str] | None = None, settings: Any = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--catalogue", type=Path, required=True, help="skill-library release tree (repo root)"
    )
    ap.add_argument("--runs", type=int, default=200)
    a = ap.parse_args(argv)
    s = settings or get_settings()
    if s.env == "prod":
        print("refusing to seed a production database (ENV=prod)", file=sys.stderr)
        return 2
    partitions.run(s)
    sync(s, a.catalogue, "v0.1.0", "0" * 40)
    with tx("app", s) as conn:
        enc, _k = encrypt(s, "Demo Client")
        conn.execute(
            text(
                "INSERT INTO clients (code, display_name_enc, consent_ref, consent_recorded_at, "
                "consent_scope) "
                "VALUES ('CL-DEMO', :n, 'CONSENT-DEMO', now(), :sc) ON CONFLICT DO NOTHING"
            ),
            {"n": enc, "sc": ["code_processing", "companion_storage", "product_prs", "ci_webhook"]},
        )
        conn.execute(
            text(
                "INSERT INTO projects (client_id, code) SELECT id, 'PRJ-DEMO' FROM clients "
                "WHERE code = 'CL-DEMO' ON CONFLICT DO NOTHING"
            )
        )
        for code, repo, domain in SYSTEMS:
            conn.execute(
                text(
                    "INSERT INTO systems (project_id, code, domain, companion_repo) SELECT id, :c, "
                    ":d, :r "
                    "FROM projects WHERE code = 'PRJ-DEMO' ON CONFLICT DO NOTHING"
                ),
                {"c": code, "d": domain, "r": f"example-org/cl-demo-{code.lower()}-companion"},
            )
            conn.execute(
                text(
                    "INSERT INTO system_repos (system_id, name, github_full_name, kind) SELECT id, "
                    ":n, :g, "
                    "'product' FROM systems WHERE code = :c ON CONFLICT DO NOTHING"
                ),
                {"n": repo, "g": f"example-org/{repo}", "c": code},
            )
        users: list[tuple[Any, str]] = []
        for i, name in enumerate(USERS):
            oid = str(uuid.UUID(int=i + 1))
            u = resolve_user(
                conn,
                s,
                EntraClaims(
                    oid,
                    TENANT,
                    "tsl",
                    frozenset({"Events.Write"}),
                    frozenset({"Engineer"}),
                    f"{name} Example",
                    None,
                ),
            )
            for code, _r, _d in SYSTEMS[: 1 + i % 2]:
                conn.execute(
                    text(
                        "INSERT INTO role_grants (user_id, role, scope_type, scope_id, granted_at) "
                        "SELECT CAST(:u AS uuid), 'engineer', 'system', id::text, now() FROM "
                        "systems "
                        "WHERE code = :c ON CONFLICT DO NOTHING"
                    ),
                    {"u": u.id, "c": code},
                )
            kid = ulid("key")
            conn.execute(
                text(
                    "INSERT INTO keys (key_id, user_id, device_id, public_key, expires_at) VALUES "
                    "(:k, CAST(:u AS uuid), :d, :p, now() + interval '180 days') ON CONFLICT DO "
                    "NOTHING"
                ),
                {"k": kid, "u": u.id, "d": ulid("dev"), "p": bytes(32)},
            )
            users.append((u, kid))
    schemas = load(s.schemas_dir)
    now = datetime.now(UTC)
    by_user: dict[str, list[dict[str, Any]]] = {}
    for i in range(a.runs):
        user, kid = users[i % len(users)]
        code, repo, _d = SYSTEMS[i % 2]
        run_id = ulid("run")
        t0 = now - timedelta(days=RNG.randint(0, 120), minutes=RNG.randint(0, 600))
        evs = [
            _ev(
                "run.started",
                {
                    "workflow": "brownfield-change",
                    "workflow_version": "1.3.0",
                    "ticket_ref": f"DEMO-{i + 1}",
                    "system": code,
                    "plugin_version": "0.1.0",
                    "pinned_skills": {"design": "1.4.0"},
                    "pod": "brownfield-change-pod",
                },
                run_id,
                t0,
            )
        ]
        for seq, (step, skill, ver) in enumerate(
            [
                ("impact", "impact-analysis", None),
                ("design", "design", "1.4.0"),
                ("threat", "threat-model", None),
            ],
            start=3,
        ):
            ver = ver or _version(s, skill)
            outcome = RNG.choice(OUTCOMES)
            evs.append(
                _ev(
                    "step.decided",
                    {
                        "step": step,
                        "skill": skill,
                        "skill_version": ver,
                        "attempt": 1,
                        "outcome": outcome,
                        "band": RNG.choice(["High", "Medium", "Low"]),
                        "signals": {
                            "S1": round(RNG.uniform(0.6, 1), 2),
                            "S2": 1.0,
                            "S3": 4.0,
                            "S4": 0,
                            "S5": "fresh",
                            "S6": {"lines": 20, "files": 2, "sensitive": False},
                        },
                        "caps": [],
                        "gate_failures": [],
                        "findings_count": {"blocker": 0, "major": 0, "minor": 1},
                        "duration_ms": 30000,
                        "verification_sha256": f"{RNG.getrandbits(256):064x}",
                        "seq": seq,
                        "reasons": [] if outcome.startswith("PASS") else ["S1"],
                        "key_id": kid,
                        "decided_by": "tsl@0.1.0",
                    },
                    run_id,
                    t0 + timedelta(minutes=seq),
                )
            )
        if RNG.random() < 0.6:
            evs.append(
                _ev(
                    "pr.opened",
                    {"repo": repo, "number": 1000 + i, "draft": False, "lowest_band": "High"},
                    run_id,
                    t0 + timedelta(minutes=20),
                )
            )
            evs.append(
                _ev(
                    "run.status_changed",
                    {"from": "RUNNING", "to": "COMPLETED", "reason_code": "pr_opened"},
                    run_id,
                    t0 + timedelta(minutes=21),
                )
            )
        by_user.setdefault(user.id, []).extend(evs)
    for uid, evs in by_user.items():
        for k in range(0, len(evs), 500):
            with tx("app", s) as conn:
                ingest(conn, s, schemas, evs[k : k + 500], "tsl", uid)
    project_all(s)
    with tx("app", s) as conn:
        conn.execute(
            text(
                "UPDATE pull_requests SET state = 'merged', merged_at = opened_at + interval '1 "
                "day' "
                "WHERE number % 3 <> 0"
            )
        )
    refresh_views.run(s)
    print(f"seeded {a.runs} runs for {len(users)} users")
    return 0


def _version(s: Any, skill: str) -> str:
    with tx("app", s) as conn:
        return str(
            conn.execute(
                text("SELECT current_version FROM skills WHERE id = :k"), {"k": skill}
            ).scalar()
        )


if __name__ == "__main__":
    raise SystemExit(main())
