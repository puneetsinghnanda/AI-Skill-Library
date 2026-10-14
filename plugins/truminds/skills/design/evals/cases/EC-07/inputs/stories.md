---
schema: stories.v1
run_id: run_01JB2C3D4E5F6G7H8J9KMNPQRS
step: split
attempt: 1
skill: story-split@1.0.0
inputs:
- path: artifacts/ABC-463/run_01JB2C3D4E5F6G7H8J9KMNPQRS/req.md
  sha256: 39d1e982a287aa6f1af15cb1c6386aecc0088bbbe37799d0ef025e2557cb861b
pack_sha:
  sample-orders: 7fcdb863ee081bea543c0d0fb8a3540547829fac
claims: []
trace:
- REQ-1
known:
- S-1
assumed: []
unknown: []
stories:
- id: S-1
  title: Gift message on an order
  trace:
  - REQ-1
  acceptance_criteria:
  - id: AC1
    text: Given an order, when the customer adds a gift message, then it is printed on the packing slip
---
# Stories: ABC-463

## Stories
- S-1 Gift message on an order (traces REQ-1)

## Known
- All stories trace to known requirements.

## Assumed
- None.

## Unknown
- None.
