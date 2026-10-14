---
schema: intent.v1
run_id: run_01JB2C3D4E5F6G7H8J9KMNPQRS
step: req
attempt: 1
skill: requirement-review@1.0.0
inputs:
- path: artifacts/ABC-475/run_01JB2C3D4E5F6G7H8J9KMNPQRS/ticket.md
  sha256: 275e32f8b5ca7c11f0268386e6b4213037c4f84cbc34a2d3003dc72bdffa3e98
pack_sha:
  sample-orders: 140836f9fd16b7f065f5155f237b705bc2d64a48
claims: []
trace:
- REQ-1
known:
- REQ-1
assumed: []
unknown: []
requirements:
- id: REQ-1
  title: Dispatched email
  type: functional
  status: known
  statement: Customers get an email when their order is dispatched.
  cites:
  - artifacts/ABC-475/run_01JB2C3D4E5F6G7H8J9KMNPQRS/ticket.md#L12
unknowns: []
questions: []
glossary:
- term: dispatched
  found: false
---
# Requirements review: ABC-475

## Summary
Invented fixture.

## Requirements
- REQ-1 Dispatched email (known): Customers get an email when their order is dispatched.

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
