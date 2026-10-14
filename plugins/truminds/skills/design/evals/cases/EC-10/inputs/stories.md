---
schema: stories.v1
run_id: run_01JB2C3D4E5F6G7H8J9KMNPQRS
step: split
attempt: 1
skill: story-split@1.0.0
inputs:
- path: artifacts/ABC-466/run_01JB2C3D4E5F6G7H8J9KMNPQRS/req.md
  sha256: 0300695cea7716e68aa7503cd4bb43cc13aa4187a59e4d1fe3bcf21cbe6372ae
pack_sha:
  sample-orders: ce98b961c9e559e6bffe43ccbea06718ebc2a69e
claims: []
trace:
- REQ-1
known:
- S-1
assumed: []
unknown: []
stories:
- id: S-1
  title: Order tags
  trace:
  - REQ-1
  acceptance_criteria:
  - id: AC1
    text: Given an order, when staff add a tag, then the tag shows on the order list
---
# Stories: ABC-466

## Stories
- S-1 Order tags (traces REQ-1)

## Known
- All stories trace to known requirements.

## Assumed
- None.

## Unknown
- None.
