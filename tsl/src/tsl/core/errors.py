"""Error catalogue (registry §2, Doc 4 §5.2, SDD-04 §5, SDD-03 §14.1).

Every code tsl can raise lives here with its exit code, message template and
next-action template. The registry is canonical; tests compare the two.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ErrorDef:
    code: str
    exit: int
    message: str
    next: str


def _d(code: str, exit_: int, message: str, next_: str) -> ErrorDef:
    return ErrorDef(code, exit_, message, next_)


# exit codes (SDD-04 §3.2)
OK, USAGE, CHECK, BLOCKED, PAUSED, ABORT, AUTHNET = 0, 1, 2, 3, 4, 5, 10

CATALOGUE: dict[str, ErrorDef] = {
    e.code: e
    for e in [
        # identity
        _d("E-AUTH-01", AUTHNET, "Not logged in to Truminds.", "tsl login"),
        _d("E-AUTH-02", AUTHNET, "Your signing key is revoked or unknown.", "tsl login"),
        _d(
            "E-AUTH-03",
            BLOCKED,
            "You do not have the engineer role for system {system}.",
            "Ask your tech lead or admin for access",
        ),
        _d(
            "E-AUTH-04",
            BLOCKED,
            "Only a tech lead of this system can do this ({action}).",
            "Ask the system's tech lead, for example to run tsl context sign",
        ),
        _d(
            "E-AUTH-05",
            BLOCKED,
            "Approver lacks role {role} for gate {gate}.",
            "Ask someone with that role to approve",
        ),
        _d(
            "E-AUTH-06",
            BLOCKED,
            "You cannot approve a gate on a step you generated.",
            "Ask another tech lead",
        ),
        _d(
            "E-AUTH-07",
            AUTHNET,
            "Role cache older than 24 h and service unreachable.",
            "Reconnect, then repeat",
        ),
        _d(
            "E-AUTH-11",
            BLOCKED,
            "Approval for gate {gate} could not be verified: {reason}.",
            "{fix}",
        ),
        _d(
            "E-AUTH-08",
            BLOCKED,
            "Your account has no Truminds app role, or it is deactivated.",
            "Ask your manager to request access",
        ),
        _d(
            "E-CFG-01",
            USAGE,
            "{file} is invalid: {pointer} {reason}",
            "Fix the file; tsl validate {file}",
        ),
        _d(
            "E-CHK-01",
            CHECK,
            "Hard gate {gate} failed: {detail}",
            "Claude retries automatically ({n} of {max})",
        ),
        _d(
            "E-CI-01",
            CHECK,
            "PR has code changes but no verification records for run {run_id}.",
            "Run the change through /truminds:run",
        ),
        _d(
            "E-CI-02",
            CHECK,
            "Record signature invalid or signer lacked role at signing time.",
            "Re-run the step",
        ),
        _d(
            "E-CI-03",
            CHECK,
            "CI re-run of code checks differs from laptop result.",
            "Investigate; re-run the step",
        ),
        _d(
            "E-CI-04",
            CHECK,
            "PR code differs from the verified change (tree or diff hash).",
            "Resume the run so the code step is re-verified",
        ),
        _d("E-CI-05", CHECK, "Record chain incomplete: {detail}", "Finish the run"),
        _d(
            "E-CI-06",
            CHECK,
            "Companion repo or key registry unreachable; failing closed.",
            "Re-run the CI job",
        ),
        _d(
            "E-COMP-01",
            CHECK,
            "Companion check failed: schema invalid in {path}: {detail}",
            "Fix the listed files",
        ),
        _d(
            "E-COMP-02",
            CHECK,
            "Companion check failed: {detail}",
            "Fix the listed files; protected paths change only by pull request",
        ),
        _d(
            "E-COMP-03",
            CHECK,
            "Companion check failed: record {path} was modified or deleted.",
            "Restore the record; records are append-only",
        ),
        _d(
            "E-COMP-04",
            CHECK,
            "Companion check failed: forbidden content in {path} line {line}.",
            "Remove it and rewrite history with the admin",
        ),
        _d(
            "E-COMP-05",
            CHECK,
            "Companion check failed: {path} is too large ({detail}).",
            "Remove the file; build outputs and data never go in the companion repo",
        ),
        _d(
            "E-COMP-06",
            BLOCKED,
            "Cannot archive: {n} runs are not completed.",
            "Finish them or use --abandon-runs",
        ),
        _d("E-COMP-07", BLOCKED, "System {system} is archived.", "None; read-only"),
        _d(
            "E-CONS-01",
            BLOCKED,
            "No client consent recorded for {client} (or scope lacks {scope}).",
            "Admin records consent in the portal",
        ),
        _d(
            "E-CONS-02",
            BLOCKED,
            "Consent for {client} does not cover opening PRs on product repos.",
            "Submit the patch by hand, or extend consent",
        ),
        _d(
            "E-CTX-01",
            BLOCKED,
            "Context pack missing{detail}.",
            "Tech lead runs tsl context build, reviews, then tsl context sign",
        ),
        _d(
            "E-CTX-02",
            OK,
            "Context pack is stale ({reason}). Band capped at Medium.",
            "tsl context build then re-sign with tsl context sign",
        ),
        _d("E-CTX-03", BLOCKED, "Pack signature does not verify.", "Re-sign with tsl context sign"),
        _d(
            "E-CTX-04",
            CHECK,
            "Section {section} is not reviewed ({detail}).",
            "Tech lead reviews the section, removes markers, sets status: reviewed",
        ),
        _d("E-CTX-05", CHECK, "Size limit exceeded: {detail}.", "Split or shorten the section"),
        _d(
            "E-CTX-06",
            CHECK,
            "Secret, personal data or denied term found in {path} line {line} ({kind}).",
            "Remove it by hand; re-run tsl context build --check",
        ),
        _d(
            "E-CTX-07",
            CHECK,
            "Pack lint failed: {n} broken anchors or citations.",
            "Fix the listed anchors or Sources: lines",
        ),
        _d(
            "E-CTX-08",
            CHECK,
            "Extractor {name} failed on {repo} ({reason}); section {section} not rebuilt.",
            "Report to the extractor owner; other sections are built",
        ),
        _d(
            "E-CTX-09",
            BLOCKED,
            "Manifest out of date, or product repo {repo} cannot be read.",
            "Run tsl context build; check .tsl/local.yaml and access",
        ),
        _d("E-DEC-01", BLOCKED, "Gate {gate} still pending.", "tsl verify --status, then decide"),
        _d("E-DEC-02", BLOCKED, "Artifact changed since checks ran.", "Run tsl verify"),
        _d("E-DEP-01", OK, "{thing} is deprecated.", "Use {replacement}"),
        _d("E-ENV-01", BLOCKED, "Prerequisite missing: {item}", "Fix hint from tsl doctor"),
        _d(
            "E-HARN-01",
            CHECK,
            "Harness accuracy below target: {detail}",
            "Fix the gate or decide logic, or the labelled case",
        ),
        _d(
            "E-IMP-01",
            CHECK,
            "New eval case {case} does not fail before the change (not a reproduction).",
            "Rewrite the case so it reproduces the failure",
        ),
        _d(
            "E-IMP-02",
            CHECK,
            "Regression, or cases removed or edited without justification: {detail}",
            "Fix the skill change, or restore the cases",
        ),
        _d(
            "E-IMP-03",
            CHECK,
            "Pass rate {after} is below the minimum {min} or below before ({before}).",
            "Improve the skill until the eval set passes",
        ),
        _d(
            "E-IMP-04",
            CHECK,
            "Eval result unsigned, signer mismatch or skill hash mismatch: {detail}",
            "Re-run tsl eval run on the before and after versions",
        ),
        _d(
            "E-IMP-05",
            CHECK,
            "Forbidden content in eval file {path} line {line}.",
            "Use invented data only (SDD-11 §7)",
        ),
        _d(
            "E-ENV-02",
            OK,
            "Full-disk encryption cannot be confirmed.",
            "Turn on FileVault or BitLocker, or confirm with IT",
        ),
        _d(
            "E-EVAL-01",
            CHECK,
            "Eval pass rate {rate} below {min} or fewer than {n} cases.",
            "Fix the skill or add cases",
        ),
        _d(
            "E-GIT-01",
            AUTHNET,
            "Git {op} failed: {detail}",
            "Check network and access, then repeat",
        ),
        _d(
            "E-HOOK-01",
            OK,
            "Write blocked: tsl is missing, the wrong version, or did not answer "
            "while a run is active.",
            "uv tool install truminds-tsl, then tsl doctor",
        ),
        _d(
            "E-IN-01",
            CHECK,
            "Required input {name} missing for skill {skill}.",
            "Provide it or run the upstream step",
        ),
        _d("E-IN-02", CHECK, "Input {artifact} is stale (H6).", "Re-running upstream step {step}"),
        _d(
            "E-INIT-01",
            BLOCKED,
            "System {system} has no companion repo registered.",
            "Admin registers it",
        ),
        _d(
            "E-INIT-02",
            BLOCKED,
            "Companion repo {repo} is not empty.",
            "Use the existing repo, or ask the admin",
        ),
        _d(
            "E-INT-01",
            USAGE,
            "Internal error {log_id}",
            "Report {log_id} with ~/.truminds/logs/tsl.log",
        ),
        _d("E-KEY-01", AUTHNET, "No usable OS keychain backend.", "See tsl doctor"),
        _d(
            "E-KEY-02",
            AUTHNET,
            "Key proof does not verify, or iat too old.",
            "Repeat tsl login; check the laptop clock",
        ),
        _d(
            "E-KEY-03",
            AUTHNET,
            "Key id already registered with another public key.",
            "Repeat tsl login",
        ),
        _d("E-KEY-04", AUTHNET, "Key not found, or not yours.", "tsl keys list"),
        _d("E-KEY-05", AUTHNET, "Your signing key expired.", "tsl keys rotate"),
        _d(
            "E-KEY-06",
            AUTHNET,
            "compromised_since is outside the key's life, or later than the stored value.",
            "Correct the time",
        ),
        _d(
            "E-LOCK-01",
            BLOCKED,
            "{ticket} / {workflow} is locked by {holder} in {run_id}.",
            "Resume if yours; else ask a tech lead to release (tsl state unlock)",
        ),
        _d(
            "E-LOCK-02",
            BLOCKED,
            "Lock lost or released for run {run_id}.",
            "Start a new run with /truminds:run",
        ),
        _d(
            "E-LOCK-03",
            AUTHNET,
            "Cannot take a lock offline.",
            "Reconnect, then start the run again",
        ),
        _d(
            "E-LOCK-04",
            AUTHNET,
            "Could not push the run lock after 3 retries.",
            "Check write access to the companion repo; retry",
        ),
        _d(
            "E-NET-01",
            OK,
            "Telemetry offline; {n} events queued in outbox.",
            "None; sent automatically",
        ),
        _d(
            "E-NET-02",
            AUTHNET,
            "Insights service unreachable.",
            "Retry; offline-safe commands still work",
        ),
        _d(
            "E-POD-01",
            BLOCKED,
            "Workflow belongs to more than one pod on the system.",
            "Pass --pod",
        ),
        _d(
            "E-POL-01",
            ABORT,
            "Blocked: write outside allowed paths {path}.",
            "Run aborted; check tsl.yaml product_repos",
        ),
        _d(
            "E-POL-02",
            ABORT,
            "Blocked: read of sensitive file {path}.",
            "Run aborted; remove the need or ask tech lead to adjust policy",
        ),
        _d(
            "E-POL-03",
            ABORT,
            "Blocked: MCP write {tool} without approval.",
            "Add an approval entry, then resume",
        ),
        _d("E-POL-04", ABORT, "Tool {tool} not permitted for skill {skill}.", "Run aborted"),
        _d(
            "E-POL-05", ABORT, "Tool log missing or altered.", "Run aborted; tech lead investigates"
        ),
        _d(
            "E-PR-01",
            BLOCKED,
            "Run {run_id} has records that are not pushed to the companion repo.",
            "Reconnect; the next tsl call pushes them",
        ),
        _d(
            "E-REPO-01",
            USAGE,
            "Not inside a companion repo (no tsl.yaml found).",
            "cd into the companion repo or pass --repo",
        ),
        _d(
            "E-REV-01",
            BLOCKED,
            "Cannot prepare review: checks missing or failing.",
            "Run tsl verify and fix gates first",
        ),
        _d(
            "E-REV-02",
            CHECK,
            "Reviewer output is not valid review.v1: {pointer}",
            "Re-run the review skill",
        ),
        _d(
            "E-REV-03",
            CHECK,
            "Review is for an older artifact or package.",
            "Run the review step again",
        ),
        _d(
            "E-REV-04",
            OK,
            "Reviewer could not review: {reason}. Band capped at Low.",
            "None; decide will escalate",
        ),
        _d("E-RUN-01", PAUSED, "Run paused for input.", "Answer open-questions.md, then resume"),
        _d("E-RUN-02", PAUSED, "Run paused for approval.", "Approver runs tsl approve"),
        _d("E-RUN-03", CHECK, "Cannot resume: {n} blocking questions unanswered.", "Answer them"),
        _d("E-RUN-04", BLOCKED, "Run {run_id} not found.", "tsl state show"),
        _d("E-RUN-05", BLOCKED, "Run is {status}; {command} needs {needed}.", "{hint}"),
        _d(
            "E-RUN-06",
            BLOCKED,
            "Run {run_id} belongs to {owner}.",
            "Ask the owner, or a tech lead to unlock",
        ),
        _d(
            "E-RUN-07",
            CHECK,
            "Frozen answers changed after resume ({ids}).",
            "Add a revision block with a reason instead of editing the answer",
        ),
        _d(
            "E-RUN-08",
            BLOCKED,
            "Approval does not match the artifact ({detail}).",
            "Ask the approver to review the current artifact again",
        ),
        _d(
            "E-RUN-09",
            BLOCKED,
            "Step {step} is not the open step of the active run.",
            "tsl next {run_id}",
        ),
        _d(
            "E-RUN-10",
            BLOCKED,
            "Pinned skill version not installed ({detail}).",
            "tsl state repin {run_id}",
        ),
        _d(
            "E-RUN-11",
            BLOCKED,
            "Run busy in another process or session.",
            "Close the other session, or tsl state resume {run_id} --take-over",
        ),
        _d(
            "E-SCH-01",
            USAGE,
            "File {path} uses schema {version} that this tsl does not read.",
            "tsl migrate or upgrade the plugin",
        ),
        _d(
            "E-SEC-01",
            ABORT,
            "Secret or PII detected in artifact (H4).",
            "Run aborted; security event raised",
        ),
        _d(
            "E-SEC-02",
            ABORT,
            "Personal data detected in artifact (H4).",
            "Run aborted; security event raised",
        ),
        _d("E-USE-01", USAGE, "Invalid arguments: {detail}", "tsl {cmd} --help"),
        _d(
            "E-SMOKE-01",
            CHECK,
            "Smoke run failed at '{step}': {detail}",
            "Fix that step, then run tsl smoke again",
        ),
        _d(
            "E-VER-01",
            BLOCKED,
            "tsl {a} does not match {what} {b}.",
            "uv tool install truminds-tsl=={b}",
        ),
        _d(
            "E-WFL-01",
            CHECK,
            "Workflow file does not match workflow.v1: {detail}",
            "Fix the workflow",
        ),
        _d("E-WFL-02", CHECK, "Workflow graph invalid: {detail}", "Fix the workflow"),
        _d(
            "E-WFL-03",
            CHECK,
            "Input binding missing or schema mismatch: {detail}",
            "Fix the workflow",
        ),
        _d("E-WFL-04", CHECK, "Skill range does not resolve: {detail}", "Fix the workflow"),
        _d("E-WFL-05", CHECK, "Retry limits exceed org maximums: {detail}", "Fix the workflow"),
        # harness gate codes (SDD-03 §14.1); reported inside checks.json
        _d(
            "E-H1-01",
            CHECK,
            "Front matter missing or not valid YAML in {file}.",
            "Fix and write again",
        ),
        _d("E-H1-02", CHECK, "Unknown schema {id}.", "Use a schema listed by tsl validate"),
        _d(
            "E-H1-03",
            CHECK,
            "Envelope {field} {value} does not match run state {expected}.",
            "Fix the envelope",
        ),
        _d("E-H1-04", CHECK, "Body schema error at {pointer}: {message}", "Fix the field"),
        _d(
            "E-H1-05",
            CHECK,
            "Citation {ref} does not match the citation format.",
            "Use repo:path#anchor",
        ),
        _d("E-H2-01", CHECK, "Section {title} missing.", "Add it"),
        _d("E-H2-02", CHECK, "Section {title} is empty.", "Add content"),
        _d(
            "E-H2-03",
            CHECK,
            "Known / Assumed / Unknown incomplete.",
            "Add the lists; mark each unknown blocking or not",
        ),
        _d("E-H3-01", CHECK, "Build failed: {summary}", "Fix loop"),
        _d("E-H3-02", CHECK, "Tests failed: {summary}", "Fix loop"),
        _d("E-H3-03", CHECK, "Lint failed: {summary}", "Fix loop"),
        _d("E-H3-04", CHECK, "SAST failed: {summary}", "Fix loop"),
        _d("E-H3-05", CHECK, "Coverage dropped: {summary}", "Fix loop"),
        _d("E-H3-06", CHECK, "Verifier step {step} timed out.", "Fix loop"),
        _d(
            "E-H3-07",
            BLOCKED,
            "Docker not running or image unavailable.",
            "Start Docker, then tsl verify --gates H3",
        ),
        _d("E-H4-03", CHECK, "Client name found in shared output.", "Replace with a code"),
        _d(
            "E-H4-04",
            CHECK,
            "Value {value} in {where} not found in inputs or assumptions.",
            "Remove it or add an assumption",
        ),
        _d("E-H5-01", CHECK, "Trace missing or incomplete.", "Add trace ids"),
        _d("E-H5-02", CHECK, "Trace id {id} not found.", "Fix the id"),
        _d(
            "E-H5-03",
            CHECK,
            "code[] does not match the run branch diff.",
            "Re-run tsl verify --inputs after the last edit and copy code[]",
        ),
        _d(
            "E-H6-03",
            CHECK,
            "Upstream record for {input} missing, unsigned or not passed.",
            "Re-run step {step}",
        ),
    ]
}


class _Default(dict[str, Any]):
    def __missing__(self, key: str) -> str:
        return f"<{key}>"


def render(template: str, **kw: Any) -> str:
    return template.format_map(_Default(kw))


class TslError(Exception):
    """A failure with a catalogue code. Services raise it; the CLI renders it."""

    def __init__(
        self,
        code: str,
        message: str | None = None,
        *,
        next: str | None = None,
        data: dict[str, Any] | None = None,
        exit: int | None = None,
        **fmt: Any,
    ) -> None:
        d = CATALOGUE.get(code)
        if d is None:
            raise KeyError(f"unknown error code {code}")
        self.code = code
        self.exit = d.exit if exit is None else exit
        self.message = (message if message is not None else render(d.message, **fmt))[:300]
        self.next = (next if next is not None else render(d.next, **fmt))[:300]
        self.data = data or {}
        super().__init__(f"{code} {self.message}")


def warning(code: str, message: str | None = None, **fmt: Any) -> dict[str, str]:
    d = CATALOGUE[code]
    return {"code": code, "message": (message or render(d.message, **fmt))[:300]}
