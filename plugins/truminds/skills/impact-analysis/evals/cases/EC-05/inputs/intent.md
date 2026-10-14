---
schema: intent.v1
run_id: run_01JB2C3D4E5F6G7H8J9KMNPQRS
step: req
attempt: 1
skill: requirement-review@1.0.0
inputs:
- path: artifacts/ABC-451/run_01JB2C3D4E5F6G7H8J9KMNPQRS/ticket.md
  sha256: f3bebe04794efbf20d900c97487c967502c983f8d14e2dce32fad04d441354e8
pack_sha:
  sample-support: 6d483b0d431ee1c033c1f3750aaea92a967f5447
claims: []
trace:
- REQ-1
known:
- REQ-1
assumed: []
unknown: []
requirements:
- id: REQ-1
  title: First response p95
  type: non-functional
  status: known
  statement: Priority-1 tickets get a first response within 2 hours, measured at p95.
  cites:
  - artifacts/ABC-451/run_01JB2C3D4E5F6G7H8J9KMNPQRS/ticket.md#L12
unknowns: []
questions: []
glossary: []
---
# Requirements review: ABC-451

## Summary
Invented fixture.

## Requirements
- REQ-1 First response p95 (known): Priority-1 tickets get a first response within 2 hours, measured at p95.

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
