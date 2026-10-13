---
name: env-probe
description: Spike S-08 only. Shows whether TSL_SESSION_ID reaches skill injection and Bash. Only when the user types /tsl-spike:env-probe.
disable-model-invocation: true
allowed-tools: Bash(printenv *)
---
Injected before you read this (do not edit):
!`printenv TSL_SESSION_ID || echo "TSL_SESSION_ID not set in skill injection"`

Now run `printenv TSL_SESSION_ID` with the Bash tool and show both results to the user, labelled
"injection" and "bash". Do nothing else.
