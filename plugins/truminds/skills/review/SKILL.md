---
name: review
description: Harness review step for one artifact. Used by truminds workflows only.
context: fork
agent: truminds:reviewer
user-invocable: false
---
Review package from tsl (artifact, rubric, cited context sections):
!`tsl review prepare $ARGUMENTS --json`
