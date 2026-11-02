---
schema: intent.v1
run_id: run_01JB2C3D4E5F6G7H8J9KMNPQRS
step: req
attempt: 1
skill: requirement-review@1.0.0
inputs:
- path: artifacts/ABC-582/run_01JB2C3D4E5F6G7H8J9KMNPQRS/ticket.md
  sha256: 9c2e4a6b8d0f1e3c5a7b9d1f3e5c7a9b0d2f4e6c8a1b3d5f7e9c0a2b4d6f8e1a
pack_sha:
  sample-clinic: 8a41c2e7d9b03f56e1a7c4d2b8f09e3a6c5d1b72
claims: []
trace: &id001
- REQ-1
- REQ-2
known: *id001
assumed: []
unknown: []
requirements:
- id: REQ-1
  title: Next appointment column
  type: functional
  status: known
  statement: The patient list shows a Next appointment column with the date of the patient's earliest future
    appointment with status Booked, or a dash when there is none.
  cites:
  - artifacts/ABC-582/run_01JB2C3D4E5F6G7H8J9KMNPQRS/ticket.md#L12
- id: REQ-2
  title: Last visit unchanged
  type: constraint
  status: known
  statement: The existing Last visit column is unchanged.
  cites:
  - artifacts/ABC-582/run_01JB2C3D4E5F6G7H8J9KMNPQRS/ticket.md#L13
unknowns: []
questions: []
glossary: []
---
# Requirements review: ABC-582

## Summary
Invented fixture on an invented clinic system. Last visit already shows the date of the latest Completed
appointment.

## Requirements
- REQ-1 Next appointment column (known): The patient list shows a Next appointment column with the date of
  the patient's earliest future appointment with status Booked, or a dash when there is none.
- REQ-2 Last visit unchanged (known): The existing Last visit column is unchanged.

## Known
- REQ-1: stated in the ticket.
- REQ-2: stated in the ticket.

## Assumed
- None.

## Unknown
- None.

## Open questions
- None.

## Out of scope
- None.
