---
schema: context-section.v1
section: conventions
owner: tl-7a1c
origin: human
status: reviewed
verified_at:
  sample-orders: 4fcd2eecc9496508f60b49a0962d012e0ef12c90
---
# Conventions {#conventions}

## Code style {#code-style}
JavaScript with ESLint. Route handlers live in api/src/routes and call one service function each.
Sources: sample-orders:api/.eslintrc.json#L1

## Errors {#errors}
Handlers return JSON errors with a code and a message. Never return stack traces.
Sources: sample-orders:api/src/routes/errors.js#L4

## Data access {#data-access}
The web app never stores order data in the browser. All data goes through the api.
Sources: sample-orders:web/src/lib/api.js#L1
