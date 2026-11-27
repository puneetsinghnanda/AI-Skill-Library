"""pre-tool: write scope, Bash rules and the open step's tools while a run is active (SDD-05 §5.3).

While a step's skill is open (tsl verify --inputs marked it launched and tsl decide has not run),
a tool outside that skill's allowed-tools is refused before it runs, so H7 never has to fail the
step for it afterwards. The run loop's own tools (tsl commands, the review skill) stay allowed.
"""

from __future__ import annotations

import fnmatch
import json
import os
import re
import time
from pathlib import Path
from typing import Any

from tsl.hooks.dispatch import Ctx, active_run, allow, deny, log_tool, policy_for, version_ok

BIND_WINDOW_S = 600
# Tools the run loop itself uses between the skill and tsl decide; never step work.
RUN_LOOP_TOOLS = frozenset({"Skill", "Agent", "Task", "ToolSearch", "AskUserQuestion", "TodoWrite"})
LOGGED = ("Write", "Edit", "NotebookEdit", "Bash")
WRITE_TOOLS = ("Write", "Edit", "NotebookEdit")
# Written by tsl only: artifacts cite the answers, and the wait time is the engineer's.
TSL_ONLY = {
    "*/runs/*/ide-answers.md": "ide-answers.md is written by tsl from AskUserQuestion only",
    "*/runs/*/ide-questions.json": "ide-questions.json is written by tsl from AskUserQuestion only",
}
# A tool call this soon after an ask can be a parallel call of the same message, with the
# dialog still open: it does not close the ask.
ASK_CLOSE_AFTER_S = 10


def _is_reviewer(ctx: Ctx) -> bool:
    """The call comes from the truminds reviewer subagent (hook input agent_type)."""
    at = str(ctx.data.get("agent_type") or "")
    return at in ("reviewer", "truminds:reviewer") or at.endswith(":reviewer")


def _reviewer_write_refused(ctx: Ctx, idx: dict[str, Any] | None) -> str | None:
    """Why the reviewer may not make this write, or None. It may Write one file only: the
    review input of the bound run's current step. Outside a bound run it writes nothing."""
    if idx is None:
        return "the reviewer writes only inside a bound run; return the JSON instead"
    step = str((idx["_state"].get("cursor") or {}).get("step") or "")
    want = _abs(ctx, f"{idx['companion']}/runs/{idx['run_id']}/review-input/{step}.review.json")
    ti = ctx.data.get("tool_input") or {}
    got = _abs(ctx, str(ti.get("file_path") or ti.get("notebook_path") or ""))
    if ctx.tool == "Write" and step and os.path.normcase(got) == os.path.normcase(want):
        return None
    rel = f"runs/{idx['run_id']}/review-input/{step or '<step>'}.review.json"
    return f"the reviewer writes only {rel} with Write; return the JSON instead"


def _open_step(ctx: Ctx, idx: dict[str, Any]) -> tuple[str, list[str]] | None:
    """(skill id, allowed tools) of the cursor step while its skill is open, else None."""
    st = idx["_state"]
    cur = st.get("cursor") or {}
    step = cur.get("step")
    if not step:
        return None
    s = next((x for x in st.get("steps", []) if x.get("id") == step), None)
    a = (s or {}).get("attempts") or []
    if not a or not a[-1].get("skill_started_at") or a[-1].get("decided_at"):
        return None
    from tsl.core.repo import Companion
    from tsl.orchestrator.run import RunCtx

    try:
        run = RunCtx(ctx.rt, Companion(Path(idx["companion"])), idx["run_id"])
        sk = run.skill_for(str(step))
    except Exception:
        return None  # skill not loadable: H7 still checks the step afterwards
    return sk.id, sk.allowed_tools


def _off_step(ctx: Ctx, cmd: str, open_step: tuple[str, list[str]]) -> str | None:
    """Why this call is outside the open step's tools, or None when it is allowed."""
    skill, allowed = open_step
    tool = ctx.tool
    if tool == "Bash":
        from tsl.harness.commands import bash_allowed, is_read_only

        if bash_allowed(cmd, allowed):
            return None
        if is_read_only(cmd) or cmd.strip().startswith(("sed ", "awk ", "type ")):
            return f"step {skill} reads files with Read, Grep or Glob, not shell commands"
        return f"Bash command is not in step {skill}'s tools; only tsl commands run here"
    if tool in allowed or tool in RUN_LOOP_TOOLS:
        return None
    if tool == "NotebookEdit" and "Edit" in allowed:
        return None
    if tool == "PowerShell":
        return f"step {skill} runs tsl through the Bash tool, not PowerShell"
    return f"tool {tool} is not in step {skill}'s tools ({', '.join(allowed)})"


READ_TOOLS = ("Read", "Grep", "Glob")
_WILD = set("*?[{")


def _record_ask(ctx: Ctx, idx: dict[str, Any], ti: dict[str, Any]) -> None:
    """ide-questions.json (roadmap B2): AskUserQuestion opens an ask; any other tool of the same
    agent closes the asks it left open (the dialog was dismissed: no post-tool hook came).

    Best effort: this hook is fail-closed inside a run, so a failure here must never deny."""
    try:
        from tsl.approvals import ide_questions

        root = Path(idx["companion"])
        agent = ctx.data.get("agent_id") or None
        if ctx.tool != "AskUserQuestion":
            ide_questions.close_open(
                root,
                idx["run_id"],
                reason="dismissed",
                agent_id=agent,
                older_than_s=ASK_CLOSE_AFTER_S,
            )
            return
        step, attempt = ide_questions.ask_step(idx["_state"])
        ide_questions.raised(
            root,
            idx["run_id"],
            step,
            attempt,
            ide_questions.questions_of(ti),
            source="hook",
            tool_use_id=str(ctx.data.get("tool_use_id") or ""),
            agent_id=agent,
        )
    except Exception as exc:  # a missed record only loses the wait time: noted for tsl doctor
        from tsl.approvals import ide_questions

        ide_questions.note_failure(ctx.home, str(idx.get("run_id")), "pre-tool", exc)


def _rel_parts(root: str, path: str) -> list[str] | None:
    """Path parts relative to the companion root, or None when the path is outside it."""
    # normcase lowers the case on Windows and turns / into \; compare with / again.
    r = os.path.normcase(root.rstrip("/")).replace("\\", "/")
    p = os.path.normcase(path).replace("\\", "/")
    if p == r:
        return []
    if not p.startswith(r + "/"):
        return None
    return [x for x in path[len(root.rstrip("/")) + 1 :].split("/") if x and x != "."]


def _other_run_read(ctx: Ctx, idx: dict[str, Any], ti: dict[str, Any]) -> str | None:
    """Why this Read, Grep or Glob reaches another run's files, or None (while a run is bound).

    Runs are independent: the run loop, the skill and its reviewer read only this run's
    folders (artifacts/<ticket>/<run_id>/, runs/<run_id>/), never another run's, even of the
    same ticket, its answers or questions. A search whose scope takes in other runs (the repo
    root, artifacts/, runs/, a ticket folder, or a wildcard there) is refused too.

    One exception: a skill that reads run states (an input of schema run-state.v1, as
    status-report has) may Read or Glob runs/<any run>/state.json, and nothing else of
    another run."""
    root = _abs(ctx, str(idx["companion"]))
    run_id = str(idx["run_id"])
    if ctx.tool == "Read":
        target = str(ti.get("file_path") or "")
    else:
        base = str(ti.get("path") or ctx.data.get("cwd") or ".")
        extra = str(ti.get("pattern") if ctx.tool == "Glob" else ti.get("glob") or "")
        target = base + ("/" + extra if extra and not extra.startswith("!") else "")
    parts = _rel_parts(root, _abs(ctx, target)) if target else None
    if parts is None:
        return None  # outside the companion repo (product repos)
    first = parts[0] if parts else ""
    if parts and first not in ("artifacts", "runs") and not (_WILD & set(first)):
        return None  # context/, policy files ...
    if ctx.tool in ("Read", "Glob") and is_run_state_path(parts) and _reads_run_states(ctx, idx):
        return None
    depth = 3 if first == "artifacts" else 2  # artifacts/<ticket>/<run>, runs/<run>
    if len(parts) < depth or any(_WILD & set(x) for x in parts[:depth]):
        return (
            "this search also takes in other runs' files; search this run's folders "
            f"(artifacts/<ticket>/{run_id}/, runs/{run_id}/) or context/ instead"
        )
    if parts[depth - 1] == run_id:
        return None
    rel = "/".join(parts)
    return (
        f"{rel} belongs to another run. Runs are independent: use only this run's files and "
        "the inputs tsl gave, never an earlier run's artifacts, answers or questions"
    )


def _other_run_bash(cmd: str, run_id: str) -> str | None:
    """A shell command that names another run's folder (cat, grep, ls ...), or None. tsl
    commands are left to tsl, which keeps to the run it is given."""
    from tsl.harness.commands import strip_cd
    from tsl.harness.gates import OTHER_RUN

    if strip_cd(cmd).lstrip().startswith("tsl "):
        return None
    flat = cmd.replace("\\", "/")
    for m in OTHER_RUN.finditer(flat):
        if m.group(2) != run_id:
            return (
                f"{m.group(1)} belongs to another run. Runs are independent: use only this run's "
                "files and the inputs tsl gave"
            )
    # The folders that hold every run: artifacts/, artifacts/<ticket>/, runs/, or a wildcard there.
    if re.search(r"(?<![\w.-])(artifacts/([^/\s'\"]+/?)?|runs/)(\*|['\"]?(\s|$))", flat):
        return "this command takes in other runs' files; name this run's folders instead"
    return None


def is_run_state_path(parts: list[str]) -> bool:
    """runs/<run>/state.json, the run id possibly a wildcard (Glob runs/*/state.json)."""
    return len(parts) == 3 and parts[0] == "runs" and parts[2] == "state.json"


def _reads_run_states(ctx: Ctx, idx: dict[str, Any]) -> bool:
    """Whether the run's current step is a skill that reads run states (status-report)."""
    step = (idx["_state"].get("cursor") or {}).get("step")
    if not step:
        return False
    try:
        from tsl.core.repo import Companion
        from tsl.orchestrator.run import RunCtx
        from tsl.orchestrator.skills import reads_run_states

        run = RunCtx(ctx.rt, Companion(Path(idx["companion"])), idx["run_id"])
        return reads_run_states(run.skill_for(str(step)).meta)
    except Exception:
        return False


def _try_bind(ctx: Ctx) -> dict[str, Any] | None:
    """U-06 fallback: bind a lock this user created in the last 10 minutes (SDD-04 §6.14)."""
    cwd = Path(str(ctx.data.get("cwd") or "."))
    root = None
    for p in (cwd, *cwd.parents):
        if (p / "tsl.yaml").is_file():
            root = p
            break
    if root is None or not (root / "runs" / "active").is_dir() or not ctx.session_id:
        return None
    now = time.time()
    recent = [
        p
        for p in (root / "runs" / "active").glob("*.lock")
        if now - p.stat().st_mtime < BIND_WINDOW_S
    ]
    if not recent:
        return None
    me_p = ctx.home / "cache" / "me.json"
    me = json.loads(me_p.read_text(encoding="utf-8")) if me_p.is_file() else {}
    for lp in sorted(recent):
        lk = json.loads(lp.read_text(encoding="utf-8"))
        st_p = root / "runs" / lk["run_id"] / "state.json"
        if lk.get("holder") != me.get("pseudonym") or not st_p.is_file():
            continue
        st = json.loads(st_p.read_text(encoding="utf-8"))
        if st.get("active_session") or st.get("status") != "RUNNING":
            continue
        from tsl.core.repo import Companion
        from tsl.state.session import bind, compile_policy
        from tsl.state.store import RunStore

        comp = Companion(root)
        rt = ctx.rt
        bind(
            rt,
            comp,
            ctx.session_id,
            lk["run_id"],
            f"runs/active/{lp.name}",
            compile_policy(rt, comp, lk["run_id"], st["pinned"]["tsl"]),
        )

        def setsess(s: dict[str, Any]) -> None:
            s["active_session"] = {
                "session_id": ctx.session_id[:128],
                "host_hash": "h_0000",
                "since": s["updated_at"],
            }

        RunStore(rt, comp, lk["run_id"]).update(setsess)
        return active_run(ctx)
    return None


def _abs(ctx: Ctx, path: str) -> str:
    p = Path(path)
    if not p.is_absolute():
        p = Path(str(ctx.data.get("cwd") or ".")) / p
    return os.path.normpath(str(p)).replace("\\", "/")


def _allowed(target: str, pol: dict[str, Any]) -> bool:
    if any(fnmatch.fnmatch(target, d) for d in pol.get("deny", [])):
        return False
    return any(fnmatch.fnmatch(target, a) for a in pol.get("allow", []))


def _sensitive(tok: str, base: str, glob: str) -> bool:
    """A file-name glob matches the last path part; a glob with '/' matches the path tail."""
    if "/" in glob:
        return fnmatch.fnmatch(tok, glob) or fnmatch.fnmatch(tok, "*/" + glob)
    return fnmatch.fnmatch(base, glob)


def handle(ctx: Ctx) -> tuple[str, int]:
    if ctx.tool.startswith("mcp__"):
        return allow(ctx)  # pre-mcp decides MCP tools
    idx = None
    try:
        idx = active_run(ctx)
        if idx is None and not ctx.session_file().is_file():
            idx = _try_bind(ctx)
    except Exception:
        idx = None
    if _is_reviewer(ctx) and ctx.tool in WRITE_TOOLS:
        why = _reviewer_write_refused(ctx, idx)
        if why is not None:
            # Refused before it runs and not written to the tool log, so H7 has nothing to
            # fail: the reviewer then hands its JSON back instead (SDD-05 §4.3).
            return deny(ctx, "E-POL-06", f"Refused: {why}")
    if idx is None:
        return allow(ctx)  # outside a run: static rules come from managed settings
    try:
        pol = policy_for(ctx, idx)
        if not version_ok(str(pol.get("pinned_tsl", idx["_state"]["pinned"]["tsl"]))):
            log_tool(idx, ctx, ctx.tool, "deny", "E-VER-01")
            return deny(
                ctx, "E-VER-01", "tsl version does not match the run pin; install the pinned tsl"
            )
        ti = ctx.data.get("tool_input") or {}
        open_step = _open_step(ctx, idx)
        if open_step is not None:
            why = _off_step(ctx, str(ti.get("command") or ""), open_step)
            if why is not None:
                # Refused before it runs and not written to the tool log: nothing happened,
                # so H7 has nothing to fail. hook.log still records the refusal.
                return deny(ctx, "E-POL-06", f"Refused: {why}. Carry on with the step's tools")
        _record_ask(ctx, idx, ti)
        if ctx.tool in READ_TOOLS:
            # While this session holds a run, in a step or between steps (HMS-5: the run loop
            # read the earlier run "as a starting point" before each step).
            why = _other_run_read(ctx, idx, ti)
            if why is not None:
                return deny(ctx, "E-POL-06", f"Refused: {why}")
        if ctx.tool == "Bash":
            why = _other_run_bash(str(ti.get("command") or ""), str(idx["run_id"]))
            if why is not None:
                return deny(ctx, "E-POL-06", f"Refused: {why}")
        if ctx.tool not in LOGGED:
            return allow(ctx)
        if ctx.tool in ("Write", "Edit", "NotebookEdit"):
            raw = str(ti.get("file_path") or ti.get("notebook_path") or "")
            target = _abs(ctx, raw)
            for pat, why in TSL_ONLY.items():
                if fnmatch.fnmatch(target, pat):
                    # Only the hooks record the user's IDE questions and answers.
                    log_tool(idx, ctx, target, "deny", "E-POL-01")
                    return deny(ctx, "E-POL-01", f"Blocked: {why}")
            if not raw or not _allowed(target, pol):
                log_tool(idx, ctx, target, "deny", "E-POL-01")
                return deny(ctx, "E-POL-01", f"Blocked: write outside allowed paths {target}")
            log_tool(idx, ctx, target, "allow", None)
            return allow(ctx)
        if ctx.tool == "Bash":
            cmd = str(ti.get("command") or "")
            for pat in pol.get("bash_deny", []):
                if pat in cmd:
                    log_tool(idx, ctx, cmd[:80], "deny", "E-POL-01")
                    return deny(
                        ctx,
                        "E-POL-01",
                        f"Blocked: '{pat}' is not allowed inside a run (tsl pr does pushes)",
                    )
            for tok in cmd.split():
                tok = tok.strip("'\"")
                base = tok.rsplit("/", 1)[-1]
                if any(_sensitive(tok, base, g) for g in pol.get("read_deny", [])):
                    log_tool(idx, ctx, cmd[:80], "deny", "E-POL-02")
                    return deny(ctx, "E-POL-02", f"Blocked: read of sensitive file {base}")
            from tsl.harness.commands import is_read_only, strip_cd

            log_tool(idx, ctx, strip_cd(cmd)[:80], "allow", None, read_only=is_read_only(cmd))
            return allow(ctx)
        return allow(ctx)
    except Exception:
        return deny(
            ctx,
            "E-HOOK-01",
            "Write blocked: tsl did not answer while a run is active. Run tsl doctor",
        )
