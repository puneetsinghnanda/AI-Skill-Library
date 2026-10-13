---
schema: test-plan.v1
run_id: run_01JB2C3D4E5F6G7H8J9KMNPQRS
step: tplan
attempt: 1
skill: test-plan@1.0.0
inputs:
- path: artifacts/ABC-272/run_01JB2C3D4E5F6G7H8J9KMNPQRS/split.md
  sha256: c58b7d5a3b09fc820d569c417541f1d631aaf6c71dcdf8dd9e6812e636bf3d86
pack_sha:
  sample-orders: 773729fa3bbfaa60a11291d55941da2241d8addd
claims: []
trace:
- REQ-1
known: []
assumed: []
unknown: []
tests:
- id: TP-1
  title: Printed invoice looks right
  covers:
  - S-1/AC1
  level: manual
- id: TP-2
  title: Invoice total matches
  covers:
  - S-1/AC2
  level: unit
---
# Test plan: ABC-272

## Scope
Invented fixture.

## Tests
- TP-1 Printed invoice looks right covers S-1/AC1 (manual)
- TP-2 Invoice total matches covers S-1/AC2 (unit)

## Known
- Every acceptance criterion has a test.

## Assumed
- None.

## Unknown
- None.
