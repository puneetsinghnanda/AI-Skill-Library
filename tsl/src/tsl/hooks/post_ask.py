"""post-ask: record the user's AskUserQuestion answers for the open step (ide-answers.md).

Reached through the PostToolUse `post-write` event (matcher includes AskUserQuestion), so the
launcher's fail-open rule applies: a failure never blocks the session. A missed record is
caught later by the `answers.logged` skill check, which fails an artifact whose answers are
not in the log.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from tsl.hooks.dispatch import Ctx, _finish, _now, active_run


def _answered_by(companion: Path) -> str:
    def cfg(key: str) -> str:
        try:
            cp = subprocess.run(
                ["git", "-C", str(companion), "config", "--get", key],
                capture_output=True,
                text=True,
                timeout=3,
            )
            return cp.stdout.strip()
        except (OSError, subprocess.SubprocessError):
            return ""

    name, email = cfg("user.name"), cfg("user.email")
    if name and email:
        return f"{name} <{email}>"
    return name or email or "unknown"


def _items(data: dict[str, Any]) -> list[dict[str, Any]]:
    ti = data.get("tool_input") or {}
    tr = data.get("tool_response")
    answers = ti.get("answers") or (tr.get("answers") if isinstance(tr, dict) else None) or {}
    notes = ti.get("annotations") or (tr.get("annotations") if isinstance(tr, dict) else None) or {}
    out = []
    for q in ti.get("questions") or []:
        text = str(q.get("question") or "")
        ans = answers.get(text) if isinstance(answers, dict) else None
        if ans is None or str(ans).strip() == "":
            continue  # skipped: the step falls back to open-questions.md for this one
        if isinstance(ans, list):
            ans = ", ".join(str(a) for a in ans)
        note = (notes.get(text) or {}).get("notes") if isinstance(notes, dict) else None
        if note:
            ans = f"{ans} (notes: {note})"
        opts = [str(o.get("label") or "") for o in q.get("options") or [] if isinstance(o, dict)]
        out.append({"question": text, "options": opts, "answer": ans})
    return out


def handle(ctx: Ctx) -> tuple[str, int]:
    try:
        idx = active_run(ctx)
        if idx is None:
            return _finish(ctx, None)  # outside a run: nothing to record
        st = idx["_state"]
        cur = st.get("cursor") or {}
        if not cur.get("step"):
            return _finish(ctx, None)
        items = _items(ctx.data)
        if not items:
            return _finish(ctx, None)
        from tsl.approvals import ide_answers
        from tsl.core.paths import ide_answers_path

        companion = Path(idx["companion"])
        rel = ide_answers_path(idx["run_id"])
        ids = ide_answers.append(
            companion / rel,
            idx["run_id"],
            str(cur["step"]),
            int(cur.get("attempt") or 1),
            _now(),
            _answered_by(companion),
            str(ctx.data.get("tool_use_id") or ""),
            items,
        )
        ctx.decision, ctx.code = "allow", None
        lines = [
            f"{aid}: {it['question'][:120]} -> {it['answer'][:120]}"
            for aid, it in zip(ids, items, strict=True)
        ]
        msg = (
            f"tsl recorded the user's answers in {rel}. Cite each as {rel}#<a-nn> "
            "(lower-case heading anchor) and list it under answers in the artifact:\n"
            + "\n".join(lines)
        )
        return _finish(
            ctx,
            {
                "hookSpecificOutput": {
                    "hookEventName": "PostToolUse",
                    "additionalContext": msg[:4000],
                }
            },
        )
    except Exception as exc:  # fail open: the answers.logged check catches a missing record
        code = getattr(exc, "code", "E-INT-01")
        ctx.decision, ctx.code = "allow", code if str(code).startswith("E-") else "E-INT-01"
        return _finish(
            ctx,
            {
                "systemMessage": f"tsl could not record the IDE answers ({ctx.code}). "
                "Ask again or let the step pause for input. Run tsl doctor."
            },
        )
