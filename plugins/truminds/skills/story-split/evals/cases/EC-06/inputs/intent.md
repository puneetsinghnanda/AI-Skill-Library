---
schema: intent.v1
run_id: run_01JB2C3D4E5F6G7H8J9KMNPQRS
step: req
attempt: 1
skill: requirement-review@1.0.0
inputs:
- path: artifacts/ABC-472/run_01JB2C3D4E5F6G7H8J9KMNPQRS/ticket.md
  sha256: 406d690529beebfbfcdba84a91d46f9e30c43f64591845565d6a62730d4df808
pack_sha:
  sample-library: c7767d2820ea5d6832b3730394cddb8a94fb4e90
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
  title: Renew once
  type: functional
  status: known
  statement: A member can renew a loan once.
  cites:
  - artifacts/ABC-472/run_01JB2C3D4E5F6G7H8J9KMNPQRS/ticket.md#L12
- id: REQ-2
  title: Loan limit
  type: constraint
  status: known
  statement: A member holds at most 5 loans.
  cites:
  - artifacts/ABC-472/run_01JB2C3D4E5F6G7H8J9KMNPQRS/ticket.md#L12
unknowns: []
questions: []
glossary: []
---
# Requirements review: ABC-472

## Summary
Invented fixture.

## Requirements
- REQ-1 Renew once (known): A member can renew a loan once.
- REQ-2 Loan limit (known): A member holds at most 5 loans.

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
