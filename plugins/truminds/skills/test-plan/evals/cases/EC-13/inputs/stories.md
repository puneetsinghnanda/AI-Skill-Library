---
schema: stories.v1
run_id: run_01JB2C3D4E5F6G7H8J9KMNPQRS
step: split
attempt: 1
skill: story-split@1.0.0
inputs:
- path: artifacts/ABC-261/run_01JB2C3D4E5F6G7H8J9KMNPQRS/req.md
  sha256: 1d829e9e552b21c96eb4e6aa2214344192b97e0dc104ffad021d1f30cc94db62
pack_sha:
  sample-orders: 802a9431245e837a8b8eeb9a5a94284ef079c8f9
claims: []
trace:
- REQ-1
- REQ-2
known:
- S-1
- S-2
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
  - id: AC2
    text: Given a note over 500 characters, when staff save it, then an error is shown
- id: S-2
  title: Notes listed
  trace:
  - REQ-2
  acceptance_criteria:
  - id: AC1
    text: Given an order with notes, when the page opens, then notes are listed newest first
---
# Stories: ABC-261

## Stories
- S-1 Staff add a note (traces REQ-1)
- S-2 Notes listed (traces REQ-2)

## Known
- All stories trace to known requirements.

## Assumed
- None.

## Unknown
- None.
