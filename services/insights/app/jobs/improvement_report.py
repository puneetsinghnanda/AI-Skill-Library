"""Weekly improvement report job (SDD-11 §4). Plain SQL and Python; no model calls.

Implements IS-1, IS-2, IS-5, IS-7, IS-8 and IS-10 from ``skill_window_stats``. IS-3, IS-4, IS-6
and IS-9 need event fields that no event carries yet (``escalate_reason``, ``gate_kind``,
``findings_dropped_count``; SDD-11 §4.2 "needs"), so they are reported as not computed.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import Connection, text

from app.config import Settings
from app.crypto import ulid
from app.db import tx
from app.jobs import refresh_views
from app.timeutil import iso_date, utcnow

NOT_COMPUTED = ["IS-3", "IS-4", "IS-6", "IS-9"]


@dataclass(frozen=True)
class Rule:
    op: str
    threshold: float
    min_sample: int

    def over(self, v: float) -> bool:
        return v < self.threshold if self.op == "lt" else v > self.threshold


def load_rules(path: Path) -> dict[str, Rule]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {
        k: Rule(str(v["op"]), float(v["threshold"]), int(v["min_sample"]))
        for k, v in (raw.get("signals") or {}).items()
    }


def _signals(st: Any, prev: Any | None) -> dict[str, tuple[float | None, int]]:
    def r(n: Any, d: Any) -> float | None:
        return float(n) / float(d) if d else None

    out = {
        "IS-1": (r(st.first_try_pass, st.first_attempts), int(st.first_attempts)),
        "IS-2": (r(st.retries, st.steps), int(st.steps)),
        "IS-5": (
            None if st.s1_mean is None else 1.0 - float(st.s1_mean),
            int(st.pass_path_attempts),
        ),
        "IS-7": (r(st.overrides, st.steps), int(st.steps)),
        "IS-8": (r(st.input_steps, st.steps), int(st.steps)),
    }
    if prev is not None and prev.first_attempts and st.first_attempts:
        cur = float(st.first_try_pass) / float(st.first_attempts)
        old = float(prev.first_try_pass) / float(prev.first_attempts)
        out["IS-10"] = (cur - old, min(int(st.first_attempts), int(prev.first_attempts)))
    return out


def _clusters(conn: Connection, skill: str, version: str, s: Settings) -> list[dict[str, Any]]:
    rows = conn.execute(
        text(
            "SELECT s.run_id, s.step_id, s.attempt, s.seq, s.outcome, s.gate_failures, "
            "s.reasons, "
            "s.findings_blocker, "
            "s.findings_major, s.findings_minor, s.signals, r.workflow_id, sy.code AS system "
            "FROM "
            "steps s "
            "JOIN runs r ON r.id = s.run_id LEFT JOIN systems sy ON sy.id = r.system_id WHERE "
            "s.skill_id = :k "
            "AND s.skill_version = :v AND s.decided_at >= now() - interval '28 days' "
            "AND s.outcome NOT IN ('PASS','PASS-WITH-FINDINGS')"
        ),
        {"k": skill, "v": version},
    ).all()
    groups: dict[str, list[Any]] = {}
    for x in rows:
        sig = x.signals or {}
        failing = [c for c in (x.reasons or []) if c.startswith("S")]
        if isinstance(sig.get("S1"), (int, float)) and sig["S1"] < 0.75 and "S1" not in failing:
            failing.append("S1<0.75")
        sev = ",".join(
            f"{k}:{v}"
            for k, v in (
                ("blocker", x.findings_blocker),
                ("major", x.findings_major),
                ("minor", x.findings_minor),
            )
            if v
        )
        key = "|".join(
            [
                x.outcome,
                ",".join(sorted(x.gate_failures or [])) or "-",
                ",".join(sorted(failing)) or "-",
                sev or "-",
                "-",
            ]
        )
        groups.setdefault(key, []).append(x)
    total = len(rows)
    out = []
    for key, items in sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0]))[:5]:
        out.append(
            {
                "signature": key,
                "count": len(items),
                "share": round(len(items) / total, 4) if total else None,
                "workflows": sorted({i.workflow_id for i in items if i.workflow_id}),
                "positions": sorted({i.seq for i in items if i.seq is not None}),
                "references": [
                    {
                        "system": i.system,
                        "run_id": i.run_id,
                        "step": i.step_id,
                        "attempt": i.attempt,
                    }
                    for i in items[:10]
                ],
            }
        )
    return out


def run(s: Settings, refresh: bool = True) -> dict[str, int]:
    if refresh:
        refresh_views.run(s, ["skill_window_stats"])
    rules = load_rules(s.improvement_thresholds_file)
    today = utcnow().date()
    opened = closed = reports = 0
    with tx("app", s) as conn:
        stats = conn.execute(text("SELECT * FROM skill_window_stats")).all()
        by_skill: dict[str, list[Any]] = {}
        for st in stats:
            by_skill.setdefault(st.skill_id, []).append(st)
        for skill, versions in by_skill.items():
            versions.sort(key=lambda v: [int(x) for x in v.skill_version.split(".")])
            for i, st in enumerate(versions):
                prev = versions[i - 1] if i > 0 else None
                values = _signals(st, prev)
                flags_out = []
                for sig, rule in rules.items():
                    v, n = values.get(sig, (None, 0))
                    live = conn.execute(
                        text(
                            "SELECT id, status FROM skill_flags WHERE skill_id = :k AND "
                            "skill_version = :v AND signal = :s "
                            "AND status NOT IN ('VERIFIED','DISMISSED')"
                        ),
                        {"k": skill, "v": st.skill_version, "s": sig},
                    ).first()
                    enough = v is not None and n >= rule.min_sample
                    if enough and v is not None and rule.over(float(v)):
                        if live is None:
                            conn.execute(
                                text(
                                    "INSERT INTO skill_flags (id, skill_id, skill_version, "
                                    "signal, "
                                    "value, threshold, sample, "
                                    "status, opened_at, updated_at) VALUES (:id, :k, :v, :s, "
                                    ":val, "
                                    ":t, :n, 'OPEN', now(), now())"
                                ),
                                {
                                    "id": ulid("flg"),
                                    "k": skill,
                                    "v": st.skill_version,
                                    "s": sig,
                                    "val": round(float(v), 4),
                                    "t": rule.threshold,
                                    "n": n,
                                },
                            )
                            opened += 1
                        else:
                            conn.execute(
                                text(
                                    "UPDATE skill_flags SET value = :val, sample = :n, "
                                    "updated_at = "
                                    ""
                                    "now() "
                                    "WHERE id = :id"
                                ),
                                {"val": round(float(v), 4), "n": n, "id": live.id},
                            )
                    elif enough and live is not None and live.status == "OPEN":
                        conn.execute(
                            text("DELETE FROM skill_flags WHERE id = :id"), {"id": live.id}
                        )
                        closed += 1
                    flags_out.append(
                        {
                            "signal": sig,
                            "value": None if v is None else round(float(v), 4),
                            "threshold": rule.threshold,
                            "sample": n,
                            "enough_data": enough,
                        }
                    )
                # RELEASED -> VERIFIED / REOPENED on the newer version (SDD-11 §9)
                if prev is not None:
                    for f in conn.execute(
                        text(
                            "SELECT id, signal FROM skill_flags WHERE skill_id = :k "
                            "AND skill_version = :v AND status = 'RELEASED'"
                        ),
                        {"k": skill, "v": prev.skill_version},
                    ).all():
                        frule = rules.get(f.signal)
                        v, n = values.get(f.signal, (None, 0))
                        if frule and v is not None and n >= frule.min_sample:
                            new = "REOPENED" if frule.over(float(v)) else "VERIFIED"
                            conn.execute(
                                text(
                                    "UPDATE skill_flags SET status = :s, updated_at = now() "
                                    "WHERE "
                                    "id = :id"
                                ),
                                {"s": new, "id": f.id},
                            )
                meta = conn.execute(
                    text(
                        "SELECT k.owner_pseudonym, v.eval_pass_rate FROM skills k JOIN "
                        "skill_versions v ON v.skill_id = k.id "
                        "AND v.version = :v WHERE k.id = :k"
                    ),
                    {"k": skill, "v": st.skill_version},
                ).first()
                imps = conn.execute(
                    text(
                        "SELECT id, from_version, to_version, state, before_pass_rate, "
                        "after_pass_rate FROM improvements "
                        "WHERE skill_id = :k ORDER BY created_at DESC LIMIT 20"
                    ),
                    {"k": skill},
                ).all()
                body = {
                    "header": {
                        "skill_id": skill,
                        "version": st.skill_version,
                        "owner_pseudonym": meta.owner_pseudonym if meta else None,
                        "window_end": iso_date(today),
                        "window_days": int(st.window_days),
                        "samples": {
                            "steps": int(st.steps),
                            "first_attempts": int(st.first_attempts),
                        },
                        "eval_pass_rate": float(meta.eval_pass_rate)
                        if meta and meta.eval_pass_rate is not None
                        else None,
                    },
                    "signals": flags_out,
                    "not_computed": NOT_COMPUTED,
                    "clusters": _clusters(conn, skill, st.skill_version, s),
                    "version_comparison": {
                        "current": {k: values[k][0] for k in ("IS-1", "IS-2", "IS-7")},
                        "previous": None
                        if prev is None
                        else {
                            k: v
                            for k, (v, _n) in _signals(prev, None).items()
                            if k in ("IS-1", "IS-2", "IS-7")
                        },
                    },
                    "improvements": [
                        {
                            "improvement_id": x.id,
                            "from_version": x.from_version,
                            "to_version": x.to_version,
                            "state": x.state,
                            "before_pass_rate": None
                            if x.before_pass_rate is None
                            else float(x.before_pass_rate),
                            "after_pass_rate": None
                            if x.after_pass_rate is None
                            else float(x.after_pass_rate),
                        }
                        for x in imps
                    ],
                }
                conn.execute(
                    text(
                        "INSERT INTO improvement_reports (skill_id, skill_version, window_end, "
                        "body) VALUES (:k, :v, :w, "
                        "CAST(:b AS jsonb)) ON CONFLICT (skill_id, skill_version, window_end) DO "
                        ""
                        "UPDATE SET body = EXCLUDED.body"
                    ),
                    {"k": skill, "v": st.skill_version, "w": today, "b": json.dumps(body)},
                )
                reports += 1
    return {"opened": opened, "closed": closed, "reports": reports}


def due(s: Settings) -> bool:
    with tx("app", s) as conn:
        last = conn.execute(text("SELECT max(window_end) FROM improvement_reports")).scalar()
    return last is None or utcnow().date() - last >= timedelta(days=7)
