"""The tsl command tree (SDD-04 §6). Each command calls one service and prints one envelope."""

from __future__ import annotations

import functools
import os
import sys
import traceback
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Any

import typer

from tsl.core.envelope import human, make
from tsl.core.errors import CATALOGUE, TslError, render

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    pretty_exceptions_enable=False,
    help="tsl: Truminds Skill Library command-line tool. Code decides; the model proposes.",
)
keys_app = typer.Typer(no_args_is_help=True, help="Signing keys (SDD-07 §5.5).")
state_app = typer.Typer(no_args_is_help=True, help="Run state (SDD-02).")
review_app = typer.Typer(no_args_is_help=True, help="Reviewer package and record (SDD-03 §7).")
context_app = typer.Typer(no_args_is_help=True, help="Context pack (SDD-06).")
eval_app = typer.Typer(no_args_is_help=True, help="Skill evals (SDD-01 §10).")
improve_app = typer.Typer(no_args_is_help=True, help="Improvement loop (SDD-11).")
events_app = typer.Typer(no_args_is_help=True, help="Telemetry outbox (SDD-04 §8).")
harness_app = typer.Typer(no_args_is_help=True, help="Harness accuracy (SDD-03 §16).")
companion_app = typer.Typer(no_args_is_help=True, help="Companion repo CI and archive (SDD-12).")
for name, sub in (
    ("keys", keys_app),
    ("state", state_app),
    ("review", review_app),
    ("context", context_app),
    ("eval", eval_app),
    ("improve", improve_app),
    ("events", events_app),
    ("harness", harness_app),
    ("companion", companion_app),
):
    app.add_typer(sub, name=name)


class Opts:
    json: bool = False
    repo: Path | None = None
    verbose: int = 0
    color: bool = True


OPTS = Opts()
FORCED: dict[str, Any] = {"json": False, "no_color": False, "verbose": 0}


def _version(v: bool) -> None:
    if v:
        from tsl import __version__

        sys.stdout.write(f"tsl {__version__}\n")
        raise typer.Exit(0)


@app.callback()
def root(
    json_: Annotated[
        bool, typer.Option("--json", help="Envelope on stdout; human text on stderr")
    ] = False,
    repo: Annotated[Path | None, typer.Option("--repo", help="Companion repo root")] = None,
    verbose: Annotated[int, typer.Option("-v", count=True, help="-v info, -vv debug")] = 0,
    no_color: Annotated[bool, typer.Option("--no-color")] = False,
    version: Annotated[bool, typer.Option("--version", callback=_version, is_eager=True)] = False,
) -> None:
    OPTS.json = json_ or bool(FORCED["json"])
    OPTS.repo = repo
    OPTS.verbose = verbose or int(FORCED["verbose"])
    no_color = no_color or bool(FORCED["no_color"])
    OPTS.color = not no_color and not os.environ.get("NO_COLOR") and sys.stderr.isatty()


def _print(env_json: str, text: str) -> None:
    if OPTS.json:
        sys.stdout.write(env_json + "\n")
        sys.stderr.write(text + "\n")
    else:
        sys.stdout.write(text + "\n")


def _flush_stderr() -> None:
    from tsl.core.runtime import _current

    if _current is not None and _current.stderr_lines:
        for line in _current.stderr_lines:
            sys.stderr.write(line + "\n")
        _current.stderr_lines.clear()


def emit_ok(
    message: str,
    data: dict[str, Any],
    warnings: list[dict[str, str]] | None = None,
    next_: str | None = None,
) -> int:
    env = make("OK", 0, message, next_, data, warnings)
    _flush_stderr()
    _print(env.to_json(), human(env, OPTS.color))
    return 0


def emit_err(
    code: str,
    message: str,
    next_: str | None,
    data: dict[str, Any] | None,
    warnings: list[dict[str, str]] | None = None,
    exit_: int | None = None,
) -> int:
    d = CATALOGUE[code]
    ex = d.exit if exit_ is None else exit_
    env = make(code, ex, message, next_, data, warnings)
    _flush_stderr()
    _print(env.to_json(), human(env, OPTS.color))
    return ex


def render_error(code: str, message: str, as_json: bool, args: list[str]) -> int:
    OPTS.json = as_json
    cmd = next((a for a in args if not a.startswith("-")), "")
    return emit_err(
        code,
        render(CATALOGUE[code].message, detail=message.strip()[:200]),
        render(CATALOGUE[code].next, cmd=cmd),
        {},
    )


def _log_internal(exc: BaseException) -> str:
    from tsl.core.clock import iso, system_clock
    from tsl.core.ids import IdFactory
    from tsl.core.log import append_line

    log_id = IdFactory(system_clock).ulid()[-10:]
    try:
        from tsl.core.runtime import get_runtime

        home = get_runtime().home.logs
    except Exception:
        home = Path.home() / ".truminds" / "logs"
    append_line(
        home / "tsl.log",
        {
            "ts": iso(system_clock()),
            "level": "error",
            "log_id": log_id,
            "cmd": " ".join(sys.argv[1:3]),
            "code": "E-INT-01",
            "msg": "".join(traceback.format_exception(exc))[-4000:],
        },
    )
    return log_id


# Commands that change a run's status: their events are sent right away, not only at session end.
SENDS_EVENTS = {
    "state_start",
    "state_resume",
    "state_cancel",
    "state_unlock",
    "decide",
    "approve",
    "pr",
    "pr_sync",
}


def command(fn: Callable[..., int]) -> Callable[..., None]:
    """Run a command body; map TslError to its envelope and anything else to E-INT-01."""

    @functools.wraps(fn)
    def wrapper(*a: Any, **kw: Any) -> None:
        try:
            try:
                code = fn(*a, **kw)
            finally:
                if fn.__name__ in SENDS_EVENTS:
                    from tsl.telemetry.emit import send_soon

                    send_soon(rt)
        except TslError as e:
            code = emit_err(e.code, e.message, e.next, e.data, exit_=e.exit)
        except typer.Exit:
            raise
        except Exception as exc:  # never a stack trace on stdout (SDD-04 §4)
            log_id = _log_internal(exc)
            code = emit_err(
                "E-INT-01",
                render(CATALOGUE["E-INT-01"].message, log_id=log_id),
                render(CATALOGUE["E-INT-01"].next, log_id=log_id),
                {"log_id": log_id},
            )
        raise typer.Exit(code)

    return wrapper


def rt() -> Any:
    from tsl.core.runtime import get_runtime

    return get_runtime()


def comp() -> Any:
    from tsl.core.repo import Companion

    c = Companion.discover(OPTS.repo)
    _ = c.config
    return c


# ------------------------------------------------------------------------------- identity
@app.command()
@command
def login(rotate_key: Annotated[bool, typer.Option("--rotate-key")] = False) -> int:
    """Sign in with a device code (Entra ID, or GitHub in the test phase); register this key."""
    from tsl.services.identity_cmds import login as svc

    data = svc(rt(), rotate_key)
    return emit_ok(f"Logged in as {data['pseudonym']}, key {data['key_id']}", data)


@app.command()
@command
def logout(revoke_key: Annotated[bool, typer.Option("--revoke-key")] = False) -> int:
    """Delete the token cache; with --revoke-key also revoke and delete this device's key."""
    from tsl.services.identity_cmds import logout as svc

    return emit_ok("Logged out", svc(rt(), revoke_key))


@app.command()
@command
def whoami(refresh: Annotated[bool, typer.Option("--refresh")] = False) -> int:
    """Show who you are, your role grants and your key status."""
    from tsl.services.identity_cmds import whoami as svc

    data = svc(rt(), refresh)
    return emit_ok(f"{data['pseudonym']} (key {data['key_status']})", data)


@keys_app.command("list")
@command
def keys_list() -> int:
    """List your registered keys."""
    from tsl.services.identity_cmds import keys_list as svc

    return emit_ok("Keys", svc(rt()))


@keys_app.command("rotate")
@command
def keys_rotate() -> int:
    """Create a new key; the old one is revoked as replaced."""
    from tsl.services.identity_cmds import keys_rotate as svc

    data = svc(rt())
    return emit_ok(f"New key {data['key_id']}", data)


@keys_app.command("revoke")
@command
def keys_revoke(
    key_id: str,
    compromised_since: Annotated[str | None, typer.Option("--compromised-since")] = None,
) -> int:
    """Revoke one of your keys."""
    from tsl.services.identity_cmds import keys_revoke as svc

    return emit_ok(f"Revoked {key_id}", svc(rt(), key_id, compromised_since))


# ------------------------------------------------------------------------------- setup
@app.command()
@command
def doctor(
    plugin_version: Annotated[str | None, typer.Option("--plugin-version")] = None,
    run: Annotated[
        bool,
        typer.Option("--run", help="Also check, live, that a run can start or resume from here"),
    ] = False,
) -> int:
    """Check prerequisites, login, key, service, outbox and the companion repo."""
    from tsl.services.doctor import doctor as svc

    data, warnings = svc(rt(), plugin_version, OPTS.repo or Path.cwd(), run)
    return emit_ok("All checks passed", data, warnings)


@app.command()
@command
def smoke() -> int:
    """Run a whole workflow with canned content and no AI, to prove the setup end to end."""
    from tsl.services.smoke import smoke as svc

    data, warnings = svc(rt(), comp().root, progress=lambda line: sys.stderr.write(line + "\n"))
    return emit_ok(
        f"Smoke run passed: {data['run_id']} started, decided and cancelled", data, warnings
    )


@app.command()
@command
def init(
    system: Annotated[str, typer.Option("--system")],
    product_repo: Annotated[list[str], typer.Option("--product-repo")],
    clone_dir: Annotated[Path | None, typer.Option("--clone-dir")] = None,
) -> int:
    """Set up an empty companion repo for a system (tech lead)."""
    from tsl.services.init import init as svc

    data, warnings = svc(rt(), system, product_repo, clone_dir)
    return emit_ok("Companion repo initialised", data, warnings, "tsl context build")


@app.command()
@command
def validate(paths: list[Path], lock: Annotated[bool, typer.Option("--lock")] = False) -> int:
    """Validate skills, workflows, policy, tsl.yaml or the whole plugin."""
    from tsl.services.validate import validate as svc

    data, code = svc(rt(), paths, lock)
    if code is None:
        return emit_ok(f"{len(data['results'])} item(s) valid", data)
    bad = next(r for r in data["results"] if not r["ok"])
    e = bad["errors"][0]
    msg = f"{bad['path']}: {e['pointer']} {e['message']}"
    return emit_err(code, msg[:300], "Fix the file and run tsl validate again", data, exit_=2)


# ------------------------------------------------------------------------------- harness
@app.command()
@command
def verify(
    artifact: Annotated[str | None, typer.Argument()] = None,
    inputs: Annotated[bool, typer.Option("--inputs")] = False,
    run: Annotated[str | None, typer.Option("--run")] = None,
    step: Annotated[str | None, typer.Option("--step")] = None,
    fast: Annotated[bool, typer.Option("--fast")] = False,
    gates: Annotated[str | None, typer.Option("--gates")] = None,
    detach: Annotated[bool, typer.Option("--detach")] = False,
    status: Annotated[bool, typer.Option("--status")] = False,
    ci: Annotated[bool, typer.Option("--ci")] = False,
) -> int:
    """Run the code checks H1-H7 on an artifact, or check a step's inputs with --inputs."""
    from tsl.harness import verify as svc

    c = comp()
    if inputs:
        data = svc.verify_inputs(rt(), c, run, step, artifact)
        return emit_ok(
            "inputs ready", data, c.warnings, f"write the artifact to {data['artifact_path']}"
        )
    if artifact is None:
        raise TslError("E-USE-01", detail="artifact path required", cmd="verify")
    if status:
        return emit_ok("H3 status", svc.h3_status(rt(), c, artifact))
    if detach:
        return emit_ok(
            "Verifier started in the background",
            svc.detach_h3(rt(), c, artifact),
            next_=f"tsl verify {artifact} --status",
        )
    only = [g.strip() for g in gates.split(",")] if gates else None
    data = svc.verify_artifact(rt(), c, artifact, fast=fast, only=only)
    return emit_ok("All hard gates pass", data, c.warnings)


@app.command()
@command
def decide(artifact: str) -> int:
    """Verify citations, compute signals, band and outcome, and sign the check record."""
    from tsl.harness.decide_service import decide as svc

    data, d, warnings = svc(rt(), comp(), artifact)
    run_id = data["verification_path"].split("/")[2]
    o = d.outcome
    if o in ("PASS", "PASS-WITH-FINDINGS"):
        return emit_ok(f"Step passed [{o} · {d.band}]", data, warnings, "continue")
    if o == "RETRY":
        why = ", ".join(d.gate_failures) or (
            "major findings" if d.budget_kind == "review" else "checks"
        )
        return emit_err(
            "E-CHK-01", f"Step needs a retry: {why}", "retry with feedback", data, warnings
        )
    if o == "NEEDS-INPUT":
        return emit_err(
            "E-RUN-01",
            f"Run paused for input: {d.signals['S4']} blocking question(s)",
            f"/truminds:resume {run_id} after answering",
            data,
            warnings,
        )
    if o == "ESCALATE":
        return emit_err(
            "E-RUN-02",
            f"Run paused for approval: {d.escalate_reason}",
            f"approver runs tsl approve {run_id} {data['gate']}",
            data,
            warnings,
        )
    code = next((c for c in d.codes if c.startswith(("E-SEC", "E-POL"))), "E-POL-05")
    return emit_err(code, f"Run aborted: {code}", "stopped", data, warnings)


@review_app.command("prepare")
@command
def review_prepare(artifact: str) -> int:
    """Build the review package for the forked reviewer."""
    from tsl.review.service import prepare

    data = prepare(rt(), comp(), artifact)
    if not OPTS.json:
        sys.stdout.write(data["package"] + "\n")
        return 0
    return emit_ok("Review package ready", data)


@review_app.command("record")
@command
def review_record(
    artifact: str,
    file: Annotated[Path | None, typer.Option("--file")] = None,
    unavailable: Annotated[str | None, typer.Option("--unavailable")] = None,
) -> int:
    """Store the reviewer's review.v1 JSON (stdin by default)."""
    from tsl.review.service import record

    text = None
    if unavailable is None:
        text = file.read_text(encoding="utf-8") if file else sys.stdin.read()
    data, warnings = record(rt(), comp(), artifact, text, unavailable)
    return emit_ok("Review recorded", data, warnings)


# ------------------------------------------------------------------------------- runs
@state_app.command("start")
@command
def state_start(
    workflow: str,
    ticket: str,
    system: Annotated[str | None, typer.Option("--system")] = None,
    pod: Annotated[str | None, typer.Option("--pod")] = None,
    ticket_file: Annotated[
        str | None,
        typer.Option("--ticket-file", help="Ticket text (Markdown) to snapshot as ticket.md"),
    ] = None,
) -> int:
    """Start a run: take the lock, write state.json, the workflow snapshot and ticket.md."""
    from tsl.state.service import start

    data, warnings = start(rt(), comp(), workflow, ticket, system, pod, ticket_file or None)
    return emit_ok(f"Run {data['run_id']} started", data, warnings, f"tsl next {data['run_id']}")


@state_app.command("resume")
@command
def state_resume(
    run_id: str, take_over: Annotated[bool, typer.Option("--take-over")] = False
) -> int:
    """Resume a paused run after answers or a signed approval."""
    from tsl.state.service import resume

    data, warnings = resume(rt(), comp(), run_id, take_over)
    return emit_ok(f"Run {run_id} is {data['status']}", data, warnings, f"tsl next {run_id}")


@state_app.command("show")
@command
def state_show(
    run_id: Annotated[str | None, typer.Argument()] = None,
    all_: Annotated[bool, typer.Option("--all")] = False,
) -> int:
    """Show runs in this companion repo."""
    from tsl.state.service import show

    data = show(rt(), comp(), run_id, all_)
    return emit_ok(f"{len(data['runs'])} run(s)", data)


@state_app.command("unlock")
@command
def state_unlock(
    ticket: str, workflow: str, reason: Annotated[str, typer.Option("--reason")]
) -> int:
    """Release a stale lock (tech lead)."""
    from tsl.state.service import unlock

    return emit_ok("Lock released", unlock(rt(), comp(), ticket, workflow, reason))


@state_app.command("cancel")
@command
def state_cancel(run_id: str, reason: Annotated[str, typer.Option("--reason")]) -> int:
    """Cancel a run (owner or tech lead)."""
    from tsl.state.service import cancel

    return emit_ok(f"Run {run_id} cancelled", cancel(rt(), comp(), run_id, reason))


@state_app.command("repair")
@command
def state_repair(run_id: str) -> int:
    """Rebuild state.json from the snapshot and the signed records."""
    from tsl.state.service import repair

    return emit_ok(f"State of {run_id} rebuilt", repair(rt(), comp(), run_id))


@state_app.command("repin")
@command
def state_repin(run_id: str) -> int:
    """Pin the installed skill versions after a plugin upgrade."""
    from tsl.state.service import repin

    return emit_ok(f"Run {run_id} repinned", repin(rt(), comp(), run_id))


@app.command("next")
@command
def next_(run_id: str) -> int:
    """Name the single next action of a run."""
    from tsl.orchestrator.next import next_action

    data, instruction = next_action(rt(), comp(), run_id)
    msg = {
        "run_skill": f"Step {data.get('step')} ({data.get('progress', {}).get('index')}/"
        f"{data.get('progress', {}).get('total')})",
        "run_decide": f"Decide step {data.get('step')}",
        "open_pr": "Open the pull request",
        "done": "Run complete",
        "stopped": "Run stopped",
    }.get(data["action"], data["action"])
    return emit_ok(msg, data, next_=instruction)


@app.command()
@command
def approve(run_id: str, gate: str) -> int:
    """Sign the decision written under a gate in approvals.md."""
    from tsl.approvals.service import approve as svc

    data = svc(rt(), comp(), run_id, gate)
    return emit_ok(f"{gate} {data['decision']} signed", data, next_=f"/truminds:resume {run_id}")


@app.command()
@command
def pr(
    run_id: str,
    draft: Annotated[bool, typer.Option("--draft")] = False,
    repo: Annotated[str | None, typer.Option("--repo", help="Product repo name")] = None,
) -> int:
    """Push run branches and open pull requests (never merges)."""
    from tsl.services.pr import open_prs

    data = open_prs(rt(), comp(), run_id, draft, repo)
    return emit_ok(f"{len(data['prs'])} pull request(s) opened", data)


@app.command("pr-sync")
@command
def pr_sync(
    run_id: Annotated[str | None, typer.Argument(help="One run; all runs when omitted")] = None,
) -> int:
    """Report run PRs merged or closed on GitHub to the portal (backfills missed webhooks)."""
    from tsl.services.pr import sync_prs

    data = sync_prs(rt(), comp(), run_id)
    return emit_ok(f"{data['sent']} merged or closed pull request(s) reported", data)


@app.command("ci-verify")
@command
def ci_verify(
    pr_: Annotated[int, typer.Option("--pr")],
    repo: Annotated[str, typer.Option("--repo")],
    companion: Annotated[Path, typer.Option("--companion")] = Path("companion"),
    head: Annotated[str | None, typer.Option("--head")] = None,
    product: Annotated[Path | None, typer.Option("--product")] = None,
    ci_token_file: Annotated[Path | None, typer.Option("--ci-token-file")] = None,
) -> int:
    """Re-check a pull request's records in CI. No LLM; fails closed."""
    from tsl.ci.verify import ci_verify as svc

    token = ci_token_file.read_text(encoding="utf-8").strip() if ci_token_file else None
    data, codes, note = svc(rt(), pr_, repo, companion, head, product, token)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        rows = "\n".join(
            f"| {s['step']} | {s['outcome']} | {s['band']} | {s['signature']} | {s['hash']} | "
            f"{s['recheck']} |"
            for s in data["steps"]
        )
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(
                f"## tsl-ci-verify: {data['result']}\n\n"
                "| Step | Outcome | Band | Signature | Hash | "
                f"CI re-check |\n|---|---|---|---|---|---|\n{rows}\n"
            )
    if not codes:
        return emit_ok("CI verify passed", data)
    return emit_err(
        codes[0],
        render(CATALOGUE[codes[0]].message, run_id=data.get("run_id"), detail=note or codes[0]),
        CATALOGUE[codes[0]].next,
        data,
        exit_=2,
    )


@app.command(context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def hook(event: str) -> None:
    """Claude Code hook entry (stdin/stdout hook JSON; never the envelope)."""
    from tsl.hooks.dispatch import run as run_hook

    out, code = run_hook(event, sys.stdin.read())
    if out:
        sys.stdout.write(out + "\n")
    raise typer.Exit(code)


# ------------------------------------------------------------------------------- context
@context_app.command("build")
@command
def context_build(
    check: Annotated[bool, typer.Option("--check")] = False,
    product_repo: Annotated[str | None, typer.Option("--product-repo")] = None,
    repo_commit: Annotated[list[str] | None, typer.Option("--repo-commit")] = None,
    sections: Annotated[str | None, typer.Option("--sections", help="id,id,...")] = None,
) -> int:
    """Run the extractors into context/generated/ and write the manifest."""
    from tsl.context.build import build

    commits = dict(x.split("=", 1) for x in (repo_commit or []))
    only = [x.strip() for x in sections.split(",") if x.strip()] if sections else None
    data, warnings, code = build(rt(), comp(), check, commits or None, only)
    if code is None:
        return emit_ok(
            "Context pack built" if not check else "Context pack checked",
            data,
            warnings,
            None if check else "review the sections, then tsl context sign",
        )
    if code == "E-CTX-02":
        return emit_err(
            code,
            "Context pack drift is over the limit",
            CATALOGUE[code].next,
            data,
            warnings,
            exit_=2,
        )
    w = next((x for x in warnings if x["code"] == code), None)
    msg = w["message"] if w else f"{code}: see data.lint and data.size"
    return emit_err(code, msg, CATALOGUE[code].next, data, warnings)


@context_app.command("sign")
@command
def context_sign() -> int:
    """Sign the pack (tech lead)."""
    from tsl.context.build import sign

    data = sign(rt(), comp())
    return emit_ok("Context pack signed", data)


@context_app.command("status")
@command
def context_status(deep: Annotated[bool, typer.Option("--deep")] = False) -> int:
    """Freshness verdict of the pack (F1-F7)."""
    from tsl.context.build import status_cmd

    data, warnings = status_cmd(rt(), comp())
    return emit_ok(f"Context pack is {data['state']}", data, warnings)


@context_app.command("draft-prepare")
@command
def context_draft_prepare(section: str) -> int:
    """Package for /truminds:context-draft: template, fact ids, budget, rules."""
    from tsl.context.build import draft_prepare

    data = draft_prepare(rt(), comp(), section)
    return emit_ok(f"Draft package for {section}", data, next_=data["check_command"])


@context_app.command("deny-term")
@command
def context_deny_term(term: str) -> int:
    """Print the hash of a name to block; the name is never written to disk."""
    from tsl.context.build import deny_term

    data = deny_term(term)
    return emit_ok("Add this line to context.redaction.deny_term_hashes", data)


# ------------------------------------------------------------------------------- evals
@eval_app.command("plan")
@command
def eval_plan(skill: str, version: Annotated[str | None, typer.Option("--version")] = None) -> int:
    """Lay out the eval work folder for a skill."""
    from tsl.evals.service import plan

    data = plan(rt(), skill, version)
    return emit_ok(f"{len(data['cases'])} eval cases ready", data)


@eval_app.command("run")
@command
def eval_run(skill: str, version: Annotated[str | None, typer.Option("--version")] = None) -> int:
    """Score every case with code only and sign the eval result."""
    from tsl.evals.service import run

    data, code = run(rt(), skill, version)
    if code is None:
        return emit_ok(f"Eval pass rate {data['pass_rate']}", data)
    return emit_err(
        code, f"Eval pass rate {data['pass_rate']} is below the minimum", CATALOGUE[code].next, data
    )


@eval_app.command("check")
@command
def eval_check(skill: str, case: Annotated[str, typer.Option("--case")]) -> int:
    """Score one case, unsigned."""
    from tsl.evals.service import check

    data = check(rt(), skill, case)
    if data["pass"]:
        return emit_ok(f"Case {case} passes", data)
    return emit_err(
        "E-EVAL-01",
        f"Case {case} fails: {'; '.join(data['failed_checks'])[:200]}",
        "Fix the skill or the case",
        data,
    )


@improve_app.command("plan")
@command
def improve_plan(
    skill: str,
    report: Annotated[Path | None, typer.Option("--report")] = None,
    flag: Annotated[str | None, typer.Option("--flag")] = None,
    offline: Annotated[bool, typer.Option("--offline")] = False,
) -> int:
    """Fetch the improvement report and print a plan."""
    from tsl.improve.plan import plan

    data, warnings = plan(rt(), skill, report, flag, offline)
    return emit_ok(
        f"Improvement plan for {skill}",
        data,
        warnings,
        f"tsl improve case {skill} --id EC-<nn>  (add a failing eval case first)",
    )


@improve_app.command("case")
@command
def improve_case(
    skill: str,
    id_: Annotated[str, typer.Option("--id")],
    kind: Annotated[str, typer.Option("--kind")] = "normal",
    title: Annotated[str | None, typer.Option("--title")] = None,
    improvement: Annotated[str | None, typer.Option("--improvement")] = None,
) -> int:
    """Scaffold a new eval case (invented data only, with the attestation block)."""
    from tsl.improve.service import case

    data = case(rt(), skill, id_, kind, title, improvement)
    return emit_ok(
        f"Case {id_} created", data, next_=f"write invented inputs, then tsl eval plan {skill}"
    )


@improve_app.command("check")
@command
def improve_check(
    skill: str,
    improvement: Annotated[str | None, typer.Option("--improvement")] = None,
    base: Annotated[str | None, typer.Option("--base")] = None,
    new_case: Annotated[list[str] | None, typer.Option("--new-case")] = None,
    before: Annotated[Path | None, typer.Option("--before")] = None,
    after: Annotated[Path | None, typer.Option("--after")] = None,
    deny_hashes: Annotated[Path | None, typer.Option("--deny-hashes")] = None,
) -> int:
    """Compare the signed before and after eval results; write improvement.v1."""
    from tsl.improve.service import check, raise_first

    data, codes = check(rt(), skill, improvement, base, new_case, before, after, deny_hashes)
    if codes:
        raise raise_first(data, codes)
    return emit_ok("Improvement evidence written", data, next_=f"tsl improve pr {skill}")


@improve_app.command("pr")
@command
def improve_pr(
    skill: str,
    improvement: Annotated[str | None, typer.Option("--improvement")] = None,
    summary: Annotated[str | None, typer.Option("--summary")] = None,
) -> int:
    """Push the improvement branch and open a PR with the evidence (never merges)."""
    from tsl.improve.service import open_pr

    data = open_pr(rt(), skill, improvement, summary)
    return emit_ok(f"Pull request #{data['pr']['number']} opened", data)


@harness_app.command("eval")
@command
def harness_eval(
    code_only: Annotated[bool, typer.Option("--code-only")] = False,
    dir_: Annotated[Path | None, typer.Option("--dir", help="Folder of case folders")] = None,
) -> int:
    """Measure gate, citation and decide accuracy on the labelled set."""
    from tsl.harness.accuracy import run

    data, misses = run(rt(), dir_, code_only)
    if not misses:
        return emit_ok(f"Harness accuracy on target ({data['cases']} cases)", data)
    return emit_err(
        "E-HARN-01",
        render(CATALOGUE["E-HARN-01"].message, detail="; ".join(misses)[:200]),
        CATALOGUE["E-HARN-01"].next,
        data,
    )


@companion_app.command("check")
@command
def companion_check(
    base: Annotated[str | None, typer.Option("--base", help="Check commits after this")] = None,
    event: Annotated[str | None, typer.Option("--event", help="push | pull_request")] = None,
    deny_hashes: Annotated[Path | None, typer.Option("--deny-hashes")] = None,
) -> int:
    """Companion CI: schemas, path ownership, append-only records, content, size."""
    from tsl.services.companion import check, first_error

    if event not in (None, "push", "pull_request"):
        raise TslError("E-USE-01", detail="--event is push or pull_request", cmd="companion check")
    data = check(rt(), comp(), base, event, deny_hashes)
    if data["codes"]:
        raise first_error(data)
    return emit_ok(f"Companion check passed ({data['files_checked']} files)", data)


@companion_app.command("archive")
@command
def companion_archive(
    reason: Annotated[str, typer.Option("--reason")] = "engagement_ended",
    abandon_runs: Annotated[bool, typer.Option("--abandon-runs")] = False,
) -> int:
    """Archive the companion repo (admin): ARCHIVE.json signed, tagged archive/final."""
    from tsl.services.companion import archive

    data, warnings = archive(rt(), comp(), reason, abandon_runs)
    return emit_ok(
        "Companion repo archived",
        data,
        warnings,
        "Admin sets the GitHub repository to archived (read-only) in its settings",
    )


# ------------------------------------------------------------------------------- telemetry
@events_app.command("flush")
@command
def events_flush(
    max_seconds: Annotated[float, typer.Option("--max-seconds")] = 30.0,
    retry_dead: Annotated[bool, typer.Option("--retry-dead")] = False,
) -> int:
    """Send queued events to the insights service."""
    from tsl.telemetry.emit import flush

    r = rt()
    if retry_dead:
        r.outbox().retry_dead()
    res = flush(r, max_seconds)
    data = res.data()
    if res.auth_failed:
        return emit_err(
            "E-AUTH-01", "Not logged in to Truminds; events stay queued", "tsl login", data
        )
    warnings = []
    if res.offline or data["pending"]:
        warnings.append(
            {"code": "E-NET-01", "message": f"Telemetry offline; {data['pending']} events queued"}
        )
    return emit_ok(f"{data['sent']} event(s) sent", data, warnings)


@app.command()
@command
def migrate(
    to: Annotated[str, typer.Option("--to")],
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
) -> int:
    """Plan a schema migration of unsigned files (signed records are never rewritten)."""
    from tsl.services.migrate import plan

    data = plan(comp(), to, dry_run)
    return emit_ok(f"{len(data['files'])} file(s) to migrate", data)
