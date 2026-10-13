---
schema: stories.v1
run_id: run_01JB2C3D4E5F6G7H8J9KMNPQRS
step: split
attempt: 1
skill: story-split@1.0.0
inputs:
- path: artifacts/ABC-341/run_01JB2C3D4E5F6G7H8J9KMNPQRS/req.md
  sha256: 6b18d93e5d21d14ed834a21522f412e09505990af0114445d610e9fe40faa92d
pack_sha:
  sample-orders: c366911bfcba82f67946eecd101282e6494612ef
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
    text: Given an order, when staff add a note, then it is stored
- id: S-2
  title: Notes listed
  trace:
  - REQ-2
  acceptance_criteria:
  - id: AC1
    text: Given notes, when the page opens, then they are listed
---
# Stories: ABC-341

## Stories
- S-1 Staff add a note (traces REQ-1)
- S-2 Notes listed (traces REQ-2)

## Known
- All stories trace to known requirements.

## Assumed
- None.

## Unknown
- None.
