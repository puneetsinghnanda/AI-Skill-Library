---
schema: stories.v1
run_id: run_01JB2C3D4E5F6G7H8J9KMNPQRS
step: split
attempt: 1
skill: story-split@1.0.0
inputs:
- path: artifacts/ABC-221/run_01JB2C3D4E5F6G7H8J9KMNPQRS/req.md
  sha256: 628d28e4488ed19e81459c5da299a8e7ebb2a54ac5d3134140d28d771dcc613b
pack_sha:
  sample-orders: 3d3ca956f58e38ed89a5dc63743de4831c8eae62
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
    text: Given an order, when staff add a note, then the note is listed on the order
---
# Stories: ABC-221

## Stories
- S-1 Staff add a note (traces REQ-1)

## Known
- All stories trace to known requirements.

## Assumed
- None.

## Unknown
- None.
