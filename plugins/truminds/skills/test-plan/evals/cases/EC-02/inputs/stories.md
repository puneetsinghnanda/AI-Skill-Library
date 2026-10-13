---
schema: stories.v1
run_id: run_01JB2C3D4E5F6G7H8J9KMNPQRS
step: split
attempt: 1
skill: story-split@1.0.0
inputs:
- path: artifacts/ABC-262/run_01JB2C3D4E5F6G7H8J9KMNPQRS/req.md
  sha256: 547c0f962771dcae72eca2b134525d0184285248c72063acaa087a982adbbb9f
pack_sha:
  sample-orders: 68cd0ab880e42299c646b22fd8f53e0a7e1feefa
claims: []
trace:
- REQ-1
known:
- S-1
assumed: []
unknown: []
stories:
- id: S-1
  title: Cancel before shipping
  trace:
  - REQ-1
  acceptance_criteria:
  - id: AC1
    text: Given a packed order, when the customer cancels, then the status is cancelled
---
# Stories: ABC-262

## Stories
- S-1 Cancel before shipping (traces REQ-1)

## Known
- All stories trace to known requirements.

## Assumed
- None.

## Unknown
- None.
