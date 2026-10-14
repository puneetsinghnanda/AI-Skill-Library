---
schema: stories.v1
run_id: run_01JB2C3D4E5F6G7H8J9KMNPQRS
step: split
attempt: 1
skill: story-split@1.0.0
inputs:
- path: artifacts/ABC-485/run_01JB2C3D4E5F6G7H8J9KMNPQRS/req.md
  sha256: 93cc1c11b467cc32847865f20ce710cfcc24be59d5b467cdd1b263867b4e4bed
pack_sha:
  sample-orders: 8767c8e0cd137853ba5ceae071e4e085b2c58595
claims: []
trace:
- REQ-1
known:
- S-1
assumed: []
unknown: []
stories:
- id: S-1
  title: Order list under load
  trace:
  - REQ-1
  acceptance_criteria:
  - id: AC1
    text: Given 1000 requests per second, when the order list is called, then p95 stays under 300 ms
---
# Stories: ABC-485

## Stories
- S-1 Order list under load (traces REQ-1)

## Known
- All stories trace to known requirements.

## Assumed
- None.

## Unknown
- None.
