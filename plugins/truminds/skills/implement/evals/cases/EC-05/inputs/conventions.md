---
schema: context-section.v1
section: conventions
owner: tl-7a1c
origin: human
status: reviewed
verified_at:
  sample-support: d7e64ccb9f00d25c7602a97693214588be7cbf2f
---
# Conventions {#conventions}

## Code style {#code-style}
JavaScript with ESLint. Route handlers live in api/src/routes and call one service function each.
Sources: sample-support:api/.eslintrc.json#L1

## Errors {#errors}
Handlers return JSON errors with a code and a message. Never return stack traces.
Sources: sample-support:api/src/routes/errors.js#L4
