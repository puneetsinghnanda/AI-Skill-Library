---
schema: test-plan.v1
run_id: run_01JB2C3D4E5F6G7H8J9KMNPQRS
step: tplan
attempt: 1
skill: test-plan@1.0.0
inputs:
- path: artifacts/ABC-271/run_01JB2C3D4E5F6G7H8J9KMNPQRS/split.md
  sha256: c37970849942a5483f4602ed8ac2e6a663b63536cd869704a25c5b3fd0392fa5
pack_sha:
  sample-orders: c4171c93fd9ce1d1effd05f17c4e5b1731e32b05
claims: []
trace:
- REQ-1
known: []
assumed: []
unknown: []
tests:
- id: TP-1
  title: Add note stores it
  covers:
  - S-1/AC1
  level: unit
- id: TP-2
  title: Long note rejected
  covers:
  - S-1/AC2
  level: unit
- id: TP-3
  title: Notes listed newest first
  covers:
  - S-2/AC1
  level: e2e
---
# Test plan: ABC-271

## Scope
Invented fixture.

## Tests
- TP-1 Add note stores it covers S-1/AC1 (unit)
- TP-2 Long note rejected covers S-1/AC2 (unit)
- TP-3 Notes listed newest first covers S-2/AC1 (e2e)

## Known
- Every acceptance criterion has a test.

## Assumed
- None.

## Unknown
- None.
