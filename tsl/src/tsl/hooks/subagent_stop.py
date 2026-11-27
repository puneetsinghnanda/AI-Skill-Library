"""subagent-stop: a subagent ended, so an IDE question it left open is gone (roadmap B2).

A subagent whose AskUserQuestion dialog was dismissed (Esc) and that then ends never makes
another tool call, so the pre-tool hook never closes its ask, and its wait would grow until the
run ends. This closes that agent's open asks when it stops. Never blocks, prints nothing; it
writes one hook.log line and no hook.decision event (the event's hook enum has no
subagent-stop, and an event the service rejects goes dead).
"""

from __future__ import annotations

from pathlib import Path

from tsl.hooks.dispatch import Ctx, _finish, active_run


def handle(ctx: Ctx) -> tuple[str, int]:
    idx = None
    try:
        agent = str(ctx.data.get("agent_id") or "")
        idx = active_run(ctx) if agent else None
        if idx is not None:
            from tsl.approvals import ide_questions

            ide_questions.close_open(
                Path(idx["companion"]), str(idx["run_id"]), reason="dismissed", agent_id=agent
            )
    except Exception as exc:  # never blocks: a missed close is noted for tsl doctor
        if idx is not None:
            from tsl.approvals import ide_questions

            ide_questions.note_failure(ctx.home, str(idx["run_id"]), "subagent-stop", exc)
    return _finish(ctx, None)
