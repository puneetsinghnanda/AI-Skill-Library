---
name: status
description: Show the status of a Truminds run, or of this user's runs in the current companion repo. Only when the user types /truminds:status.
argument-hint: [run_id]
disable-model-invocation: true
allowed-tools: Bash(tsl *), Read
---
Run status from tsl (do not edit):
!`tsl state show $0 --json`

If "ok" is false, show "message" and "next" to the user and stop.

Otherwise show "data.runs" as a short table: run id, ticket, workflow, status, step, attempt,
updated at and what the run is waiting on. Then show "next".
For a paused run, say exactly who must act:
- PAUSED_INPUT: answer the blocking questions in runs/<run_id>/open-questions.md, then /truminds:resume <run_id>.
- PAUSED_APPROVAL: the approver fills the gate entry in runs/<run_id>/approvals.md and runs `tsl approve <run_id> <gate>`.
Do not change any file. Do not start, resume or decide anything from this command.
