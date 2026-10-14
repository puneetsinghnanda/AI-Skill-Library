---
schema: intent.v1
run_id: run_01JB2C3D4E5F6G7H8J9KMNPQRS
step: req
attempt: 1
skill: requirement-review@1.0.0
inputs:
- path: artifacts/ABC-473/run_01JB2C3D4E5F6G7H8J9KMNPQRS/ticket.md
  sha256: f4703cbf5eca8972979ac99e65422e5228d5d07ba608a9410fdb56b83c8b7bb8
pack_sha:
  sample-orders: c795a9f3e072a9e92d7031e746f838c534547e0f
claims: []
trace:
- REQ-1
known: []
assumed: []
unknown:
- U-1
questions:
- id: Q-01
  blocking: true
  ask: product owner
  text: Which export is broken and what is wrong with it?
  evidence: []
requirements:
- id: REQ-1
  title: Fix the export
  type: functional
  status: unknown
  statement: Fix the export.
  cites:
  - artifacts/ABC-473/run_01JB2C3D4E5F6G7H8J9KMNPQRS/ticket.md#L12
unknowns:
- id: U-1
  text: The ticket does not say which export or what fails.
  question: Q-01
glossary: []
---
# Requirements review: ABC-473

## Summary
Invented fixture.

## Requirements
- REQ-1 Fix the export (unknown): Fix the export.

## Known
- None.

## Assumed
- None.

## Unknown
- U-1: The ticket does not say which export or what fails.

## Open questions
- Q-01 (blocking, product owner): Which export is broken and what is wrong with it?

## Out of scope
- None.
