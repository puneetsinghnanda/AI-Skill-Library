"""tsl next in code mode: code runs the workflow loop, the model only does the step it is given.

Design A1 (tsl-advance) §5. Each call works out the phase of the open step from files on disk,
runs every check, record and decision that needs no model, and returns one next-action.v2
instruction: run_step, fix, run_reviewer, ask, pause_approval, done or stopped.

A second call with nothing changed on disk returns the same instruction, except a fix: each fix
handout is a round, changed file or not, so a fix the step cannot make by editing the artifact
(an H7 tool-log item) ends in the full checks after FIX_ROUNDS. Per attempt the loop keeps a small
state file next to the instruction (seeded, fix, verified and prepared keys), so it never repeats
a check. For a code step the key is the artifact hash plus the product repo diff, so a retry that
only changes product code counts as progress.
"""

from __future__ import annotations

import shutil
from typing import Any

from tsl.approvals import questions_md
from tsl.core.clock import iso
from tsl.core.errors import TslError
from tsl.core.jsonio import read_json, write_json
from tsl.core.paths import history_dir, sibling
from tsl.core.repo import Companion
from tsl.core.runtime import Runtime
from tsl.harness import plain
from tsl.orchestrator.extensions import ask_raised, phase
from tsl.orchestrator.next import _action_for_attempt, next_action, pinned_and_heartbeat
from tsl.orchestrator.run import RunCtx
from tsl.state.store import latest

SCHEMA = "next-action.v2"
FIX_ROUNDS = 2  # self-check rounds per attempt before the full checks run anyway
H3_ENV = ("E-H3-07", "E-H3-08", "E-H3-09")  # verifier could not run: H3 stays pending
SEEDED_CAUSES = ("retry_checks", "retry_review", "retry_verifier", "gate_changes")
MAX_HOPS = 50  # safety net: decisions and attempt openings per call


def instructions_dir(run_id: str) -> str:
    return f"runs/{run_id}/instructions"


def instruction_path(run_id: str, step: str, attempt: int) -> str:
    return f"{instructions_dir(run_id)}/{step}.a{attempt}.json"


def _loop_path(run_id: str, step: str, attempt: int) -> str:
    return f"{instructions_dir(run_id)}/{step}.a{attempt}.loop.json"


class _Loop:
    def __init__(self, rt: Runtime, comp: Companion, run_id: str) -> None:
        self.rt, self.comp, self.run_id = rt, comp, run_id
        self.warnings: list[dict[str, str]] = []
        self.notes: list[str] = []  # outcomes reached during this call, shown before the action

    # ----------------------------------------------------------------- helpers
    def _sha(self, rel: str) -> str | None:
        from tsl.core.hashing import sha256_file

        p = self.comp.path(rel)
        return sha256_file(p) if p.is_file() else None

    def _key(self, ctx: RunCtx, step: str, rel: str) -> str | None:
        """What counts as the step's work: the artifact, plus the product diff for a code step."""
        sha = self._sha(rel)
        if sha is None or not ctx.skill_for(step).is_code:
            return sha
        from tsl.harness.verify import product_changes

        diffs = [f"{c['repo']}:{c['diff_sha256']}" for c in product_changes(ctx) or []]
        return "|".join([sha, *diffs])

    def _ls(self, step: str, n: int) -> dict[str, Any]:
        p = self.comp.path(_loop_path(self.run_id, step, n))
        return dict(read_json(p)) if p.is_file() else {}

    def _save_ls(self, step: str, n: int, ls: dict[str, Any]) -> None:
        p = self.comp.path(_loop_path(self.run_id, step, n))
        p.parent.mkdir(parents=True, exist_ok=True)
        write_json(p, ls)

    def _say(self, text: str) -> str:
        return " · ".join([*self.notes, text]) if self.notes else text

    # ------------------------------------------------------------ instructions
    def _instruction(
        self, ctx: RunCtx, step: str, action: str, say: str, **extra: Any
    ) -> dict[str, Any]:
        v1 = _action_for_attempt(ctx, step, "run_skill")
        n = int(v1["attempt"])
        out: dict[str, Any] = {
            "schema": SCHEMA,
            "action": action,
            "run_id": self.run_id,
            "step": step,
            "attempt": n,
            "skill": v1["skill"],
            "instruction_path": instruction_path(self.run_id, step, n),
            "say": self._say(say),
            "artifact_path": v1["artifact_path"],
            "allowed_tools": ctx.skill_for(step).allowed_tools,
            "context": {
                "inputs": v1["inputs"],
                "context_sections": v1["context_sections"],
                "answers": v1["answers"],
                "open_questions": v1["open_questions"],
            },
            "retry": self._retry(ctx, step, v1),
            "budget": v1["budget"],
            "progress": v1["progress"],
        }
        out.update(extra)
        p = self.comp.path(out["instruction_path"])
        if not self.notes and p.is_file():
            # A repeat call: nothing was decided on the way, so the same instruction, with the
            # say it was first handed out with (that one names the outcome that led here).
            old = dict(read_json(p))
            if {**old, "say": out["say"]} == out:
                out["say"] = old["say"]
        p.parent.mkdir(parents=True, exist_ok=True)
        write_json(p, out)
        self._current_action(ctx, action, step, n)
        return out

    def _retry(self, ctx: RunCtx, step: str, v1: dict[str, Any]) -> dict[str, Any] | None:
        n = int(v1["attempt"])
        if n == 1 or v1["cause"] not in SEEDED_CAUSES:
            return None
        prev = f"{history_dir(ctx.ticket, self.run_id, step, n - 1)}/{step}.md"
        return {
            "cause": v1["cause"],
            "seeded_from": prev if self.comp.path(prev).is_file() else None,
            "feedback": v1["feedback"],  # gate failures and review findings, by path
        }

    def _run_level(self, action: str, say: str, **extra: Any) -> dict[str, Any]:
        """ask, pause_approval, done, stopped: no step is being worked on, so clear
        current_action (else a paused or finished run looks stuck)."""
        ctx = RunCtx(self.rt, self.comp, self.run_id)
        if ctx.state.get("current_action") is not None:

            def clear(st: dict[str, Any]) -> None:
                st["current_action"] = None

            ctx.store.update(clear)
        out = {"schema": SCHEMA, "action": action, "run_id": self.run_id, "say": self._say(say)}
        out.update(extra)
        return out

    def _current_action(self, ctx: RunCtx, action: str, step: str, n: int) -> None:
        """D2: what was handed out, by which session, since when (same action keeps its time)."""
        cur = ctx.state.get("current_action") or {}
        if cur.get("action") == action and cur.get("step") == step and cur.get("attempt") == n:
            return
        rec = {
            "action": action,
            "step": step,
            "attempt": n,
            "started_at": iso(self.rt.clock()),
            "driver": ctx.state.get("driver") or "skill",
            "session_id": self.rt.session_id(),
            "agent_id": None,
        }

        def apply(st: dict[str, Any]) -> None:
            st["current_action"] = rec

        ctx.state = ctx.store.update(apply)

    # ------------------------------------------------------------- the phases
    def run(self) -> dict[str, Any]:
        for _ in range(MAX_HOPS):
            ctx = RunCtx(self.rt, self.comp, self.run_id)
            st = ctx.state
            cur = st.get("cursor")
            a = latest(ctx.step(str(cur["step"]))) if cur else None
            if st["status"] == "RUNNING" and cur and a is not None and a.get("outcome") is None:
                with ctx.store.local_lock():  # the same checks next_action makes (E-RUN-10/11)
                    ctx.assert_lock_held()
                    ctx.assert_session()
                    pinned_and_heartbeat(self.rt, self.comp, ctx)
                out = self._in_step(ctx, str(cur["step"]), a)
                if out is not None:
                    return out
                continue  # a decision was made: ask next_action what follows
            try:
                v1, _ = next_action(self.rt, self.comp, self.run_id)
            except TslError as exc:
                act = (exc.data or {}).get("action")
                if act == "pause_input":
                    from tsl.state.service import resume

                    try:  # resume's own rule decides what is answered (answered_by too)
                        _, w = resume(self.rt, self.comp, self.run_id)
                    except TslError as e:
                        if e.code != "E-RUN-03":
                            raise
                        return self._ask(ctx, list((e.data or {}).get("unanswered") or []))
                    self.warnings += w
                    continue
                if act == "pause_approval":
                    return self._run_level("pause_approval", exc.message)
                raise
            act = v1["action"]
            if act in ("run_skill", "run_decide"):
                continue  # the attempt is open now: the in-step branch takes it
            if act == "open_pr":
                from tsl.services.pr import open_prs

                data = open_prs(self.rt, self.comp, self.run_id, False, None)
                self.notes.append(f"{len(data['prs'])} pull request(s) opened")
                continue
            return self._run_level(act, "Run complete" if act == "done" else "Run stopped")
        raise RuntimeError(f"next: no stable action after {MAX_HOPS} hops")

    def _in_step(self, ctx: RunCtx, step: str, a: dict[str, Any]) -> dict[str, Any] | None:
        n = int(a["n"])
        rel = str(a["artifact"])
        ls = self._ls(step, n)
        self._seed(ctx, step, a, rel, ls)
        key = self._key(ctx, step, rel)
        if key is None or key == ls.get("seeded_key"):
            return self._instruction(ctx, step, "run_step", self._step_say(ctx, step, a))
        if self.comp.path(sibling(rel, ".review.json")).is_file():
            return self._decide(rel)
        if ls.get("prepared_key") == key:
            return self._after_review(ctx, step, n, rel, ls)
        if ls.get("verified_key") != key:
            rounds = int(ls.get("fix_rounds", 0))
            if rounds < FIX_ROUNDS:
                from tsl.harness.verify import self_check

                fix = self_check(self.rt, self.comp, rel)["fix"]
                if fix:  # every handout is a round, so an unfixable item cannot loop forever
                    ls.update(fix_rounds=rounds + 1, fix_key=key, fix=fix)
                    self._save_ls(step, n, ls)
                    return self._fix(ctx, step, fix)
            if not self._full_checks(rel):
                return self._decide(rel)  # a hard gate failed: decide skips the review
            key = str(self._key(ctx, step, rel))  # the full checks stamp the envelope
            ls["verified_key"] = key
            self._save_ls(step, n, ls)
        return self._prepare(ctx, step, n, ls, key)

    def _seed(
        self, ctx: RunCtx, step: str, a: dict[str, Any], rel: str, ls: dict[str, Any]
    ) -> None:
        """A retry starts from the last attempt: copy it to artifact_path once (design §6 #6)."""
        n = int(a["n"])
        if n == 1 or a.get("cause") not in SEEDED_CAUSES or "seeded_key" in ls:
            return
        prev = self.comp.path(f"{history_dir(ctx.ticket, self.run_id, step, n - 1)}/{step}.md")
        dest = self.comp.path(rel)
        if prev.is_file() and not dest.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(prev, dest)
            ls["seeded_key"] = self._key(ctx, step, rel)
        else:
            ls["seeded_key"] = None
        self._save_ls(step, n, ls)

    def _step_say(self, ctx: RunCtx, step: str, a: dict[str, Any]) -> str:
        p = ctx.progress(step)
        what = f"attempt {a['n']}" + (f" ({a['cause']})" if int(a["n"]) > 1 else "")
        return f"{step} ({p['index']}/{p['total']}): {what}"

    def _fix(self, ctx: RunCtx, step: str, fix: list[dict[str, str]]) -> dict[str, Any]:
        a = latest(ctx.step(step))
        if (ctx.state.get("current_action") or {}).get("action") != "fix" and a is not None:
            phase(self.rt, self.comp, ctx.state, step, int(a["n"]), "fix")
        return self._instruction(
            ctx, step, "fix", f"{step}: self-check found {len(fix)} item(s) to fix", fix=fix
        )

    def _full_checks(self, rel: str) -> bool:
        """Every check, the verifier (H3) too. False when a hard gate failed."""
        from tsl.harness.verify import verify_artifact

        try:
            verify_artifact(self.rt, self.comp, rel)
        except TslError as exc:
            # E-H3-07/08/09: the verifier could not run. H3 stays pending, and review prepare
            # refuses a pending gate (E-REV-01), so stop with tsl's own message (start Docker,
            # then `tsl next` again). Nothing is marked as checked, so that call re-runs them.
            if exc.code in H3_ENV:
                step = rel.rsplit("/", 1)[-1].removesuffix(".md")
                raise TslError(
                    exc.code,
                    f"Paused at {step}: the code checks could not run ({exc.message})",
                    next=f"Start Docker Desktop, then run tsl next {self.run_id} "
                    "(or tell the session to continue)",
                    data=exc.data,
                ) from None
            if any(g.get("status") == "fail" for g in (exc.data or {}).get("gates", [])):
                return False
            raise
        return True

    def _prepare(
        self, ctx: RunCtx, step: str, n: int, ls: dict[str, Any], key: str
    ) -> dict[str, Any]:
        from tsl.review.service import prepare

        pkg = prepare(self.rt, self.comp, str(latest(ctx.step(step))["artifact"]))  # type: ignore[index]
        ls.update(
            prepared_key=key,
            package_path=pkg["package_path"],
            write_to=pkg["review_input_path"],
        )
        self._save_ls(step, n, ls)
        return self._reviewer(ctx, step, ls)

    def _reviewer(self, ctx: RunCtx, step: str, ls: dict[str, Any]) -> dict[str, Any]:
        rounds = int(ls.get("review_rounds", 0))
        say = f"{step}: checks passed, review" + (f" (round {rounds + 1})" if rounds else "")
        review = {"package_path": ls["package_path"], "write_to": ls["write_to"]}
        return self._instruction(ctx, step, "run_reviewer", say, review=review)

    def _after_review(
        self, ctx: RunCtx, step: str, n: int, rel: str, ls: dict[str, Any]
    ) -> dict[str, Any] | None:
        """The reviewer's file is there: record it, or rerun the reviewer on E-REV-02/05."""
        from tsl.review.service import record

        inp = self.comp.path(ls["write_to"])
        if not inp.is_file():
            return self._reviewer(ctx, step, ls)
        try:
            _, w = record(self.rt, self.comp, rel, inp.read_text(encoding="utf-8"), None)
        except TslError as exc:
            if exc.code not in ("E-REV-02", "E-REV-05"):
                raise
            # E-REV-02 has its own budget (retry.review); E-REV-05 rounds are counted and
            # capped by record itself (retry.record), so they never use up the E-REV-02 one.
            invalid = int(ls.get("invalid_rounds", 0)) + (exc.code == "E-REV-02")
            if exc.code == "E-REV-02" and invalid >= ctx.retry_limits(step)["review"]:
                _, w = record(
                    self.rt, self.comp, rel, None, "reviewer output still invalid (E-REV-02)"
                )
                self.warnings += w
                return self._decide(rel)
            ls.update(review_rounds=int(ls.get("review_rounds", 0)) + 1, invalid_rounds=invalid)
            ls.pop("prepared_key", None)  # prepare again: the package carries the error (#62)
            self._save_ls(step, n, ls)
            return self._prepare(ctx, step, n, ls, str(self._key(ctx, step, rel)))
        self.warnings += w
        return self._decide(rel)

    def _decide(self, rel: str) -> dict[str, Any] | None:
        from tsl.harness.decide_service import decide

        _, d, w = decide(self.rt, self.comp, rel)
        self.warnings += w
        step = rel.rsplit("/", 1)[-1].removesuffix(".md")
        if d.outcome in ("PASS", "PASS-WITH-FINDINGS"):
            self.notes.append(f"{step} passed ({d.outcome}, {d.band})")
        elif d.outcome == "RETRY":
            self.notes.append(f"{step} needs a retry: {', '.join(d.gate_failures) or 'review'}")
        else:
            self.notes.append(f"{step}: {d.outcome}")
        return None

    def _asking_step(self, ctx: RunCtx) -> tuple[str | None, int | None]:
        """The step whose decision asked (NEEDS-INPUT), latest first."""
        for s in reversed(ctx.state["steps"]):
            a = latest(s) if s.get("attempts") else None
            if a is not None and a.get("outcome") == "NEEDS-INPUT":
                return str(s["id"]), int(a["n"])
        return None, None

    def _ask(self, ctx: RunCtx, missing: list[str]) -> dict[str, Any]:
        """The blocking questions resume still finds without a valid answer (E-RUN-03): no
        answer, or an answer without a valid answered_by. Every open question when the error
        does not list them."""
        path = ctx.comp.path(ctx.questions_rel())
        open_qs = {q["id"]: q for q in questions_md.unanswered(path, self.run_id)}
        eff: dict[str, Any] = {}
        if missing and path.is_file():
            try:
                eff = questions_md.effective(questions_md.load(path).get("questions", []))
            except TslError:
                eff = {}
        qs: list[dict[str, Any]] = []
        for qid in missing or list(open_qs):
            qs.append(
                open_qs.get(qid)
                or {
                    "id": qid,
                    "question": str((eff.get(qid) or {}).get("question") or "")[:300],
                    "blocking": True,
                    "cite": f"runs/{self.run_id}/open-questions.md#{qid.lower()}",
                }
            )
        blocking = sum(1 for q in qs if q.get("blocking"))
        msg, _ = plain.paused_input(blocking, self.run_id, ctx.questions_rel())
        questions = [{k: q.get(k) for k in ("id", "question", "blocking", "cite")} for q in qs]
        step, n = self._asking_step(ctx)
        if not self._asked(step, n, [str(q["id"]) for q in qs]):  # a repeat records nothing
            phase(self.rt, self.comp, ctx.state, step, n, "ask")
            self.warnings += ask_raised(self.rt, self.comp, self.run_id, step, n, qs)
        return self._run_level("ask", msg, ask={"questions": questions, "answers_to": None})

    def _asked(self, step: str | None, n: int | None, ids: list[str]) -> bool:
        """True when this call hands out the same questions as the last ask; else remember."""
        p = self.comp.path(f"{instructions_dir(self.run_id)}/ask.json")
        now = {"step": step, "attempt": n, "ids": ids}
        if p.is_file() and dict(read_json(p)) == now:
            return True
        p.parent.mkdir(parents=True, exist_ok=True)
        write_json(p, now)
        return False


def code_next(
    rt: Runtime, comp: Companion, run_id: str, *, take_over: bool = False
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    """The next-action.v2 instruction for a run in code mode, and warnings.

    --take-over: another session holds the run (D2). Take it over first, as
    `tsl state resume --take-over` does, then carry on from the files on disk."""
    if take_over:
        from tsl.state.service import resume

        resume(rt, comp, run_id, take_over=True)
    loop = _Loop(rt, comp, run_id)
    return loop.run(), loop.warnings
