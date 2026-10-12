---
name: run
description: Start a Truminds workflow on a ticket. Only when the user types /truminds:run.
argument-hint: <workflow> <ticket>
disable-model-invocation: true
allowed-tools: Bash(tsl *), Read, Grep, Glob, Write, Edit
---

Run state from tsl (do not edit):
!`tsl state start $0 $1 --json`

If the JSON above has "ok": false, show its "message" and "next" to the user and stop.

Otherwise loop until tsl says the run is finished:
1. Run `tsl next <run_id> --json`. It names the next skill and its input files.
2. Use that skill to produce the artifact at the path tsl gives.
3. Run the `review` skill on the artifact.
4. Run `tsl decide <artifact> --json` and do exactly what its "next" field says
   (continue, retry with the findings, pause for input, pause for approval, stop).
Never decide pass or fail yourself.
