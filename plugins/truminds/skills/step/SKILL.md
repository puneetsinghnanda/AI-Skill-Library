---
name: step
description: Runs one workflow step in a forked subagent with a fresh context. Use only from the run loop, when tsl next returns data.runner.
argument-hint: <artifact path> --context <artifacts|full>
context: fork
agent: truminds:step-runner
user-invocable: false
allowed-tools: Bash(tsl step brief *), Bash(tsl verify *), Read, Grep, Glob, Write, Edit
---
Step brief from tsl:
!`tsl step brief $ARGUMENTS`

If the text above does not start with "# Step brief", it is an error from tsl: answer with its
message and stop. Write nothing.
