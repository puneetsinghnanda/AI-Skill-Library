---
schema: triage.v1
run_id: run_01JB2C3D4E5F6G7H8J9KMNPQRS
step: triage
attempt: 1
skill: defect-triage@1.0.0
inputs:
- path: artifacts/ABC-432/run_01JB2C3D4E5F6G7H8J9KMNPQRS/ticket.md
  sha256: c8d7daba73d806e297f1c0229332a0cf57a6e45aecf4ffb7d6743fd51ba33e9b
pack_sha:
  sample-library: 9018505da089c872b904572a4ac18fe71b9ad287
claims: []
trace: []
known: []
assumed: []
unknown: []
candidates:
- component: module:sample-library:api/src/loans
  likelihood: high
  cites:
  - artifacts/ABC-432/run_01JB2C3D4E5F6G7H8J9KMNPQRS/ticket.md#L12
  - context/generated/module-map.json#module:sample-library:api/src/loans
---
# Defect triage: ABC-432

## Summary
Invented fixture.

## Candidates
- module:sample-library:api/src/loans (high)

## Known
- Candidates cite the ticket and the module map.

## Assumed
- None.

## Unknown
- None.
