"""pre-mcp: MCP reads allowed; writes need a signed approval in approvals.md (SDD-05 §5.3, R-14)."""

from __future__ import annotations

import fnmatch
import json
from pathlib import Path
from typing import Any

from tsl.hooks.dispatch import Ctx, active_run, allow, deny, log_tool, policy_for


def _org_mcp(ctx: Ctx) -> dict[str, Any]:
    root = ctx.env.get("CLAUDE_PLUGIN_ROOT")
    if not root:
        f = ctx.home / "cache" / "plugin-root.txt"
        root = f.read_text(encoding="utf-8").strip() if f.is_file() else ""
    p = Path(root) / "policy" / "policy.yaml"
    from tsl.core.jsonio import read_yaml

    return dict(read_yaml(p)["mcp"])


def _approved(ctx: Ctx, idx: dict[str, Any]) -> bool:
    from tsl.approvals import approvals_md
    from tsl.core.clock import parse_iso
    from tsl.identity.keys import public_key
    from tsl.identity.verify import accept, facts_from

    p = Path(idx["companion"]) / "runs" / idx["run_id"] / "approvals.md"
    if not p.is_file():
        return False
    obj = approvals_md.parse(p.read_text(encoding="utf-8"))
    payload = json.dumps(ctx.data.get("tool_input") or {}, sort_keys=True)
    for e in obj.get("entries", []):
        b = e.get("signature") or {}
        act = b.get("action") or {}
        if b.get("kind") != "external_write" or b.get("decision") != "approve":
            continue
        if act.get("tool") != ctx.tool or str(act.get("target", "")) not in payload:
            continue
        facts = public_key(
            ctx.rt, str(b.get("key_id")), online=False
        )  # no network on the hook path
        verdict, _ = accept(
            b, parse_iso(str(b["approved_at"])), [], facts_from(facts), check_roles=False
        )
        if verdict != "bad":
            return True
    return False


def handle(ctx: Ctx) -> tuple[str, int]:
    idx = None
    try:
        idx = active_run(ctx)
    except Exception:
        idx = None
    try:
        mcp = policy_for(ctx, idx)["mcp"] if idx else _org_mcp(ctx)
        is_read = any(
            fnmatch.fnmatch(ctx.tool, g)
            for g in [*mcp.get("local_tools", []), *mcp.get("read_tools", [])]
        )
        if is_read:
            if idx:
                log_tool(idx, ctx, ctx.tool, "allow", None)
            return allow(ctx)
        if (
            idx
            and any(fnmatch.fnmatch(ctx.tool, g) for g in mcp.get("write_tools_need_approval", []))
            and _approved(ctx, idx)
        ):
            log_tool(idx, ctx, ctx.tool, "allow", None)
            return allow(ctx)
        if idx:
            log_tool(idx, ctx, ctx.tool, "deny", "E-POL-03")
        return deny(ctx, "E-POL-03", f"Blocked: MCP write {ctx.tool} without approval")
    except Exception:
        if idx:
            return deny(
                ctx, "E-HOOK-01", "MCP call blocked: tsl did not answer while a run is active"
            )
        return deny(
            ctx, "E-POL-03", f"Blocked: MCP write {ctx.tool} without approval (policy unavailable)"
        )
