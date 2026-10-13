---
schema: stories.v1
run_id: run_01JB2C3D4E5F6G7H8J9KMNPQRS
step: split
attempt: 1
skill: story-split@1.0.0
inputs:
- path: artifacts/ABC-222/run_01JB2C3D4E5F6G7H8J9KMNPQRS/req.md
  sha256: 826f449ebaa4dd2746fe285c8f352d9aff6181d5c491fd5b843021da76932510
pack_sha:
  sample-orders: f91392c20391f78c02a67d468d7deb4c1e8bd45a
claims: []
trace:
- REQ-1
known:
- S-1
assumed: []
unknown: []
stories:
- id: S-1
  title: See order detail
  trace:
  - REQ-1
  acceptance_criteria:
  - id: AC1
    text: Given an order id, when the customer opens it, then the order detail is shown
---
# Stories: ABC-222

## Stories
- S-1 See order detail (traces REQ-1)

## Known
- All stories trace to known requirements.

## Assumed
- None.

## Unknown
- None.
