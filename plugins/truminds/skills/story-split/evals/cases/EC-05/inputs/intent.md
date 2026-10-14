---
schema: intent.v1
run_id: run_01JB2C3D4E5F6G7H8J9KMNPQRS
step: req
attempt: 1
skill: requirement-review@1.0.0
inputs:
- path: artifacts/ABC-471/run_01JB2C3D4E5F6G7H8J9KMNPQRS/ticket.md
  sha256: b7e489a4022635304fe43b993e416103f59119268536af314d41e304e6e5d7a5
pack_sha:
  sample-support: bd09cf7e00e212de117768dc22311bc4a17d8e02
claims: []
trace:
- REQ-1
- REQ-2
known:
- REQ-1
- REQ-2
assumed: []
unknown: []
requirements:
- id: REQ-1
  title: First response p95
  type: non-functional
  status: known
  statement: Priority-1 tickets get a first response within 2 hours, measured at p95 over a calendar month.
  cites:
  - artifacts/ABC-471/run_01JB2C3D4E5F6G7H8J9KMNPQRS/ticket.md#L12
- id: REQ-2
  title: Breach flag
  type: functional
  status: known
  statement: A ticket without a first response after 2 hours shows a breach flag to agents.
  cites:
  - artifacts/ABC-471/run_01JB2C3D4E5F6G7H8J9KMNPQRS/ticket.md#L12
unknowns: []
questions: []
glossary: []
---
# Requirements review: ABC-471

## Summary
Invented fixture.

## Requirements
- REQ-1 First response p95 (known): Priority-1 tickets get a first response within 2 hours, measured at p95 over a calendar month.
- REQ-2 Breach flag (known): A ticket without a first response after 2 hours shows a breach flag to agents.

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
