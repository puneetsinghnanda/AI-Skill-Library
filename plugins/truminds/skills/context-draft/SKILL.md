---
name: context-draft
description: Draft one judgement section of the context pack for tech lead review. Only when the user types /truminds:context-draft.
argument-hint: <section>
disable-model-invocation: true
allowed-tools: Bash(tsl *), Read, Grep, Glob, Write, Edit
---
Draft package from tsl (do not edit):
!`tsl context draft-prepare $0 --json`

If "ok" is false, show "message" and "next" and stop.
Write only the file named in data.path. Keep its front matter; set status: drafted, origin: ai-draft.
Start every block you write with <!-- tsl:draft id=D-<n> -->.
Every heading gets an anchor {#kebab-id}. Every block that states a fact ends with a Sources: line
citing data.facts ids or product files with line numbers. If you cannot cite it, write it as a question
under "## Open points {#open-points}" instead.
Never copy secrets, personal data, data values or client names. Stay within data.budget_tokens.
Then run `tsl context build --check --sections $0 --json` and fix every error it lists.
