---
schema: intent.v1
run_id: run_01JB2C3D4E5F6G7H8J9KMNPQRS
step: req
attempt: 1
skill: requirement-review@1.0.0
inputs:
- path: artifacts/ABC-201/run_01JB2C3D4E5F6G7H8J9KMNPQRS/ticket.md
  sha256: 28d4ca2c71739e3a0570ce27da5d04a45f1c4049e49541f8d1e10cf5d258d244
- path: context/intent-baseline.md
  sha256: 14c009ff2117f31a397b10661a3d302d312b361be0f2d5efaa99a71a8f04ee35
pack_sha:
  sample-orders: 3f36a5649b4d7545324a1d7676d94189569e49ea
claims: []
trace: &id001
- REQ-1
- REQ-2
- REQ-3
known: *id001
assumed: []
unknown: []
requirements:
- id: REQ-1
  title: Add a note
  type: functional
  status: known
  statement: Staff can add a text note to an order.
  cites:
  - artifacts/ABC-201/run_01JB2C3D4E5F6G7H8J9KMNPQRS/ticket.md#L12
- id: REQ-2
  title: List notes
  type: functional
  status: known
  statement: The order page lists the notes of the order, newest first.
  cites:
  - artifacts/ABC-201/run_01JB2C3D4E5F6G7H8J9KMNPQRS/ticket.md#L13
- id: REQ-3
  title: Note length
  type: constraint
  status: known
  statement: A note holds at most 500 characters.
  cites:
  - artifacts/ABC-201/run_01JB2C3D4E5F6G7H8J9KMNPQRS/ticket.md#L14
unknowns: []
questions: []
glossary: []
---
# Requirements review: ABC-201

## Summary
Invented fixture.

## Requirements
- REQ-1 Add a note (known): Staff can add a text note to an order.
- REQ-2 List notes (known): The order page lists the notes of the order, newest first.
- REQ-3 Note length (known): A note holds at most 500 characters.

## Known
- REQ-1: stated in the ticket.
- REQ-2: stated in the ticket.
- REQ-3: stated in the ticket.

## Assumed
- None.

## Unknown
- None.

## Open questions
- None.

## Out of scope
- None.
