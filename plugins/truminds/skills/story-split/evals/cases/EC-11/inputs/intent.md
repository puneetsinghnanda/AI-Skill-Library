---
schema: intent.v1
run_id: run_01JB2C3D4E5F6G7H8J9KMNPQRS
step: req
attempt: 1
skill: requirement-review@1.0.0
inputs:
- path: artifacts/ABC-581/run_01JB2C3D4E5F6G7H8J9KMNPQRS/ticket.md
  sha256: 5d1f0c7a3b9e2d4f6a8c0e1b3d5f7a9c2e4b6d8f0a1c3e5b7d9f1a3c5e7b9d0f
pack_sha:
  sample-clinic: 8a41c2e7d9b03f56e1a7c4d2b8f09e3a6c5d1b72
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
  title: Last visit column
  type: functional
  status: known
  statement: The patient list shows a Last visit column for each patient.
  cites:
  - artifacts/ABC-581/run_01JB2C3D4E5F6G7H8J9KMNPQRS/ticket.md#L12
- id: REQ-2
  title: Last visit source
  type: functional
  status: known
  statement: Last visit is the start of the patient's latest appointment with status Completed; a patient
    with no Completed appointment shows a dash.
  cites:
  - artifacts/ABC-581/run_01JB2C3D4E5F6G7H8J9KMNPQRS/ticket.md#L13
- id: REQ-3
  title: Hospital time zone
  type: constraint
  status: known
  statement: Last visit date is the calendar date in hospital time zone Asia/Kolkata.
  cites:
  - artifacts/ABC-581/run_01JB2C3D4E5F6G7H8J9KMNPQRS/ticket.md#L14
unknowns: []
questions: []
glossary: []
---
# Requirements review: ABC-581

## Summary
Invented fixture on an invented clinic system. Appointment start times are stored in UTC.

## Requirements
- REQ-1 Last visit column (known): The patient list shows a Last visit column for each patient.
- REQ-2 Last visit source (known): Last visit is the start of the patient's latest appointment with status
  Completed; a patient with no Completed appointment shows a dash.
- REQ-3 Hospital time zone (known): Last visit date is the calendar date in hospital time zone Asia/Kolkata.

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
