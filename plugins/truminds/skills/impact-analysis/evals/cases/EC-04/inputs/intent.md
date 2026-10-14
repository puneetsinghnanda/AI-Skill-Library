---
schema: intent.v1
run_id: run_01JB2C3D4E5F6G7H8J9KMNPQRS
step: req
attempt: 1
skill: requirement-review@1.0.0
inputs:
- path: artifacts/ABC-163/run_01JB2C3D4E5F6G7H8J9KMNPQRS/ticket.md
  sha256: c59a8d92a348f37535d25385ac874e710873073ccf4611b1352a9ef3ca2c68a3
pack_sha:
  sample-orders: 0472a951131fb46c7547e1400c4a3d5d7d7202f4
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
  title: CSV export
  type: functional
  status: known
  statement: A new endpoint returns one customer's orders as CSV.
  cites:
  - artifacts/ABC-163/run_01JB2C3D4E5F6G7H8J9KMNPQRS/ticket.md#L12
- id: REQ-2
  title: No archived orders
  type: functional
  status: known
  statement: Archived orders are not included in the export.
  cites:
  - artifacts/ABC-163/run_01JB2C3D4E5F6G7H8J9KMNPQRS/ticket.md#L16
unknowns: []
questions: []
glossary: []
---
# Requirements review: ABC-163

## Summary
Invented fixture.

## Requirements
- REQ-1 CSV export (known): A new endpoint returns one customer's orders as CSV.
- REQ-2 No archived orders (known): Archived orders are not included in the export.

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
