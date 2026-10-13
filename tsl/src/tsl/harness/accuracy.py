"""tsl harness eval [--code-only]: harness accuracy on the labelled set (SDD-03 §16).

Each case folder holds `case.yaml` (harness-case.v1), `artifact.md`, an optional canned
`review.json` and optional `inputs/`. Everything is scored by code. Reviewer cases need a
reviewer output; with --code-only they are skipped (they run on a seat, SDD-03 §16.2).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tsl.core.config import effective_bands
from tsl.core.errors import TslError
from tsl.core.jsonio import read_json, read_yaml
from tsl.core.runtime import Runtime
from tsl.harness import artifact as artmod
from tsl.harness import citations
from tsl.harness.decide import DecideInput, evaluate
from tsl.harness.gates import CheckInput, run_all
from tsl.orchestrator.skills import Skill, installed

GATES = ("H1", "H2", "H3", "H4", "H5", "H6", "H7")
SEV = {"minor": 0, "major": 1, "blocker": 2}
# SDD-03 §16.4: proposed targets, pending the owner's decision (OQ-09, OQ-11).
TARGETS = {
    "gate_recall_min": 1.0,
    "gate_precision_min": 0.98,
    "citation_false_drop_max": 0.02,
    "fabrication_catch_min": 1.0,
    "decide_accuracy_min": 1.0,
    "reviewer_recall_min": 0.70,
    "reviewer_precision_min": 0.80,
}


def default_dir(rt: Runtime) -> Path:
    return rt.plugin_root().resolve().parents[1] / "harness-evals" / "cases"


def _ratio(n: int, d: int) -> float | None:
    return round(n / d, 4) if d else None


def _skill(skills: dict[str, Skill], ref: str) -> tuple[Skill | None, str | None]:
    sid, _, ver = ref.partition("@")
    sk = skills.get(sid)
    if sk is None:
        return None, f"skill {sid} not installed"
    return sk, None if sk.version == ver else f"labelled for {ref}, scored with {sk.ref}"


def _lines(ref: str) -> tuple[str, int, int] | None:
    path, _, anchor = ref.partition("#")
    if not anchor.startswith("L"):
        return None
    a, _, b = anchor[1:].partition("-L")
    try:
        lo = int(a)
        hi = int(b) if b else lo
    except ValueError:
        return None
    return path, lo, hi


def _matches(f: dict[str, Any], d: dict[str, Any]) -> bool:
    """SDD-03 §16.2 match rule: same path, overlapping span, severity within one level."""
    if abs(SEV.get(str(f.get("severity")), 0) - SEV.get(str(d["severity"]), 0)) > 1:
        return False
    lo, hi = int(d["lines"][0]), int(d["lines"][1])
    for c in f.get("cites", []):
        ref = c.get("ref") if isinstance(c, dict) else str(c)
        sp = _lines(str(ref))
        if sp and sp[0] == d["path"] and sp[1] <= hi and sp[2] >= lo:
            return True
    return False


def score_case(
    case_dir: Path, case: dict[str, Any], sk: Skill | None, code_only: bool
) -> dict[str, Any]:
    art = artmod.load(case_dir, "artifact.md")
    inputs = sorted((case_dir / "inputs").rglob("*")) if (case_dir / "inputs").is_dir() else []
    expected_inputs = [
        {"name": p.stem, "path": p.relative_to(case_dir).as_posix(), "required": False}
        for p in inputs
        if p.is_file()
    ]
    ci = CheckInput(
        root=case_dir,
        art=art,
        skill=sk,
        repos=set(),
        clones={},
        expected_inputs=expected_inputs,
        standalone=True,
    )
    run = run_all(ci, None)
    gates = {k: g.status for k, g in run.gates.items()}
    review = read_json(case_dir / "review.json") if (case_dir / "review.json").is_file() else None
    checks = {
        "gates": [g.record() for g in run.gates.values()],
        "soft": run.soft,
        "product_changes": None,
    }
    d = evaluate(
        DecideInput(
            checks=checks,
            review=review,
            front=art.front,
            rubric=sk.rubric if sk else {"criteria": []},
            limits={"checks": 2, "review": 2, "verifier": 3},
            used={"checks": 0, "review": 0, "verifier": 0},
            thresholds=effective_bands(sk.harness.get("bands") if sk else None, None),
            s5="fresh",
            requires_fresh_pack=False,
            is_code=bool(sk and sk.is_code),
            change_limits={"lines": 400, "files": 15, "sensitive_paths": []},
            resolver=citations.Resolver(case_dir, {}, {}),
            repos=set(),
        )
    )
    exp = case["expect"]
    dropped_ids = {x["id"] for x in d.dropped}
    dropped_refs: set[str] = set()
    valid_total = valid_dropped = 0
    fabricated = set(exp.get("fabricated_cites") or [])
    for f in (review or {}).get("findings", []):
        refs = [str(c.get("ref") if isinstance(c, dict) else c) for c in f.get("cites", [])]
        if f.get("id") in dropped_ids:
            dropped_refs.update(refs)
        for r in refs:
            if r not in fabricated:
                valid_total += 1
                valid_dropped += int(f.get("id") in dropped_ids)
    resolver = citations.Resolver(case_dir, {}, {})
    caught = 0
    for ref in fabricated:
        c = citations.parse(ref, set())
        text = resolver.read(c)[0] if c else None
        if ref in dropped_refs or text is None or (c and citations.span_for(c, text)[0] is None):
            caught += 1
    reviewer: dict[str, Any] | None = None
    if case["kind"] == "reviewer" and not code_only and review is not None:
        planted = [p for p in exp.get("planted_defects", []) if p["severity"] != "minor"]
        hit = sum(1 for p in planted if any(_matches(f, p) for f in d.kept))
        good = sum(1 for f in d.kept if any(_matches(f, p) for p in exp.get("planted_defects", [])))
        reviewer = {"planted": len(planted), "matched": hit, "kept": len(d.kept), "good": good}
    outcome_ok = d.outcome == exp["outcome"] and ("band" not in exp or d.band == exp["band"])
    return {
        "id": case["id"],
        "kind": case["kind"],
        "gates": gates,
        "outcome": d.outcome,
        "band": d.band,
        "outcome_ok": outcome_ok,
        "fabricated": len(fabricated),
        "fabricated_caught": caught,
        "valid_cites": valid_total,
        "valid_dropped": valid_dropped,
        "reviewer": reviewer,
    }


def run(rt: Runtime, cases_dir: Path | None, code_only: bool) -> tuple[dict[str, Any], list[str]]:
    from tsl.schemas.registry import require_valid

    base = cases_dir or default_dir(rt)
    if not base.is_dir():
        raise TslError("E-ENV-01", item=f"labelled harness cases at {base}")
    skills = installed(rt.plugin_root())
    per: list[dict[str, Any]] = []
    skipped: list[str] = []
    notes: list[str] = []
    labels: dict[str, dict[str, Any]] = {}
    for meta in sorted(base.glob("*/case.yaml")):
        case = read_yaml(meta)
        require_valid("harness-case.v1", case, str(meta.relative_to(base)))
        if case["kind"] == "reviewer" and (
            code_only or not (meta.parent / "review.json").is_file()
        ):
            skipped.append(case["id"])
            continue
        sk, note = _skill(skills, str(case["skill"]))
        if note:
            notes.append(f"{case['id']}: {note}")
        per.append(score_case(meta.parent, case, sk, code_only))
        labels[case["id"]] = case
    tp = {g: 0 for g in GATES}
    fp = {g: 0 for g in GATES}
    fn = {g: 0 for g in GATES}
    unmeasured: list[str] = []
    for r in per:
        for g, want in (labels[r["id"]]["expect"].get("gates") or {}).items():
            got = r["gates"].get(g, "skip")
            if want == "skip":
                continue
            if got == "skip":
                unmeasured.append(f"{r['id']}:{g}")
                continue
            pos_want, pos_got = want == "fail", got == "fail"
            tp[g] += int(pos_want and pos_got)
            fp[g] += int(pos_got and not pos_want)
            fn[g] += int(pos_want and not pos_got)
    gates = {
        g: {
            "tp": tp[g],
            "fp": fp[g],
            "fn": fn[g],
            "precision": _ratio(tp[g], tp[g] + fp[g]),
            "recall": _ratio(tp[g], tp[g] + fn[g]),
        }
        for g in GATES
    }
    decide_cases = [r for r in per if r["kind"] == "decide"]
    reviewers = [r["reviewer"] for r in per if r["reviewer"]]
    measures = {
        "gates": gates,
        "decide_accuracy": _ratio(sum(r["outcome_ok"] for r in decide_cases), len(decide_cases)),
        "fabrication_catch_rate": _ratio(
            sum(r["fabricated_caught"] for r in per), sum(r["fabricated"] for r in per)
        ),
        "citation_false_drop_rate": _ratio(
            sum(r["valid_dropped"] for r in per), sum(r["valid_cites"] for r in per)
        ),
        "reviewer_recall": _ratio(
            sum(x["matched"] for x in reviewers), sum(x["planted"] for x in reviewers)
        ),
        "reviewer_precision": _ratio(
            sum(x["good"] for x in reviewers), sum(x["kept"] for x in reviewers)
        ),
    }
    misses: list[str] = []
    t = TARGETS
    for g, m in gates.items():
        if m["recall"] is not None and m["recall"] < t["gate_recall_min"]:
            misses.append(f"{g} recall {m['recall']}")
        if m["precision"] is not None and m["precision"] < t["gate_precision_min"]:
            misses.append(f"{g} precision {m['precision']}")
    checks = [
        ("decide_accuracy", "decide_accuracy_min", False),
        ("fabrication_catch_rate", "fabrication_catch_min", False),
        ("citation_false_drop_rate", "citation_false_drop_max", True),
        ("reviewer_recall", "reviewer_recall_min", False),
        ("reviewer_precision", "reviewer_precision_min", False),
    ]
    for key, target, is_max in checks:
        v = measures[key]
        if isinstance(v, float) and (v > t[target] if is_max else v < t[target]):
            misses.append(f"{key} {v}")
    data = {
        "cases_dir": str(base),
        "cases": len(per),
        "skipped": skipped,
        "unmeasured": unmeasured,
        "code_only": code_only,
        "measures": measures,
        "targets": dict(TARGETS),
        "misses": misses,
        "mismatches": [
            {"id": r["id"], "outcome": r["outcome"], "band": r["band"]}
            for r in per
            if not r["outcome_ok"]
        ],
        "notes": notes,
    }
    return data, misses
