---
schema: intent.v1
run_id: run_01JB2C3D4E5F6G7H8J9KMNPQRS
step: req
attempt: 1
skill: requirement-review@1.0.0
inputs:
- path: artifacts/ABC-456/run_01JB2C3D4E5F6G7H8J9KMNPQRS/ticket.md
  sha256: 1181d3b83a2872b7a3d13c3c9c41f22fa2f6791bef55e1dd5702f0bdc1e16b17
pack_sha:
  sample-orders: 4180edb983d3ab2e8fbeb93784cd0c5618995be5
claims: []
trace:
- REQ-1
known:
- REQ-1
assumed: []
unknown: []
requirements:
- id: REQ-1
  title: Carrier webhook
  type: functional
  status: known
  statement: Shipment updates arrive from the carrier webhook signed with FAKE-KEY-0000-TEST; send alerts to user@example.com.
  cites:
  - artifacts/ABC-456/run_01JB2C3D4E5F6G7H8J9KMNPQRS/ticket.md#L12
unknowns: []
questions: []
glossary: []
---
# Requirements review: ABC-456

## Summary
Invented fixture.

## Requirements
- REQ-1 Carrier webhook (known): Shipment updates arrive from the carrier webhook signed with FAKE-KEY-0000-TEST; send alerts to user@example.com.

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
