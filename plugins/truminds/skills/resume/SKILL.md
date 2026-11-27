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

## Code loop (when "data.loop" is "code")
Run `tsl next <run_id> --json` and show "data.say" to the user unchanged. Then by
"data.action":
- run_step or fix: invoke the skill named in "data.skill" with "data.artifact_path" as its
  argument, and tell it to read "data.instruction_path" first. It writes "data.artifact_path"
  only (for fix: only what each "data.fix" item names, no full rewrite).
  If run_step has "data.runner", do not invoke "data.skill". Invoke the `step` skill instead,
  with `<data.artifact_path> --context <data.runner.context>`: it runs the step in a forked
  subagent and answers with the path.
- run_reviewer: invoke the `review` skill on "data.artifact_path".
- ask: ask "data.ask.questions" with AskUserQuestion (the hook records the answers).
- pause_approval, done, stopped: stop.
After run_step, fix, run_reviewer or ask, run `tsl next <run_id> --json` again.
If "ok" is false, show "message" and "next" and stop.
Never run verify, review record, decide or pr yourself: tsl next does them.

## Model loop (when "data.loop" is "model")
1. Run `tsl next <run_id> --json` and read "data.action".
2. run_skill: invoke the skill named in "data.skill" with "data.artifact_path" as its argument
   (its preamble runs `tsl verify <path> --inputs` from it). Give it "data.inputs",
   "data.feedback" and "data.answers". It must write exactly "data.artifact_path".
   Also give it "data.open_questions": questions of this run still unanswered. It must not
   raise them again; to refer to one it cites the question's "cite"
   (runs/<run_id>/open-questions.md#q-05), never the question id in prose alone.
   If the post-write hook blocks the write, fix what it says and write again.
3. Run `tsl verify <artifact_path> --json`. It runs every check, including the verifier
   container (H3) for steps that change code; the post-write hook ran only the fast checks.
   If "ok" is false with any failing gate (E-CHK-*, E-SEC-*, E-POL-*), skip the review and
   go straight to step 5: decide records the review as skipped, then retries the step with
   feedback or stops the run. Do not investigate with other tools while a step is open; the
   pre-tool hook refuses tools outside the step's list.
   Otherwise run the `review` skill on "data.artifact_path". The reviewer writes its JSON to
   `runs/<run_id>/review-input/<step>.review.json` and answers with that path; it records nothing.
4. Run
   `tsl review record <artifact_path> --file runs/<run_id>/review-input/<step>.review.json --json`.
   Only if the reviewer answered with the JSON itself (its write was refused), first save
   that JSON, unchanged, with the Write tool to that path.
   (A file, not stdin: long JSON on a shell command line breaks some shell wrappers.)
   On E-REV-02 or E-REV-05, run the `review` skill again with only the same <artifact_path>
   you recorded (the error output has no path of its own), and record again. tsl puts the
   error (and for E-REV-05 each failing citation and why) and the refused review in the new
   reviewer's package. Never pass the error as skill arguments (its quotes and braces make
   the skill's shell command fail) and never message the reviewer.
   On E-REV-02 the JSON did not match review.v1: stay within the review budget (retry.review,
   2 by default). If it still fails, run
   `tsl review record <artifact_path> --unavailable "reviewer output still invalid (E-REV-02)" --json`,
   with exactly that reason: never put the error message itself on the command line.
   On E-REV-05 some citations do not verify: tsl counts these rounds itself (retry.record) and
   records the review once they are used, so keep going until it is recorded; never use
   --unavailable for E-REV-05.
   E-REV-06 is a warning only: tsl moved a citation to the one place its quote is.
   Never edit the review JSON yourself.
5. Run `tsl decide <artifact_path> --json`. Show its status line to the user.
   Then go back to step 1, whatever the outcome.
6. run_decide: go straight to step 5.
7. open_pr: run `tsl pr <run_id> --json`, then go back to step 1.
8. pause_input, pause_approval, done, stopped: show "message" and "next" and stop.
Never decide pass or fail yourself. Never edit state.json, records, approvals or open-questions.md.
