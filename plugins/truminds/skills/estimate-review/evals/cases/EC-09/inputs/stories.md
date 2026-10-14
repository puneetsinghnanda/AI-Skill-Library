---
schema: stories.v1
run_id: run_01JB2C3D4E5F6G7H8J9KMNPQRS
step: split
attempt: 1
skill: story-split@1.0.0
inputs:
- path: artifacts/ABC-545/run_01JB2C3D4E5F6G7H8J9KMNPQRS/req.md
  sha256: 105564e04367b530c4c9df686823bb2a0db5cddf2fbe27a1564587d5a4ac6417
pack_sha:
  sample-orders: 957d1d17a20a2dcdfbd721dc3ebd5c148c227ca0
claims: []
trace:
- REQ-1
known:
- S-1
assumed: []
unknown: []
stories:
- id: S-1
  title: Pick a delivery slot
  trace:
  - REQ-1
  acceptance_criteria:
  - id: AC1
    text: Given checkout, when the customer picks a slot, then the order stores it
---
# Stories: ABC-545

## Stories
- S-1 Pick a delivery slot (traces REQ-1)

## Known
- All stories trace to known requirements.

## Assumed
- None.

## Unknown
- None.
