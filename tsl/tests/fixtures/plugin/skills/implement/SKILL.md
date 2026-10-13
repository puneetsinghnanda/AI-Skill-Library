---
name: implement
description: Implements a ticket in the product repo. Use only as a step of a Truminds workflow run.
argument-hint: <artifact path from tsl next>
user-invocable: false
allowed-tools: Bash(tsl verify *), Read, Grep, Glob, Write, Edit, Bash(npm test*)
---

Step context from tsl (do not edit):
!`tsl verify $0 --inputs --json`

## Job
Test fixture.

## Inputs
data.inputs.

## Rules
Stay in scope.

## Method
Edit code.

## Output
change.v1.

## If this is a retry
Fix failures.

## Hand-over
Write once.
