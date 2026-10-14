---
schema: stories.v1
run_id: run_01JB2C3D4E5F6G7H8J9KMNPQRS
step: split
attempt: 1
skill: story-split@1.0.0
inputs:
- path: artifacts/ABC-446/run_01JB2C3D4E5F6G7H8J9KMNPQRS/req.md
  sha256: 75fa8c61c24dc0165e34d74a8cf0b8688ced9278b8a3d6668c537b1a406ee6e3
pack_sha:
  sample-orders: e540f4da73835b580141147de4937f9609e76b7c
claims: []
trace:
- REQ-1
known:
- S-1
assumed: []
unknown: []
stories:
- id: S-1
  title: Note length
  trace:
  - REQ-1
  acceptance_criteria:
  - id: AC1
    text: Given a note of 501 characters, when staff save it, then it is refused
---
# Stories: ABC-446

## Stories
- S-1 Note length (traces REQ-1)

## Known
- All stories trace to known requirements.

## Assumed
- None.

## Unknown
- None.
