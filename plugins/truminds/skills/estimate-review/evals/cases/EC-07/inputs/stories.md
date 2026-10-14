---
schema: stories.v1
run_id: run_01JB2C3D4E5F6G7H8J9KMNPQRS
step: split
attempt: 1
skill: story-split@1.0.0
inputs:
- path: artifacts/ABC-543/run_01JB2C3D4E5F6G7H8J9KMNPQRS/req.md
  sha256: e07258726e044f5e2387abd278c83b0e3f2336407831cc8eb04127d232b0023a
pack_sha:
  sample-orders: 8ae8060152d9a21825e43af8f9b0c09ed19ab0c3
claims: []
trace:
- REQ-1
known:
- S-1
assumed: []
unknown: []
stories:
- id: S-1
  title: Add a gift message
  trace:
  - REQ-1
  acceptance_criteria:
  - id: AC1
    text: Given an order, when a gift message is added, then it prints on the packing slip
---
# Stories: ABC-543

## Stories
- S-1 Add a gift message (traces REQ-1)

## Known
- All stories trace to known requirements.

## Assumed
- None.

## Unknown
- None.
