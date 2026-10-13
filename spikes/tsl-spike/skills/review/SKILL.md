---
name: review
description: Spike review step for one artifact. Used by the tsl-spike demo run only.
context: fork
agent: tsl-spike:reviewer
user-invocable: false
---
Review package from tsl (artifact, rubric, cited context sections):
!`tsl review prepare $ARGUMENTS --json`
