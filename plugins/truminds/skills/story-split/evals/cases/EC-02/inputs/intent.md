---
schema: intent.v1
run_id: run_01JB2C3D4E5F6G7H8J9KMNPQRS
step: req
attempt: 1
skill: requirement-review@1.0.0
inputs:
- path: artifacts/ABC-202/run_01JB2C3D4E5F6G7H8J9KMNPQRS/ticket.md
  sha256: 8ced5db3722d41ca05e57cb8e3f54a14097aa566a1bd3187a44e610ce3e903ed
- path: context/intent-baseline.md
  sha256: 62fb51193236287898f28c52fe257d5d7fd2c3ba89744f072fe890509b6303ae
pack_sha:
  sample-orders: 7f206f5ec9892890def0dc2941a02e2012f6043a
claims: []
trace: &id001
- REQ-1
known: *id001
assumed: []
unknown:
- U-1
requirements:
- id: REQ-1
  title: Add a note
  type: functional
  status: known
  statement: Staff can add a text note to an order.
  cites:
  - artifacts/ABC-202/run_01JB2C3D4E5F6G7H8J9KMNPQRS/ticket.md#L12
unknowns:
- id: U-1
  text: Who may see internal notes is not stated
  question: Q-01
questions:
- id: Q-01
  blocking: false
  ask: product owner
  text: May customers see internal notes?
  why: Decides the visibility rule
  evidence:
  - artifacts/ABC-202/run_01JB2C3D4E5F6G7H8J9KMNPQRS/ticket.md#L12
  options:
  - Staff only
  - Staff and customer
  default: Staff only
glossary: []
---
# Requirements review: ABC-202

## Summary
Invented fixture.

## Requirements
- REQ-1 Add a note (known): Staff can add a text note to an order.

## Known
- REQ-1: stated in the ticket.

## Assumed
- None.

## Unknown
- U-1: visibility of notes. Raises Q-01.

## Open questions
- Q-01 (non-blocking, product owner): May customers see internal notes?

## Out of scope
- None.
