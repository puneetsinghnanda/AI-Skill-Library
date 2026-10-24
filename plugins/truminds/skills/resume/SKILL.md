---
name: resume
description: Resume a paused or interrupted Truminds run after questions are answered or a gate is approved. Only when the user types /truminds:resume.
argument-hint: <run_id>
disable-model-invocation: true
allowed-tools: Bash(tsl *), Read, Grep, Glob, Write, Edit
---
Run state from tsl (do not edit):
!`tsl state resume $0 --json`

If "ok" is false, show "message" and "next" to the user and stop.
(E-RUN-03 means a blocking question still has no valid answer; E-RUN-07 means a frozen answer was edited.
Show the question ids from "data" and stop. Never fill in answers yourself.)

Loop:
1. Run `tsl next <run_id> --json` and read "data.action".
2. run_skill: use the skill named in "data.skill". Give it "data.inputs",
   "data.feedback" and "data.answers". It must write exactly "data.artifact_path".
   If the post-write hook blocks the write, fix what it says and write again.
3. Run the `review` skill on "data.artifact_path". It only returns JSON; it records nothing.
4. Pipe that JSON, unchanged, to `tsl review record <artifact_path> --json` (on stdin).
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
