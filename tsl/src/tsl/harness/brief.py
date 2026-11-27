"""Step brief: one step's skill text and inputs for a forked subagent (roadmap 25-27 Nov, B1).

A step normally runs in the main session: the run loop invokes its skill, whose preamble runs
`tsl verify $0 --inputs --json`. When the run picks a forked runner for the step (data.runner in
`tsl next`), the `step` skill runs this instead, in a subagent with a fresh context:

- the skill's SKILL.md body, with the preamble replaced by the same --inputs data, so the
  subagent follows the same instructions as the main session would;
- the product clones on this laptop and the run's branch in each (the main session knows them
  from the earlier steps);
- the run's open questions (the main session gets them from `tsl next`);
- with context "full", the step's context sections and this run's answers, preloaded. With
  "artifacts" the subagent reads them itself, as the skill says.

It records the runner on the attempt, so run metrics can compare the runners per step.
"""

from __future__ import annotations

import json
import re
from typing import Any

from tsl.core.errors import TslError
from tsl.core.frontmatter import split
from tsl.core.jsonio import read_json
from tsl.core.repo import Companion
from tsl.core.runtime import Runtime

CONTEXTS = ("artifacts", "full")
PREAMBLE = "Step context from tsl (do not edit):\n!`tsl verify $0 --inputs --json`\n"
HEADER = "# Step brief"


def runners_from_env(
    env: Any, steps: list[str], asks: frozenset[str] = frozenset()
) -> dict[str, dict[str, str]]:
    """The steps TSL_STEP_RUNNER hands to a forked subagent, read once at tsl state start.

    TSL_STEP_RUNNER is a comma-separated list of <step>=<context>, for example "ut=full" or
    "ut=artifacts,split=full". Steps not in the workflow and unknown contexts are ignored: those
    steps stay in the main session. So are steps in `asks`, whose skill asks the user
    (AskUserQuestion in allowed_tools: req, impact, design): the step runner cannot ask, so
    those wait on B2. The result is pinned in state.json (step_runners), so the
    choice is visible in the run record and an environment that changes mid-run cannot move a
    step (in one HMS-34 baseline a plain `tsl next` still saw the variable).
    """
    out: dict[str, dict[str, str]] = {}
    for part in str(env.get("TSL_STEP_RUNNER") or "").split(","):
        sid, _, context = (x.strip() for x in part.partition("="))
        if sid in steps and sid not in asks and context in CONTEXTS:
            out[sid] = {"mode": "fork", "context": context}
    return out


def runner_for(state: dict[str, Any], step: str) -> dict[str, str] | None:
    """The runner the run pinned for a step at start, or None for the main session."""
    r = (state.get("step_runners") or {}).get(step)
    return dict(r) if r else None


def build(rt: Runtime, comp: Companion, artifact: str, context: str) -> dict[str, Any]:
    from tsl.approvals import questions_md
    from tsl.harness.verify import verify_inputs
    from tsl.orchestrator.run import RunCtx
    from tsl.state.store import find_step, latest

    if context not in CONTEXTS:
        raise TslError(
            "E-USE-01", detail=f"--context is one of {', '.join(CONTEXTS)}", cmd="step brief"
        )
    runner = {"mode": "fork", "context": context}
    _precheck(rt, comp, artifact, runner)  # what can fail, before verify_inputs marks the launch
    data = verify_inputs(rt, comp, None, None, artifact)  # also marks the skill launch
    run = RunCtx(rt, comp, str(data["run_id"]))
    step, n = str(data["step"]), int(data["attempt"])
    sk = run.skill_for(step)
    body = split((sk.dir / "SKILL.md").read_text(encoding="utf-8")).body
    if PREAMBLE not in body:
        raise TslError("E-USE-01", detail=f"skill {sk.id} has no inputs preamble", cmd="step brief")
    envelope = json.dumps({"ok": True, "data": data}, indent=2)
    body = body.replace(PREAMBLE, f"Step context from tsl:\n{_fenced(envelope, 'json')}\n", 1)

    def mark(st: dict[str, Any]) -> None:
        a = latest(find_step(st, step))
        if a is not None and a["n"] == n:
            a["runner"] = runner

    with run.store.local_lock():
        run.store.update(mark)

    repos = _product_repos(comp, run.state)
    open_q = questions_md.unanswered(comp.path(run.questions_rel()), run.run_id)
    parts = [
        f"{HEADER}: {step} (attempt {n}) of run {run.run_id}",
        "",
        f"You run step {step} with skill {sk.ref}. Follow the skill text below exactly; it is "
        "the same text the main session would follow. data.artifact_path is the one artifact "
        "you write.",
        "",
        "---",
        "",
        body.strip(),
        "",
        "---",
        "",
        "## Product repos",
    ]
    if repos:
        parts.append(
            "The product code is in these clones; <repo> is the name used in citations "
            "(<repo>:<path>#L<n>). Read and edit them by these paths. Never search the "
            "companion repo for them."
        )
        for r in repos:
            line = f"- {r['repo']}: {r['path']}"
            if r.get("branch"):
                line += f" (branch {r['branch']}, base {r['base_sha']}"
                line += f", last passed step at {r['head_sha']})" if r.get("head_sha") else ")"
            parts.append(line)
    else:
        parts.append("None on this laptop (.tsl/local.yaml lists no clone).")
    parts += ["", "## Open questions of this run"]
    if open_q:
        parts.append("Still unanswered. Do not raise them again; to refer to one, cite its cite.")
        parts += [f"- {q['id']} ({q['cite']}): {q['question']}" for q in open_q]
    else:
        parts.append("None.")
    loaded: list[dict[str, Any]] = []
    if context == "full":
        parts += ["", *_preloaded(comp, run.run_id, sk, loaded)]
    return {
        "run_id": run.run_id,
        "step": step,
        "attempt": n,
        "artifact_path": data["artifact_path"],
        "runner": runner,
        "product_repos": repos,
        "preloaded": loaded,
        "brief": "\n".join(parts) + "\n",
    }


def _precheck(rt: Runtime, comp: Companion, artifact: str, runner: dict[str, str]) -> None:
    """Refuse the brief before verify_inputs marks the launch, so a refused brief leaves no
    half-open step behind (the pre-tool hook would hold the main session to its tools).

    - The run must have pinned this runner at start (E-USE-01): attempt.runner is what run
      metrics compare per step, so it must agree with state.step_runners.
    - The skill has the inputs preamble, and .tsl/local.yaml reads (the product repos).

    Only for the run's current step: any other path is left to verify_inputs, which names the
    real error (not an artifact path E-USE-01, not the current step E-RUN-09, lock E-LOCK-*).
    """
    from tsl.core.paths import ARTIFACT_RE
    from tsl.harness.verify import to_rel
    from tsl.orchestrator.run import RunCtx

    m = ARTIFACT_RE.match(to_rel(comp, artifact))
    if not m:
        return
    run, step = RunCtx(rt, comp, m.group("run_id")), m.group("step")
    if (run.state.get("cursor") or {}).get("step") != step:
        return
    pinned = runner_for(run.state, step)
    if pinned != runner:
        want = (
            f"--context {pinned['context']}" if pinned else "the step's skill in the main session"
        )
        raise TslError(
            "E-USE-01",
            detail=f"run pinned {want} for step {step} at start (TSL_STEP_RUNNER); "
            f"--context {runner['context']} does not match",
            cmd="step brief",
        )
    sk = run.skill_for(step)
    if PREAMBLE not in split((sk.dir / "SKILL.md").read_text(encoding="utf-8")).body:
        raise TslError("E-USE-01", detail=f"skill {sk.id} has no inputs preamble", cmd="step brief")
    _product_repos(comp, run.state)


def _fenced(text: str, lang: str) -> str:
    """A code fence longer than any run of backticks in the text, so the text cannot close it."""
    longest = max((len(r) for r in re.findall(r"`+", text)), default=0)
    fence = "`" * max(3, longest + 1)
    return f"{fence}{lang}\n{text}\n{fence}"


def _product_repos(comp: Companion, state: dict[str, Any]) -> list[dict[str, Any]]:
    """Each product clone on this laptop, with the run's branch in it when there is one.

    The main session knows these from the earlier steps; a forked step does not, and searching
    the companion repo for them is refused (it takes in other runs' files).
    """
    branches = state.get("branch") or {}
    out: list[dict[str, Any]] = []
    for name, path in sorted(comp.local_paths().items()):
        r: dict[str, Any] = {"repo": name, "path": path.as_posix()}
        b = branches.get(name)
        if b:
            r.update(branch=b["name"], base_sha=b["base_sha"], head_sha=b.get("head_sha"))
        out.append(r)
    return out


def _preloaded(comp: Companion, run_id: str, sk: Any, loaded: list[dict[str, Any]]) -> list[str]:
    """Context sections of the step and this run's answers, within half the step's budget."""
    from tsl.core.paths import ide_answers_path

    budget = int(int(sk.meta.get("size_budget_tokens") or 30000) * 0.5)
    manifest = comp.path("context/manifest.json")
    paths = {}
    if manifest.is_file():
        paths = {str(s["id"]): str(s["path"]) for s in read_json(manifest).get("sections", [])}
    want = [(str(s), paths.get(str(s))) for s in sk.meta.get("context_sections", [])]
    want.append(("ide-answers", ide_answers_path(run_id)))
    out = [
        "## Preloaded context",
        "Already read for you. Cite it by the path shown, as the skill says.",
    ]
    used = 0
    for sid, rel in want:
        p = comp.path(rel) if rel else None
        if p is None or not p.is_file():
            if sid != "ide-answers":  # no answers yet is normal
                loaded.append({"id": sid, "path": rel, "included": False})
                where = rel or "not in context/manifest.json"
                out += ["", f"### {sid} ({where}): not found, not preloaded"]
            continue
        text = p.read_text(encoding="utf-8")
        size = len(text.encode("utf-8")) // 4
        if used + size > budget:
            loaded.append({"id": sid, "path": rel, "included": False})
            out += ["", f"### {rel} (over budget: read it yourself if you need it)"]
            continue
        used += size
        loaded.append({"id": sid, "path": rel, "included": True})
        lang = "json" if str(rel).endswith(".json") else "markdown"
        out += ["", f"### {rel}", _fenced(text.rstrip(), lang)]
    return out
