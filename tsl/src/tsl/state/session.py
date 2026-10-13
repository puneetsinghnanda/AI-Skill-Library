"""Session index and compiled policy for the hooks (SDD-04 §6.14, §11; SDD-05 §6.4)."""

from __future__ import annotations

import contextlib
import json
from pathlib import Path
from typing import Any

from tsl.core.clock import iso
from tsl.core.jsonio import read_json, read_yaml, write_json
from tsl.core.repo import Companion
from tsl.core.runtime import Runtime

SENSITIVE_READ = [
    ".env",
    ".env.*",
    "*.pem",
    "*.key",
    "*.p12",
    "*.pfx",
    "id_rsa*",
    "id_ed25519*",
    "secrets/*",
    "*.kdbx",
]


def org_policy(rt: Runtime) -> dict[str, Any]:
    from tsl.schemas.registry import require_valid

    p = rt.plugin_root() / "policy" / "policy.yaml"
    data = read_yaml(p)
    require_valid("policy.v2", data, "policy/policy.yaml")
    if "allow" not in (data.get("write_scope") or {}):
        raise ValueError("org policy must be the complete form")
    return dict(data)


def compile_policy(rt: Runtime, comp: Companion, run_id: str, pinned_tsl: str) -> dict[str, Any]:
    pol = org_policy(rt)
    add = comp.system_policy() or {}
    root = str(comp.root)
    products: list[str] = []
    for repo in comp.config.product_repos:
        clone = comp.local_paths().get(repo.name)
        if clone:
            base = str(clone) if repo.path in (".", "") else str(clone / repo.path)
            products.append(base)

    def expand(pattern: str) -> list[str]:
        p = pattern.replace("<companion>", root).replace("<run_id>", run_id)
        if "<product_repos>" in p:
            return [p.replace("<product_repos>", b) for b in products]
        return [p]

    allow = [x for pat in pol["write_scope"]["allow"] for x in expand(pat)]
    deny = [x for pat in pol["write_scope"]["deny"] for x in expand(pat)]
    deny += [x for pat in (add.get("write_scope") or {}).get("deny", []) for x in expand(pat)]
    read_only = []
    for ro in comp.config.read_only_repos:
        clone = comp.local_paths().get(str(ro["name"]))
        if clone:
            read_only.append(f"{clone}/**")
    bash = list(pol["bash_in_run"]["deny_patterns"]) + list(
        (add.get("bash_in_run") or {}).get("deny_patterns", [])
    )
    mcp = dict(pol["mcp"])
    mcp["write_tools_need_approval"] = list(mcp["write_tools_need_approval"]) + list(
        (add.get("mcp") or {}).get("write_tools_need_approval", [])
    )
    return {
        "run_id": run_id,
        "companion": root,
        "allow": allow,
        "deny": deny + read_only,
        "bash_deny": bash,
        "read_deny": SENSITIVE_READ + list(add.get("read_deny", [])),
        "mcp": mcp,
        "pinned_tsl": pinned_tsl,
    }


def bind(
    rt: Runtime,
    comp: Companion,
    session_id: str,
    run_id: str,
    lock_rel: str,
    policy: dict[str, Any],
) -> dict[str, Any]:
    idx = {
        "schema": "session-index.v1",
        "session_id": session_id,
        "run_id": run_id,
        "companion": str(comp.root),
        "lock": lock_rel,
        "bound_at": iso(rt.clock()),
    }
    from tsl.schemas.registry import require_valid

    require_valid("session-index.v1", idx, "session index")
    rt.home.ensure()
    write_json(rt.home.session(session_id), idx)
    write_json(rt.home.session_policy(session_id), policy)
    return idx


def unbind_run(rt: Runtime, run_id: str) -> None:
    d = rt.home.sessions
    if not d.is_dir():
        return
    for p in d.glob("*.json"):
        if p.name.endswith(".policy.json"):
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if data.get("run_id") == run_id:
            with contextlib.suppress(OSError):
                p.unlink()
            pol = p.with_name(p.name[:-5] + ".policy.json")
            with contextlib.suppress(OSError):
                pol.unlink()


def read_index(path: Path) -> dict[str, Any] | None:
    try:
        data = read_json(path)
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None
