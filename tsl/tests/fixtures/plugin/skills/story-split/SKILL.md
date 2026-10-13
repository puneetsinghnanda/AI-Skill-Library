---
name: story-split
description: Splits an intent into stories. Use only as a step of a Truminds workflow run.
argument-hint: <artifact path from tsl next>
user-invocable: false
allowed-tools: Bash(tsl verify *), Read, Grep, Glob, Write
---

Step context from tsl (do not edit):
!`tsl verify $0 --inputs --json`

## Job
Test fixture.

## Inputs
data.inputs.

## Rules
No invented values.

## Method
Split.

## Output
stories.v1.

## If this is a retry
Fix failures.

## Hand-over
Write once.
