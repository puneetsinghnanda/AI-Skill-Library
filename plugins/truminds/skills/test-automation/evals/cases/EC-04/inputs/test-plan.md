---
schema: test-plan.v1
run_id: run_01JB2C3D4E5F6G7H8J9KMNPQRS
step: tplan
attempt: 1
skill: test-plan@1.0.0
inputs:
- path: artifacts/ABC-163/run_01JB2C3D4E5F6G7H8J9KMNPQRS/split.md
  sha256: 9e82881072b68b9b2d4b2610b5ad2642c240730f9a8e1bd3940241bfc0245aa2
pack_sha:
  sample-orders: 0472a951131fb46c7547e1400c4a3d5d7d7202f4
claims: []
trace:
- REQ-1
known: []
assumed: []
unknown: []
tests:
- id: TP-1
  title: Export returns CSV
  covers:
  - S-1/AC1
  level: integration
- id: TP-2
  title: Archived orders left out
  covers:
  - S-1/AC2
  level: unit
---
# Test plan: ABC-163

## Scope
Invented fixture.

## Tests
- TP-1 Export returns CSV covers S-1/AC1 (integration)
- TP-2 Archived orders left out covers S-1/AC2 (unit)

## Known
- Every acceptance criterion has a test.

## Assumed
- None.

## Unknown
- None.
