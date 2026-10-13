---
schema: intent.v1
run_id: run_01JB2C3D4E5F6G7H8J9KMNPQRS
step: req
attempt: 1
skill: requirement-review@1.0.0
inputs:
- path: artifacts/ABC-213/run_01JB2C3D4E5F6G7H8J9KMNPQRS/ticket.md
  sha256: 0f726f8d0da6d42a8b62057962610f4ed871359bc482010499eedb42fa767810
- path: context/intent-baseline.md
  sha256: e099fcea51df536a60630513595a1a51c7051d66586d7813bd2235249e23dff7
pack_sha:
  sample-orders: 8e50bdaf8524f9e9ed9b410e48a0f07d4be2a0b6
claims: []
trace: &id001
- REQ-1
known: *id001
assumed: []
unknown: []
requirements:
- id: REQ-1
  title: Refund
  type: functional
  status: known
  statement: Refunds are sent through the payment provider.
  cites:
  - artifacts/ABC-213/run_01JB2C3D4E5F6G7H8J9KMNPQRS/ticket.md#L12
unknowns: []
questions: []
glossary: []
---
# Requirements review: ABC-213

## Summary
Invented fixture.

## Requirements
- REQ-1 Refund (known): Refunds are sent through the payment provider.

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
