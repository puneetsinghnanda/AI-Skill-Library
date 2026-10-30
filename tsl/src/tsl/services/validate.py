"""tsl validate <path>... [--lock] (SDD-04 §6.5, SDD-01 §14.1, SDD-02 §3.5, SDD-05 §6.4)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tsl.core.config import tighten_errors
from tsl.core.errors import TslError
from tsl.core.frontmatter import FrontMatterError, headings, norm_title, split
from tsl.core.hashing import sha256_text
from tsl.core.jsonio import read_any, read_yaml, write_json
from tsl.core.runtime import Runtime
from tsl.harness import detectors
from tsl.harness.skillchecks import validate_declared
from tsl.orchestrator import skills as skillmod
from tsl.orchestrator import workflow as wfmod
from tsl.schemas.registry import errors as schema_errors
from tsl.schemas.registry import readable

BODY_HEADINGS = ["job", "inputs", "rules", "method", "output", "if this is a retry", "hand-over"]
PREAMBLE = "!`tsl verify $0 --inputs --json`"
COMMAND_SKILLS = {"run", "resume", "status", "eval", "improve", "review", "context-draft"}
MIX = {"normal": 4, "edge": 2, "conflict": 1, "adversarial": 1, "forbidden-content": 1}


def _res(path: str, schema: str, errs: list[tuple[str, str, str]]) -> dict[str, Any]:
    return {
        "path": path,
        "schema": schema,
        "ok": not errs,
        "errors": [{"pointer": p, "message": m, "code": c} for c, p, m in errs],
    }


def _schema_of(path: Path) -> tuple[str, Any]:
    if path.suffix == ".md":
        doc = split(path.read_text(encoding="utf-8"))
        return str(doc.front.get("schema", "")), doc.front
    data = read_any(path)
    return (str(data.get("schema", "")) if isinstance(data, dict) else ""), data


def validate_file(path: Path, plugin_root: Path | None) -> dict[str, Any]:
    try:
        schema, data = _schema_of(path)
    except (FrontMatterError, ValueError, OSError) as exc:
        return _res(str(path), "", [("E-CFG-01", "/", f"cannot parse: {type(exc).__name__}")])
    if path.name.endswith(".workflow.yaml"):
        return validate_workflow(path, data, plugin_root)
    try:
        sid = readable(schema, str(path))
    except TslError:
        return _res(str(path), schema, [("E-SCH-01", "/schema", f"schema {schema} not readable")])
    if not sid:
        return _res(
            str(path), schema, [("E-CFG-01", "/schema", f"unknown schema {schema or '(none)'}")]
        )
    errs = [("E-CFG-01", e.pointer or "/", e.message) for e in schema_errors(sid, data)]
    if sid == "tsl-config.v1" and not errs:
        errs += [("E-CFG-01", p, m) for p, m in tighten_errors(data)]
    if sid == "rubric.v1" and not errs:
        total = sum(float(c["weight"]) for c in data["criteria"])
        if abs(total - 1.0) > 0.001:
            errs.append(("E-CFG-01", "/criteria", f"SKL-V07 weights sum to {total:.3f}, not 1.00"))
    if sid == "skill-checks.v1" and not errs:
        errs += [("E-CFG-01", "/checks", m) for m in validate_declared(data)]
    return _res(str(path), sid, errs)


def validate_workflow(
    path: Path,
    data: Any,
    plugin_root: Path | None,
    lock: bool = False,
    plugin_version: str | None = None,
    tsl_version: str = "0.0.0",
) -> dict[str, Any]:
    installed = skillmod.installed(plugin_root) if plugin_root else {}
    errs = wfmod.validate(data, installed)
    for s in data.get("steps", []) if isinstance(data, dict) else []:
        if wfmod.step_kind(s) == "skill" and data.get("status") != "draft":
            sk = installed.get(wfmod.skill_name(s))
            if sk and sk.meta.get("status") == "draft":
                errs.append(
                    (
                        "E-WFL-04",
                        f"/steps/{wfmod.step_id(s)}",
                        f"{sk.id} is draft; only a draft workflow may use it",
                    )
                )
    res = _res(str(path), "workflow.v1", [(c, p, m) for c, p, m in errs])
    if lock and not errs and plugin_root is not None:
        resolved = wfmod.resolve(data, installed, None)
        out = path.with_name(path.name.replace(".workflow.yaml", ".lock.json"))
        doc = {
            "schema": "workflow-lock.v1",
            "workflow": f"{data['id']}@{data['version']}",
            "workflow_sha256": sha256_text(path.read_text(encoding="utf-8")),
            "plugin_version": plugin_version or tsl_version,
            "resolved": resolved,
            "generated_by": f"tsl@{tsl_version}",
        }
        from tsl.schemas.registry import require_valid

        require_valid("workflow-lock.v1", doc, out.name)
        write_json(out, doc)
        res["lock"] = str(out)
    return res


def validate_skill(d: Path) -> dict[str, Any]:
    errs: list[tuple[str, str, str]] = []

    def e(rule: str, msg: str, ptr: str = "/") -> None:
        errs.append(("E-CFG-01", ptr, f"{rule} {msg}"))

    try:
        meta = read_yaml(d / "skill.yaml")
    except (OSError, ValueError) as exc:
        return _res(str(d), "skill-metadata.v1", [("E-CFG-01", "/", f"SKL-V02 {exc}")])
    for se in schema_errors("skill-metadata.v1", meta):
        e("SKL-V02", se.message, se.pointer)
    if errs:
        return _res(str(d), "skill-metadata.v1", errs)
    sk = skillmod.Skill(d, meta)
    try:
        doc = split((d / "SKILL.md").read_text(encoding="utf-8"))
    except (OSError, FrontMatterError) as exc:
        e("SKL-V03", f"SKILL.md: {exc}")
        return _res(str(d), "skill-metadata.v1", errs)
    if not (d.name == meta["id"] == doc.front.get("name")):
        e("SKL-V01", "folder name, skill.yaml id and SKILL.md name differ")
    for k in ("name", "description", "argument-hint", "user-invocable", "allowed-tools"):
        if k not in doc.front:
            e("SKL-V03", f"SKILL.md front matter lacks {k}")
    lines = [x.strip() for x in doc.body.split("\n") if x.strip()]
    if len(lines) < 2 or lines[1] != PREAMBLE:
        e("SKL-V04", "the input-check preamble must be the first body content")
    got = [norm_title(h.title) for h in headings(doc.body) if h.level == 2]
    if [g for g in got if g in BODY_HEADINGS] != BODY_HEADINGS:
        e("SKL-V05", "body headings missing or out of order")
    if len(doc.body.split("\n")) > 500:
        e("SKL-V05", "body longer than 500 lines")
    try:
        rub = sk.rubric
        for se in schema_errors("rubric.v1", rub):
            e("SKL-V06", se.message, se.pointer)
        if not schema_errors("rubric.v1", rub):
            total = sum(float(c["weight"]) for c in rub["criteria"])
            if abs(total - 1.0) > 0.001:
                e("SKL-V07", f"weights sum to {total:.3f}")
    except TslError as exc:
        e("SKL-V06", exc.message)
    chk = d / str(meta.get("checks") or "checks.yaml")
    if chk.is_file():
        cdoc = read_yaml(chk)
        for se in schema_errors("skill-checks.v1", cdoc):
            e("SKL-V08", se.message, se.pointer)
        if not schema_errors("skill-checks.v1", cdoc):
            for m in validate_declared(cdoc):
                e("SKL-V08", m)
    else:
        e("SKL-V08", "checks.yaml missing")
    tools = str(doc.front.get("allowed-tools", ""))
    want = {*meta.get("allowed_tools", []), "Bash(tsl verify *)"}
    have = {t.strip() for t in tools.split(",") if t.strip()}
    if have != want:
        e("SKL-V09", "SKILL.md allowed-tools must equal allowed_tools + Bash(tsl verify *)")
    cases = sorted((d / "evals" / "cases").glob("*/case.yaml"))
    kinds: dict[str, int] = {}
    for c in cases:
        cd = read_yaml(c)
        for se in schema_errors("eval-case.v1", cd):
            e("SKL-V10", f"{c.parent.name}: {se.message}", se.pointer)
        kinds[str(cd.get("kind"))] = kinds.get(str(cd.get("kind")), 0) + 1
    min_cases = int((meta.get("evals") or {}).get("min_cases", 10))
    if len(cases) < min_cases:
        e("SKL-V10", f"{len(cases)} eval cases, minimum {min_cases}")
    for k, n in MIX.items():
        if kinds.get(k, 0) < n:
            e("SKL-V10", f"needs at least {n} {k} case(s)")
    for p in sorted(d.rglob("*")):
        if not p.is_file() or p.suffix not in (".md", ".yaml", ".yml", ".json", ".txt"):
            continue
        rel = p.relative_to(d).as_posix()
        for h in detectors.scan(p.read_text(encoding="utf-8", errors="replace")):
            if h.kind in ("secret", "pii") and not (
                rel.startswith("evals/") and h.rule_id == "SEC-P-08"
            ):
                e("SKL-V12", f"forbidden content {h.rule_id} in {rel} line {h.line}")
    return _res(str(d), "skill-metadata.v1", errs)


def validate_plugin(d: Path, rt: Runtime) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    pj = json.loads((d / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    perrs: list[tuple[str, str, str]] = []
    if pj.get("name") != "truminds":
        perrs.append(("E-CFG-01", "/name", "plugin name must be truminds"))
    if pj.get("version") != rt.tsl_version:
        perrs.append(
            ("E-CFG-01", "/version", f"plugin {pj.get('version')} != tsl {rt.tsl_version}")
        )
    hooks = d / "hooks" / "hooks.json"
    if hooks.is_file():
        h = json.loads(hooks.read_text(encoding="utf-8")).get("hooks", {})
        if set(h) != {"SessionStart", "PreToolUse", "PostToolUse", "SessionEnd"}:
            perrs.append(
                ("E-CFG-01", "/hooks", "hooks.json must list exactly the SDD-05 §5.2 events")
            )
        for ev in h.values():
            for m in ev:
                for x in m.get("hooks", []):
                    if "timeout" not in x:
                        perrs.append(("E-CFG-01", "/hooks", "every hook needs an explicit timeout"))
    if (d / "skills").is_dir():
        from tsl.orchestrator import agents as agentmod

        for name in agentmod.stale(d):
            perrs.append(
                ("E-CFG-01", f"/agents/{name}", "stale; run python -m tsl.orchestrator.agents")
            )
    out.append(_res(str(d / ".claude-plugin" / "plugin.json"), "plugin", perrs))
    pol = d / "policy" / "policy.yaml"
    if pol.is_file():
        out.append(validate_file(pol, d))
    for sd in sorted((d / "skills").glob("*")) if (d / "skills").is_dir() else []:
        if (sd / "skill.yaml").is_file():
            out.append(validate_skill(sd))
        elif sd.name in COMMAND_SKILLS and (sd / "SKILL.md").is_file():
            fm = split((sd / "SKILL.md").read_text(encoding="utf-8")).front
            errs: list[tuple[str, str, str]] = []
            if sd.name != "review" and fm.get("disable-model-invocation") is not True:
                errs.append(
                    ("E-CFG-01", "/disable-model-invocation", "command skills must set true")
                )
            if sd.name == "review" and (
                fm.get("context") != "fork" or fm.get("agent") != "truminds:reviewer"
            ):
                errs.append(
                    ("E-CFG-01", "/context", "review skill must fork into truminds:reviewer")
                )
            out.append(_res(str(sd), "command-skill", errs))
    for wf in (
        sorted((d / "workflows").glob("*.workflow.yaml")) if (d / "workflows").is_dir() else []
    ):
        out.append(validate_workflow(wf, read_yaml(wf), d))
    return out


def validate(rt: Runtime, paths: list[Path], lock: bool) -> tuple[dict[str, Any], str | None]:
    results: list[dict[str, Any]] = []
    for p in paths:
        if not p.exists():
            raise TslError("E-USE-01", detail=f"{p} does not exist", cmd="validate")
        plugin_root = next(
            (
                q
                for q in (p, *p.resolve().parents)
                if (q / ".claude-plugin" / "plugin.json").is_file() and (q / "skills").exists()
            ),
            None,
        )
        if p.is_dir() and (p / ".claude-plugin" / "plugin.json").is_file():
            results += validate_plugin(p, rt)
        elif p.is_dir() and (p / "skill.yaml").is_file():
            results.append(validate_skill(p))
        elif p.name.endswith(".workflow.yaml"):
            pv = None
            if plugin_root:
                pv = json.loads((plugin_root / ".claude-plugin" / "plugin.json").read_text())[
                    "version"
                ]
            results.append(
                validate_workflow(p, read_yaml(p), plugin_root, lock, pv, rt.tsl_version)
            )
        elif p.is_file():
            results.append(validate_file(p, plugin_root))
        else:
            raise TslError(
                "E-USE-01", detail=f"{p}: not a skill folder, plugin or file", cmd="validate"
            )
    bad = [r for r in results if not r["ok"]]
    code = bad[0]["errors"][0]["code"] if bad else None
    return {"results": results}, code
