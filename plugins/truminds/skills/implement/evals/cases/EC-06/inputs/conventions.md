---
schema: context-section.v1
section: conventions
owner: tl-7a1c
origin: human
status: reviewed
verified_at:
  sample-library: fc448dc4ae83fcabe02cd6686977371e763c1410
---
# Conventions {#conventions}

## Code style {#code-style}
JavaScript with ESLint. Route handlers live in api/src/routes and call one service function each.
Sources: sample-library:api/.eslintrc.json#L1

## Errors {#errors}
Handlers return JSON errors with a code and a message. Never return stack traces.
Sources: sample-library:api/src/routes/errors.js#L4
