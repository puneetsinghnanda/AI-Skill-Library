"""tsl eval plan | run | check (SDD-01 §10, SDD-04 §6.16, §6.21). Code-only scoring."""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any

from tsl.core.clock import iso
from tsl.core.config import effective_bands
from tsl.core.errors import TslError
from tsl.core.hashing import sha256_file, sha256_raw, sha256_text
from tsl.core.jsonio import read_json, read_yaml, write_json
from tsl.core.runtime import Runtime
from tsl.harness import artifact as artmod
from tsl.harness import citations
from tsl.harness.decide import DecideInput, evaluate
from tsl.harness.gates import CheckInput, run_all
from tsl.harness.jsonpath import select
from tsl.identity.keys import load_signer
from tsl.identity.signing import canonical, round4, sign_object
from tsl.orchestrator.skills import Skill, load_skill
from tsl.telemetry.emit import emit


def _skill(rt: Runtime, skill: str, version: str | None) -> Skill:
    d = rt.plugin_root() / "skills" / skill
    if not (d / "skill.yaml").is_file():
        raise TslError("E-USE-01", detail=f"unknown skill {skill}", cmd="eval")
    sk = load_skill(d)
    if version and version != sk.version:
        raise TslError(
            "E-USE-01", detail=f"{skill} {version} is not installed (have {sk.version})", cmd="eval"
        )
    return sk


def _cases(sk: Skill) -> tuple[dict[str, Any], list[tuple[Path, dict[str, Any]]]]:
    from tsl.schemas.registry import require_valid

    base = sk.dir / "evals"
    es = read_yaml(base / "eval-set.yaml") if (base / "eval-set.yaml").is_file() else None
    if es is None:
        raise TslError(
            "E-CFG-01", file=f"{sk.id}/evals/eval-set.yaml", pointer="/", reason="missing"
        )
    require_valid("eval-set.v1", es, "eval-set.yaml")
    out = []
    for d in sorted((base / "cases").glob("*/case.yaml")):
        c = read_yaml(d)
        require_valid("eval-case.v1", c, str(d.relative_to(sk.dir)))
        out.append((d.parent, c))
    return es, out


def plan(rt: Runtime, skill: str, version: str | None) -> dict[str, Any]:
    sk = _skill(rt, skill, version)
    es, cases = _cases(sk)
    if len(cases) < int(es["min_cases"]):
        raise TslError(
            "E-CFG-01",
            file=f"{sk.id}/evals",
            pointer="/cases",
            reason=f"{len(cases)} cases, minimum {es['min_cases']}",
        )
    work = rt.home.eval_dir(sk.id, sk.version)
    items = []
    for d, c in cases:
        cw = work / c["id"]
        inp = cw / "inputs"
        if inp.exists():
            shutil.rmtree(inp)
        if (d / "inputs").is_dir():
            shutil.copytree(d / "inputs", inp)
        else:
            inp.mkdir(parents=True, exist_ok=True)
        items.append(
            {
                "id": c["id"],
                "input_dir": str(inp),
                "expected_path": str(d / "case.yaml"),
                "output_path": str(cw / "output.md"),
                "review_path": str(cw / "review.json"),
            }
        )
    return {
        "skill": sk.id,
        "version": sk.version,
        "workdir": str(work),
        "cases": items,
        "min_cases": es["min_cases"],
        "min_pass_rate": es["min_pass_rate"],
    }


def _assert(front: dict[str, Any], a: dict[str, Any]) -> str | None:
    vals = select(front, a["path"])
    if "count_min" in a and len(vals) < int(a["count_min"]):
        return f"{a['path']}: {len(vals)} < {a['count_min']}"
    if "count_max" in a and len(vals) > int(a["count_max"]):
        return f"{a['path']}: {len(vals)} > {a['count_max']}"
    if "any_matches" in a and not any(re.search(a["any_matches"], str(v)) for v in vals):
        return f"{a['path']}: nothing matches {a['any_matches']}"
    if "none_matches" in a and any(re.search(a["none_matches"], str(v)) for v in vals):
        return f"{a['path']}: a value matches {a['none_matches']}"
    if "equals" in a and vals != (a["equals"] if isinstance(a["equals"], list) else [a["equals"]]):
        return f"{a['path']}: != {a['equals']}"
    return None


def score_case(rt: Runtime, sk: Skill, case_dir: Path, case: dict[str, Any]) -> dict[str, Any]:
    work = rt.home.eval_dir(sk.id, sk.version) / case["id"]
    out = work / "output.md"
    failed: list[str] = []
    if not out.is_file():
        return {"id": case["id"], "pass": False, "failed_checks": ["no output"], "outcome": None}
    art = artmod.load(work, "output.md")
    expected_inputs = [
        {
            "name": n,
            "path": p,
            "sha256": sha256_file(work / p) if (work / p).is_file() else None,
            "schema": None,
            "step": None,
            "required": True,
        }
        for n, p in case["inputs"].items()
    ]
    ci = CheckInput(
        root=work,
        art=art,
        skill=sk,
        repos=set(),
        clones={},
        expected_inputs=expected_inputs,
        standalone=True,
    )
    run = run_all(ci, None)
    gates = {k: g.status for k, g in run.gates.items()}
    for g, want in (case["expect"].get("gates") or {}).items():
        got = "fail" if gates.get(g) == "fail" else "pass"
        if got != want:
            failed.append(f"gate {g} {got} != {want}")
    review = read_json(work / "review.json") if (work / "review.json").is_file() else None
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
            rubric=sk.rubric,
            limits={"checks": 2, "review": 2, "verifier": 3},
            used={"checks": 0, "review": 0, "verifier": 0},
            thresholds=effective_bands(sk.harness.get("bands"), None),
            s5="fresh",
            requires_fresh_pack=False,
            is_code=sk.is_code,
            change_limits={"lines": 400, "files": 15, "sensitive_paths": []},
            resolver=citations.Resolver(work, {}, {}),
            repos=set(),
        )
    )
    if d.outcome not in case["expect"]["outcome_in"]:
        failed.append(f"outcome {d.outcome} not in {case['expect']['outcome_in']}")
    for a in case["expect"].get("assert", []):
        why = _assert(art.front, a)
        if why:
            failed.append(why)
    return {"id": case["id"], "pass": not failed, "failed_checks": failed, "outcome": d.outcome}


def content_hash(sk: Skill) -> str:
    """Hash of SKILL.md, skill.yaml minus status, rubric, checks, evals/cases/** (SDD-01 §6.2)."""
    parts: list[str] = []
    meta = {k: v for k, v in sk.meta.items() if k != "status"}
    parts.append(f"skill.yaml\0{sha256_raw(canonical(meta))}")
    for name in ("SKILL.md", str(sk.meta["rubric"]), str(sk.meta.get("checks") or "checks.yaml")):
        p = sk.dir / name
        if p.is_file():
            parts.append(f"{name}\0{sha256_file(p)}")
    for p in sorted((sk.dir / "evals" / "cases").rglob("*")):
        if p.is_file():
            parts.append(f"{p.relative_to(sk.dir).as_posix()}\0{sha256_file(p)}")
    return sha256_text("\n".join(parts))


def run(rt: Runtime, skill: str, version: str | None) -> tuple[dict[str, Any], str | None]:
    sk = _skill(rt, skill, version)
    es, cases = _cases(sk)
    signer = load_signer(rt)
    per = [score_case(rt, sk, d, c) for d, c in cases]
    passed = sum(1 for p in per if p["pass"])
    rate = round4(passed / len(per)) if per else 0.0
    kinds = {c["id"]: c["kind"] for _, c in cases}
    shas = {c["id"]: sha256_file(d / "case.yaml") for d, c in cases}
    rec: dict[str, Any] = {
        "schema": "eval-result.v1",
        "skill": sk.id,
        "version": sk.version,
        "skill_sha256": content_hash(sk),
        "cases": [
            {
                "id": p["id"],
                "kind": kinds[p["id"]],
                "case_sha256": shas[p["id"]],
                "result": "pass" if p["pass"] else "fail",
                **({"outcome": p["outcome"]} if p["outcome"] else {}),
            }
            for p in per
        ],
        "cases_total": len(per),
        "cases_passed": passed,
        "pass_rate": rate,
        "repeats": 1,
        "recorded_by": f"tsl@{rt.tsl_version}",
        "recorded_at": iso(rt.clock()),
    }
    if not per:
        raise TslError("E-EVAL-01", rate=0, min=es["min_pass_rate"], n=es["min_cases"])
    signed = sign_object(rec, signer.key_id, signer.private)
    from tsl.schemas.registry import require_valid

    require_valid("eval-result.v1", signed, "eval result")
    out = sk.dir / "evals" / "results" / f"{sk.version}.eval-result.json"
    write_json(out, signed)
    emit(
        rt,
        "eval.recorded",
        {
            "skill": sk.id,
            "version": sk.version,
            "cases": len(per),
            "pass_rate": rate,
            "key_id": signer.key_id,
            "result_sha256": sha256_file(out),
        },
    )
    data = {
        "skill": sk.id,
        "version": sk.version,
        "cases": len(per),
        "passed": passed,
        "pass_rate": rate,
        "result_path": str(out),
        "key_id": signer.key_id,
        "per_case": [
            {"id": p["id"], "pass": p["pass"], "failed_checks": p["failed_checks"]} for p in per
        ],
    }
    code = None
    if rate < float(es["min_pass_rate"]) or len(per) < int(es["min_cases"]):
        code = "E-EVAL-01"
    return data, code


def check(rt: Runtime, skill: str, case_id: str) -> dict[str, Any]:
    sk = _skill(rt, skill, None)
    _, cases = _cases(sk)
    for d, c in cases:
        if c["id"] == case_id:
            return score_case(rt, sk, d, c)
    raise TslError("E-USE-01", detail=f"no case {case_id}", cmd="eval check")
