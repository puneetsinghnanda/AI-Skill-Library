---
schema: intent.v1
run_id: run_01JB2C3D4E5F6G7H8J9KMNPQRS
step: req
attempt: 1
skill: requirement-review@1.0.0
inputs:
- path: artifacts/ABC-453/run_01JB2C3D4E5F6G7H8J9KMNPQRS/ticket.md
  sha256: 5b89b92f23bc73412e54d6777ee6875d2ccd44cd15b490522ca1b4681e5e4343
pack_sha:
  sample-orders: e63b11871362fcb6d8b91356f7c9d6a3d0122a18
claims: []
trace:
- REQ-1
known:
- REQ-1
assumed: []
unknown: []
requirements:
- id: REQ-1
  title: Store delivery slot
  type: functional
  status: known
  statement: Each order stores the delivery slot the customer picked.
  cites:
  - artifacts/ABC-453/run_01JB2C3D4E5F6G7H8J9KMNPQRS/ticket.md#L12
unknowns: []
questions: []
glossary: []
---
# Requirements review: ABC-453

## Summary
Invented fixture.

## Requirements
- REQ-1 Store delivery slot (known): Each order stores the delivery slot the customer picked.

## Known
- REQ-1: stated in the ticket.

## Assumed
- None.

## Unknown
- None.

## Open questions
- None.

## Out of scope
- None.
