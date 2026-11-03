---
schema: stories.v1
run_id: run_01JB2C3D4E5F6G7H8J9KMNPQRS
step: split
attempt: 1
skill: story-split@1.0.0
inputs:
- path: artifacts/ABC-231/run_01JB2C3D4E5F6G7H8J9KMNPQRS/req.md
  sha256: 7ffe4c65cfb7de89d38199a0b72a1cd44a96d1501588290215176c6c58957e90
pack_sha:
  sample-orders: c5ddc1175d171a5498bb9fb8e1de18e4d130b0f4
claims: []
trace:
- REQ-1
known:
- S-1
assumed: []
unknown: []
stories:
- id: S-1
  title: Staff add a note
  trace:
  - REQ-1
  acceptance_criteria:
  - id: AC1
    text: Given an order, when staff add a note, then the note is stored
---
# Stories: ABC-231

## Stories
- S-1 Staff add a note (traces REQ-1)

## Known
- All stories trace to known requirements.

## Assumed
- None.

## Unknown
- None.
