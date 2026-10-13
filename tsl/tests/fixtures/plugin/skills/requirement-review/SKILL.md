---
name: requirement-review
description: Reviews one ticket against the intent baseline and writes an intent.v1 artifact. Use only as a step of a Truminds workflow run, when tsl names requirement-review as the next step.
argument-hint: <artifact path from tsl next>
user-invocable: false
allowed-tools: Bash(tsl verify *), Read, Grep, Glob, Write
---

Step context from tsl (do not edit):
!`tsl verify $0 --inputs --json`

If the JSON above has "ok": false, show its "message" and "next" to the user and stop. Write nothing.

## Job
Turn one ticket into numbered, testable requirements (test fixture).

## Inputs
Read data.inputs.

## Rules
Never invent a value.

## Method
Follow the steps.

## Output
intent.v1 front matter and the seven body sections.

## If this is a retry
Fix data.retry.failures, then data.retry.findings.

## Hand-over
Write the file once to data.artifact_path.
