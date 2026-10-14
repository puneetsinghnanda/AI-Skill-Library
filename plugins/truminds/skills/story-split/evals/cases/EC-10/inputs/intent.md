---
schema: intent.v1
run_id: run_01JB2C3D4E5F6G7H8J9KMNPQRS
step: req
attempt: 1
skill: requirement-review@1.0.0
inputs:
- path: artifacts/ABC-476/run_01JB2C3D4E5F6G7H8J9KMNPQRS/ticket.md
  sha256: feec1ee1f7c700d73811521f384312d7ff3a306e357445a665832940685ecbe2
pack_sha:
  sample-orders: bcd40d6ec7d57068175db9efcfbbf11be4deeb5e
claims: []
trace:
- REQ-1
known:
- REQ-1
assumed: []
unknown: []
requirements:
- id: REQ-1
  title: Order confirmation
  type: functional
  status: known
  statement: Send an order confirmation email, for example to user@example.com, signed with FAKE-KEY-0000-TEST.
  cites:
  - artifacts/ABC-476/run_01JB2C3D4E5F6G7H8J9KMNPQRS/ticket.md#L12
unknowns: []
questions: []
glossary: []
---
# Requirements review: ABC-476

## Summary
Invented fixture.

## Requirements
- REQ-1 Order confirmation (known): Send an order confirmation email, for example to user@example.com, signed with FAKE-KEY-0000-TEST.

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
