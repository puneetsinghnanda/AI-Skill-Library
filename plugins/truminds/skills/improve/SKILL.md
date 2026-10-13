---
name: improve
description: Improve one skill from its improvement report, starting with a failing eval case. Only when the user types /truminds:improve.
argument-hint: <skill>
disable-model-invocation: true
allowed-tools: Bash(tsl *), Read, Grep, Glob, Write, Edit
---
Improvement plan from tsl (do not edit):
!`tsl improve plan $0 --json`

If "ok" is false, show "message" and "next" to the user and stop.

Show "data.top_issues" and ask the user which flag to work on (or "owner-initiated"). Then follow
these steps in order and stop at the first failure:
1. Write the failing case first: run `tsl improve case <skill> --id <new case id> --json`, then fill the
   scaffolded case with invented data only (the sample order system, example.com addresses, FAKE-KEY-* keys).
   Describe the failure pattern in generic words; never copy text from a run, ticket, artifact or client code.
2. Before: run /truminds:eval for the current version. The new case must fail. If it passes, it does not
   reproduce the problem: stop and say so.
3. Change only files inside plugins/truminds/skills/<skill>/ (SKILL.md, rubric.md, checks.yaml, skill.yaml).
   Bump the version (patch for wording, minor for behaviour, major for a schema change) and add a CHANGELOG entry.
4. After: run /truminds:eval for the new version, all cases.
5. Run `tsl improve check <skill> --json`. Show the result. If it fails (E-IMP-01 to E-IMP-05), fix and repeat from 3.
6. Only when the user confirms, run `tsl improve pr <skill> --json` and show the PR link.
Never edit eval results, other skills, workflows or the harness. Never write to Jira or any client system.
