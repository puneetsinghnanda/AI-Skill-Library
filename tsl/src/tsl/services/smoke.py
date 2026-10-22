"""tsl smoke: a complete run with canned content and no AI, against the real setup (hardening).

It proves the plumbing in a few minutes: sign-in and grants on the service, the lock pushed to the
companion's GitHub remote, the ticket snapshot, the write hooks, every harness check, the review
record, the signed decision, events reaching the portal, and cancelling. When it passes, a failure
in a real run is about the skill's output, not the setup. It needs no second person: it stops
before any approval gate and cancels the run, which the portal then shows as Cancelled.
"""

from __future__ import annotations

import contextlib
import dataclasses
import io
import json
import sys
import tempfile
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import yaml

from tsl.core.errors import TslError
from tsl.core.runtime import Runtime, use_runtime

WORKFLOW = "brownfield-change"
TICKET_LINES = [
    "# {ticket} Smoke test of the run plumbing",
    "",
    "The smoke ticket asks for a heading on the front page.",
    "This ticket is created and cancelled by tsl smoke; it changes no code.",
]
SECTIONS = [
    "Summary",
    "Requirements",
    "Known",
    "Assumed",
    "Unknown",
    "Open questions",
    "Out of scope",
]


@dataclasses.dataclass
class Step:
    name: str
    ok: bool
    detail: str = ""


@contextlib.contextmanager
def _saved_cli_state() -> Iterator[None]:
    """Nested CLI calls share module globals with the outer `tsl smoke`; put them back after."""
    from tsl.cli import commands

    forced = dict(commands.FORCED)
    opts = {k: getattr(commands.OPTS, k) for k in ("json", "repo", "verbose", "color")}
    try:
        yield
    finally:
        commands.FORCED.clear()
        commands.FORCED.update(forced)
        for k, v in opts.items():
            setattr(commands.OPTS, k, v)


def _cli(rt: Runtime, root: Path, args: list[str], stdin: str = "") -> tuple[int, dict[str, Any]]:
    from tsl.cli.app import run_cli

    out = io.StringIO()
    old_in = sys.stdin
    sys.stdin = io.StringIO(stdin)
    try:
        with (
            _saved_cli_state(),
            use_runtime(rt),
            contextlib.redirect_stdout(out),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            code = run_cli(["--repo", str(root), *args, "--json"])
    finally:
        sys.stdin = old_in
    lines = [x for x in out.getvalue().splitlines() if x.strip().startswith("{")]
    env: dict[str, Any] = json.loads(lines[-1]) if lines else {}
    return code, env


def _hook(rt: Runtime, root: Path, event: str, payload: dict[str, Any]) -> tuple[str, int]:
    from tsl.hooks.dispatch import run as run_hook

    data = {"session_id": rt.session_id(), "cwd": str(root), **payload}
    return run_hook(event, json.dumps(data), env=rt.env, home=rt.home.root, rt_factory=lambda: rt)


def _line_of(text: str, needle: str) -> int:
    for i, line in enumerate(text.splitlines(), start=1):
        if needle in line:
            return i
    raise TslError("E-INT-01", f"smoke: '{needle}' not in the ticket snapshot", log_id="smoke")


def _artifact(envelope: dict[str, Any], ticket_rel: str, ticket_text: str) -> str:
    cite = f"{ticket_rel}#L{_line_of(ticket_text, 'heading on the front page')}"
    fm: dict[str, Any] = dict(envelope)
    fm.update(
        {
            "claims": [{"id": "C1", "text": "The ticket asks for a heading", "cites": [cite]}],
            "trace": ["REQ-1"],
            "known": ["REQ-1"],
            "assumed": [],
            "unknown": [],
            "requirements": [
                {
                    "id": "REQ-1",
                    "title": "Front page heading",
                    "type": "functional",
                    "status": "known",
                    "statement": "The front page shows a heading.",
                    "cites": [cite],
                }
            ],
            "unknowns": [],
            "questions": [],
            "glossary": [],
        }
    )
    body = {
        "Summary": "The smoke ticket asks for a heading on the front page.",
        "Requirements": "REQ-1 front page heading.",
        "Known": "REQ-1 from the ticket.",
        "Assumed": "None.",
        "Unknown": "None.",
        "Open questions": "None.",
        "Out of scope": "Everything else.",
    }
    text = "# Requirements review\n\n" + "\n".join(f"## {s}\n{body[s]}\n" for s in SECTIONS)
    return "---\n" + yaml.safe_dump(fm, sort_keys=False) + "---\n\n" + text


def _review(package: dict[str, Any], plugin_version: str) -> str:
    items = package["rubric"]["items"]
    obj = {
        "schema": "review.v1",
        "run_id": package["run_id"],
        "step": package["step"],
        "attempt": package["attempt"],
        "artifact_sha256": package["artifact_sha256"],
        "package_sha256": package["package_sha256"],
        "status": "ok",
        "reviewer": {
            "agent": "truminds:reviewer",
            "skill": "review",
            "version": plugin_version,
            "rubric_sha256": package["rubric"]["sha256"],
        },
        "rubric_score": 5.0,
        "rubric_items": [{"id": i["id"], "score": 5, "reason": "smoke"} for i in items],
        "findings": [],
        "claims_checked": [{"claim_id": "C1", "verdict": "supported"}],
        "questions": [],
    }
    return "```json\n" + json.dumps(obj) + "\n```\n"


def smoke(
    rt: Runtime, root: Path, progress: Callable[[str], object] = lambda _s: None
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    from tsl.services.doctor import _run_checks

    steps: list[Step] = []

    def done(name: str, ok: bool, detail: str = "") -> None:
        steps.append(Step(name, ok, detail))
        progress(f"{'✔' if ok else '✖'} {name}" + (f": {detail}" if detail else ""))

    def fail(name: str, env: dict[str, Any]) -> TslError:
        done(name, False, f"{env.get('code')} {env.get('message', '')}".strip())
        return TslError(
            "E-SMOKE-01",
            step=name,
            detail=f"{env.get('code')} {env.get('message', '')}"[:200],
            next=str(env.get("next") or "tsl doctor --run"),
            data={"steps": [dataclasses.asdict(s) for s in steps]},
        )

    # The smoke run stops before code steps, so it needs no Docker (doctor --run still checks it).
    blocking = [
        c for c in _run_checks(rt, root) if c["status"] == "fail" and c["id"] != "docker-running"
    ]
    if blocking:
        c = blocking[0]
        raise TslError("E-ENV-01", item=c["id"], next=c["fix"] or "tsl doctor --run")
    done("pre-flight", True, "tsl doctor --run checks passed")

    ticket = f"SMOKE-{int(rt.clock().timestamp())}"
    srt = dataclasses.replace(rt, env={**rt.env, "TSL_SESSION_ID": f"smoke-{ticket.lower()}"})
    with tempfile.TemporaryDirectory() as tmp:
        tf = Path(tmp) / f"{ticket}.md"
        tf.write_text("\n".join(TICKET_LINES).format(ticket=ticket) + "\n", encoding="utf-8")
        code, env = _cli(srt, root, ["state", "start", WORKFLOW, ticket, "--ticket-file", str(tf)])
    if code != 0:
        raise fail("start run", env)
    run_id = str(env["data"]["run_id"])
    ticket_rel = str(env["data"]["ticket_snapshot"])
    done("start run", True, f"{run_id}, lock pushed, ticket snapshot written")
    try:
        code, env = _cli(srt, root, ["next", run_id])
        if code != 0 or env.get("data", {}).get("action") != "run_skill":
            raise fail("first step", env)
        art = str(env["data"]["artifact_path"])
        code, inp = _cli(srt, root, ["verify", art, "--inputs"])
        if code != 0:
            raise fail("step inputs", inp)
        done("first step", True, f"{env['data']['step']} -> {art}")

        target = str(root / art)
        out, _ = _hook(
            srt,
            root,
            "pre-tool",
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "Write",
                "tool_input": {"file_path": target, "content": "..."},
            },
        )
        if out:
            raise fail("write hook", {"code": "E-POL", "message": out[:200]})
        ticket_text = (root / ticket_rel).read_text(encoding="utf-8")
        p = root / art
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(_artifact(inp["data"]["envelope"], ticket_rel, ticket_text), encoding="utf-8")
        out, _ = _hook(
            srt,
            root,
            "post-write",
            {
                "hook_event_name": "PostToolUse",
                "tool_name": "Write",
                "tool_input": {"file_path": target},
            },
        )
        if out:
            raise fail("harness checks", {"code": "BLOCK", "message": out[:200]})
        done("harness checks", True, "write allowed, post-write checks passed")

        code, env = _cli(srt, root, ["review", "prepare", art])
        if code != 0:
            raise fail("review", env)
        package = json.loads((root / str(env["data"]["package_path"])).read_text(encoding="utf-8"))
        state = json.loads((root / "runs" / run_id / "state.json").read_text(encoding="utf-8"))
        review = _review(package, str(state["pinned"]["plugin"]))
        code, env = _cli(srt, root, ["review", "record", art], stdin=review)
        if code != 0:
            raise fail("review", env)
        done("review", True, "package prepared, review recorded")

        code, env = _cli(srt, root, ["decide", art])
        outcome = (env.get("data") or {}).get("outcome")
        if not outcome:  # any outcome (pass, retry, escalate) proves the chain; an error does not
            raise fail("decide", env)
        done("decide", True, f"signed decision: {outcome}")
    finally:
        code, env = _cli(srt, root, ["state", "cancel", run_id, "--reason", "tsl smoke"])
        done(
            "cancel",
            code == 0,
            "run cancelled, lock released" if code == 0 else str(env.get("message")),
        )
    from tsl.telemetry.emit import flush

    flush(rt, max_seconds=20)
    # The run's own events are what make it appear in the portal.
    queued = [e for e in rt.outbox().events() if e["run_id"] == run_id and e["status"] != "sent"]
    done(
        "portal",
        not queued,
        f"events sent; the portal shows {run_id} as Cancelled"
        if not queued
        else f"{len(queued)} events still queued; open the portal, then run tsl events flush",
    )
    data = {"run_id": run_id, "ticket": ticket, "steps": [dataclasses.asdict(s) for s in steps]}
    return data, []
