---
name: demo-step
description: Writes a one-line demo artifact. Use only as a step of the tsl-spike demo run, when tsl names demo-step as the next step.
argument-hint: <artifact path from tsl next>
user-invocable: false
allowed-tools: Bash(tsl verify *), Read, Grep, Glob, Write
---

Step context from tsl (do not edit):
!`tsl verify $0 --inputs --json`

If the JSON above has "ok": false, show its "message" and "next" to the user and stop. Write nothing.

## Job
Write the file at data.artifact_path with this exact content, creating folders as needed:

# Demo artifact
Spike S-09 wrote this file.

## Hand-over
Write the file once. Do not run checks, the review or the decision.
