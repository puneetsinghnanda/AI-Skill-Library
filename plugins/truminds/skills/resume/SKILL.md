---
name: resume
description: Resume a paused or interrupted Truminds run after questions are answered or a gate is approved. Only when the user types /truminds:resume.
argument-hint: <run_id>
disable-model-invocation: true
allowed-tools: Bash(tsl *), Agent, Read, Grep, Glob, Write, Edit
---
Run state from tsl (do not edit):
!`tsl state resume $0 --json`

If "ok" is false, show "message" and "next" to the user and stop.
(E-RUN-03 means a blocking question still has no valid answer; E-RUN-07 means a frozen answer was edited.
Show the question ids from "data" and stop. Never fill in answers yourself.)

Loop:
1. Run `tsl next <run_id> --json` and read "data.action".
2. run_skill: dispatch the step to its own subagent with the Agent tool. Use
   subagent_type "data.agent" (one agent per step skill; its tools are exactly that skill's
   allowed-tools). The prompt is "data.artifact_path" on the first line, then
   "feedback: <data.feedback>" and "answers: <data.answers>" for each that is not null.
   Nothing else: the agent reads its inputs itself. Do not run the step's skill here and do
   not read the inputs or the artifact yourself. Wait for its one-line reply. If the reply says
   the post-write hook blocked the write, dispatch it once more with that message added.
3. Run `tsl verify <artifact_path> --json`. It runs every check, including the verifier
   container (H3) for steps that change code; the post-write hook ran only the fast checks.
   If "ok" is false with any failing gate (E-CHK-*, E-SEC-*, E-POL-*), skip the review and
   go straight to step 5: decide records the review as skipped, then retries the step with
   feedback or stops the run. Do not investigate with other tools while a step is open; the
   pre-tool hook refuses tools outside the step's list.
   Otherwise run the `review` skill on "data.artifact_path". It only returns JSON; it records nothing.
4. Save that JSON, unchanged, with the Write tool to
   `runs/<run_id>/review-input/<step>.review.json`, then run
   `tsl review record <artifact_path> --file runs/<run_id>/review-input/<step>.review.json --json`.
   (A file, not stdin: long JSON on a shell command line breaks some shell wrappers.)
   On E-REV-02 the JSON did not match review.v1: run the `review` skill again, passing it
   the error "message", and record again. Stay within the review budget (retry.review,
   2 by default). If it still fails, run
   `tsl review record <artifact_path> --unavailable "<the error message>" --json`.
   Never write or edit the review JSON yourself.
5. Run `tsl decide <artifact_path> --json`. Show its status line to the user.
   Then go back to step 1, whatever the outcome.
6. run_decide: go straight to step 5.
7. open_pr: run `tsl pr <run_id> --json`, then go back to step 1.
8. pause_input, pause_approval, done, stopped: show "message" and "next" and stop.
Never decide pass or fail yourself. Never edit state.json, records, approvals or open-questions.md.
