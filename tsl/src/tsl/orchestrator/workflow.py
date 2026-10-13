"""workflow.v1 loading, graph validation and skill resolution (SDD-02 §3)."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from tsl.core.config import ORG_DEFAULTS
from tsl.core.errors import TslError
from tsl.core.jsonio import read_json, read_yaml
from tsl.orchestrator.skills import Skill, range_matches


def step_id(step: dict[str, Any]) -> str:
    if "gate" in step:
        return str(step["gate"])
    if step.get("pr") is True:
        return "pr"
    return str(step["id"])


def step_kind(step: dict[str, Any]) -> str:
    return "gate" if "gate" in step else "pr" if step.get("pr") is True else "skill"


def skill_name(step: dict[str, Any]) -> str:
    return str(step["skill"]).split("@", 1)[0]


def skill_range(step: dict[str, Any]) -> str:
    return str(step["skill"]).split("@", 1)[1]


def load(plugin_root: Path, workflow_id: str) -> tuple[dict[str, Any], Path]:
    p = plugin_root / "workflows" / f"{workflow_id}.workflow.yaml"
    if not p.is_file():
        raise TslError("E-USE-01", detail=f"unknown workflow {workflow_id}", cmd="state start")
    data = read_yaml(p)
    from tsl.schemas.registry import errors

    errs = errors("workflow.v1", data)
    if errs:
        raise TslError("E-CFG-01", file=p.name, pointer=errs[0].pointer, reason=errs[0].message)
    return data, p


def load_lock(path: Path) -> dict[str, Any] | None:
    lock = path.with_name(path.name.replace(".workflow.yaml", ".lock.json"))
    return read_json(lock) if lock.is_file() else None


def ancestors(wf: dict[str, Any]) -> dict[str, set[str]]:
    deps = {step_id(s): set(s.get("after", [])) for s in wf["steps"]}
    memo: dict[str, set[str]] = {}

    def walk(n: str, stack: tuple[str, ...]) -> set[str]:
        if n in memo:
            return memo[n]
        if n in stack:
            return set()
        out: set[str] = set()
        for d in deps.get(n, set()):
            out.add(d)
            out |= walk(d, (*stack, n))
        memo[n] = out
        return out

    return {n: walk(n, ()) for n in deps}


def downstream(wf: dict[str, Any], sid: str) -> list[str]:
    anc = ancestors(wf)
    return [n for n in (step_id(s) for s in wf["steps"]) if sid in anc[n]]


def resolve(
    wf: dict[str, Any], skills: dict[str, Skill], lock: dict[str, Any] | None
) -> dict[str, str]:
    """step id -> exact skill ref. Uses the lock file when present (FR-WFL-02)."""
    out: dict[str, str] = {}
    for s in wf["steps"]:
        if step_kind(s) != "skill":
            continue
        name, rng = skill_name(s), skill_range(s)
        if lock and step_id(s) in lock.get("resolved", {}):
            ref = str(lock["resolved"][step_id(s)])
            out[step_id(s)] = ref
            continue
        sk = skills.get(name)
        if sk is None or not range_matches(sk.version, rng):
            raise TslError(
                "E-WFL-04", detail=f"{s['skill']} (installed: {sk.version if sk else 'none'})"
            )
        out[step_id(s)] = sk.ref
    return out


def snapshot(wf: dict[str, Any], resolved: dict[str, str]) -> dict[str, Any]:
    snap = copy.deepcopy(wf)
    for s in snap["steps"]:
        if step_kind(s) == "skill":
            s["skill"] = resolved[step_id(s)]
    return snap


def validate(wf: dict[str, Any], skills: dict[str, Skill]) -> list[tuple[str, str, str]]:
    """(code, pointer, message) per problem (SDD-02 §3.5)."""
    from tsl.schemas.registry import errors

    out: list[tuple[str, str, str]] = []
    for e in errors("workflow.v1", wf):
        out.append(("E-WFL-01", e.pointer, e.message))
    if out:
        return out
    steps = wf["steps"]
    ids = [step_id(s) for s in steps]
    seen: set[str] = set()
    for i, sid in enumerate(ids):
        if sid in seen:
            out.append(("E-WFL-02", f"/steps/{i}", f"duplicate step id {sid}"))
        seen.add(sid)
    for i, s in enumerate(steps):
        for d in s.get("after", []):
            if d not in seen or d == "pr":
                out.append(("E-WFL-02", f"/steps/{i}/after", f"unknown step {d}"))
    anc = ancestors(wf)
    for sid in ids:
        if sid in anc[sid]:
            out.append(("E-WFL-02", "/steps", f"cycle through {sid}"))
    roots = {step_id(s) for s in steps if not s.get("after")}
    if not roots:
        out.append(("E-WFL-02", "/steps", "no first step"))
    for sid in ids:
        if sid not in roots and not (anc[sid] & roots):
            out.append(("E-WFL-02", "/steps", f"{sid} unreachable"))
    for i, s in enumerate(steps):
        if step_kind(s) == "pr" and i != len(steps) - 1:
            out.append(("E-WFL-02", f"/steps/{i}", "pr step must be last"))
        if step_kind(s) == "gate":
            rej = s["on_reject"]
            if rej != "abort" and rej not in anc[step_id(s)]:
                out.append(("E-WFL-02", f"/steps/{i}/on_reject", f"{rej} is not upstream"))
            ch = s.get("on_changes")
            if ch and ch not in anc[step_id(s)]:
                out.append(("E-WFL-02", f"/steps/{i}/on_changes", f"{ch} is not upstream"))
            for a in s.get("artifacts", []):
                if a not in anc[step_id(s)]:
                    out.append(("E-WFL-02", f"/steps/{i}/artifacts", f"{a} is not upstream"))
    if wf["kind"] == "read_only":
        for i, s in enumerate(steps):
            if step_kind(s) == "pr":
                out.append(("E-WFL-02", f"/steps/{i}", "read_only workflow has a pr step"))
            if step_kind(s) == "skill" and (sk := skills.get(skill_name(s))) and sk.is_code:
                out.append(("E-WFL-02", f"/steps/{i}", "read_only workflow has a code skill"))
    org = ORG_DEFAULTS["retry"]
    for where, retry in [("/defaults/retry", (wf.get("defaults") or {}).get("retry") or {})] + [
        (f"/steps/{i}/retry", s.get("retry") or {}) for i, s in enumerate(steps)
    ]:
        for k, v in retry.items():
            if v > org[k]:
                out.append(("E-WFL-05", f"{where}/{k}", f"{v} > org maximum {org[k]}"))
    # skills resolve and bindings type-check
    for i, s in enumerate(steps):
        if step_kind(s) != "skill":
            continue
        sk = skills.get(skill_name(s))
        if sk is None or not range_matches(sk.version, skill_range(s)):
            out.append(("E-WFL-04", f"/steps/{i}/skill", f"{s['skill']} does not resolve"))
            continue
        binds = s.get("inputs") or {}
        for name, b in binds.items():
            if b == "run.ticket" or b.startswith("context."):
                continue
            src, outname = b.split(".", 1)
            if src not in anc[step_id(s)]:
                out.append(("E-WFL-02", f"/steps/{i}/inputs/{name}", f"{src} is not upstream"))
                continue
            prod = next((x for x in steps if step_id(x) == src), None)
            psk = skills.get(skill_name(prod)) if prod and step_kind(prod) == "skill" else None
            if psk is None:
                out.append(("E-WFL-03", f"/steps/{i}/inputs/{name}", f"{src} produces nothing"))
                continue
            produced = {o["name"]: o.get("schema") for o in psk.meta["outputs"]}
            if outname not in produced:
                out.append(
                    ("E-WFL-03", f"/steps/{i}/inputs/{name}", f"{src} has no output {outname}")
                )
                continue
            want = next((x.get("schema") for x in sk.meta["inputs"] if x["name"] == name), None)
            if want and want != produced[outname]:
                out.append(
                    (
                        "E-WFL-03",
                        f"/steps/{i}/inputs/{name}",
                        f"schema {produced[outname]} != {want}",
                    )
                )
        for x in sk.meta["inputs"]:
            if x.get("source") == "artifact" and x.get("required", True) and x["name"] not in binds:
                out.append(
                    ("E-WFL-03", f"/steps/{i}/inputs", f"required input {x['name']} unbound")
                )
    return out
