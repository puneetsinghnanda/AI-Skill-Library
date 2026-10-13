---
schema: intent.v1
run_id: run_01JB2C3D4E5F6G7H8J9KMNPQRS
step: req
attempt: 1
skill: requirement-review@1.0.0
inputs:
- path: artifacts/ABC-211/run_01JB2C3D4E5F6G7H8J9KMNPQRS/ticket.md
  sha256: 92de76d085aca604ad8bfe0e56aac4d9966b5ec15a934f0e4ed1d918f72a724e
- path: context/intent-baseline.md
  sha256: 9707520c50eaed04847be9739ae69001d8d93cd94339446cc227ddb30185120c
pack_sha:
  sample-orders: 5b539cac7e6c3925b31f4c455ab64fc3693497d3
claims: []
trace: &id001
- REQ-1
known: *id001
assumed: []
unknown: []
requirements:
- id: REQ-1
  title: Filter by status
  type: functional
  status: known
  statement: Customers can filter the order list by order status.
  cites:
  - artifacts/ABC-211/run_01JB2C3D4E5F6G7H8J9KMNPQRS/ticket.md#L12
unknowns: []
questions: []
glossary: []
---
# Requirements review: ABC-211

## Summary
Invented fixture.

## Requirements
- REQ-1 Filter by status (known): Customers can filter the order list by order status.

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
