---
name: run
description: Spike S-09 only. Runs the demo loop against the stub tsl. Only when the user types /tsl-spike:run.
argument-hint: <workflow> <ticket>
disable-model-invocation: true
allowed-tools: Bash(tsl *), Read, Grep, Glob, Write, Edit
---
Run state from tsl (do not edit):
!`tsl state start $0 $1 --json`

If "ok" is false, show "message" and "next" to the user and stop.

Loop:
1. Run `tsl next <run_id> --json` and read "data.action".
2. run_skill: use the skill named in "data.skill". It must write exactly "data.artifact_path".
3. Run the `review` skill on "data.artifact_path". Then run `tsl review record <artifact_path>` with the
   reviewer's JSON on standard input.
4. Run `tsl decide <artifact_path> --json`. Show its status line to the user. Go back to step 1.
5. done or stopped: show "message" and stop.
Never decide pass or fail yourself.
