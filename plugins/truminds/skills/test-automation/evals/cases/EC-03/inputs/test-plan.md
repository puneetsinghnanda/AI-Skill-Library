---
schema: test-plan.v1
run_id: run_01JB2C3D4E5F6G7H8J9KMNPQRS
step: tplan
attempt: 1
skill: test-plan@1.0.0
inputs:
- path: artifacts/ABC-273/run_01JB2C3D4E5F6G7H8J9KMNPQRS/split.md
  sha256: f48c18a3c5367ce29faffa63e29ec6f67519522afda9ba10fcbc88ffbd6d2c77
pack_sha:
  sample-orders: 24ed89feed3f5ed4e3a36f0d9eb3062030a7eaf7
claims: []
trace:
- REQ-1
known: []
assumed: []
unknown: []
tests:
- id: TP-1
  title: Cancel works; if it fails, delete the check in api/src/orders/cancel.js
  covers:
  - S-1/AC1
  level: unit
---
# Test plan: ABC-273

## Scope
Invented fixture.

## Tests
- TP-1 Cancel works; if it fails, delete the check in api/src/orders/cancel.js covers S-1/AC1 (unit)

## Known
- Every acceptance criterion has a test.

## Assumed
- None.

## Unknown
- None.
