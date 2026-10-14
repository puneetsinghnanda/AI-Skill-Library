---
schema: stories.v1
run_id: run_01JB2C3D4E5F6G7H8J9KMNPQRS
step: split
attempt: 1
skill: story-split@1.0.0
inputs:
- path: artifacts/ABC-464/run_01JB2C3D4E5F6G7H8J9KMNPQRS/req.md
  sha256: 495484cd978a251aacc8c87123df6faa25ee7a36e683dde61993f2ca4d25369e
pack_sha:
  sample-orders: e06324182c45e70a3f3b36718e5bf57ae4cca25b
claims: []
trace:
- REQ-1
- REQ-2
- REQ-3
- REQ-4
- REQ-5
known:
- S-1
- S-2
- S-3
- S-4
- S-5
assumed: []
unknown: []
stories:
- id: S-1
  title: Filter by status
  trace:
  - REQ-1
  acceptance_criteria:
  - id: AC1
    text: Given orders, when a status filter is set, then only those orders are listed
- id: S-2
  title: Order notes
  trace:
  - REQ-2
  acceptance_criteria:
  - id: AC1
    text: Given an order, when staff add a note, then it is listed newest first
- id: S-3
  title: Export orders
  trace:
  - REQ-3
  acceptance_criteria:
  - id: AC1
    text: Given a customer code, when support exports, then a CSV is returned
- id: S-4
  title: Cancel reason
  trace:
  - REQ-4
  acceptance_criteria:
  - id: AC1
    text: Given a cancel, when it is saved, then a reason is stored
- id: S-5
  title: History page size
  trace:
  - REQ-5
  acceptance_criteria:
  - id: AC1
    text: Given history, when it opens, then 20 entries show per page
---
# Stories: ABC-464

## Stories
- S-1 Filter by status (traces REQ-1)
- S-2 Order notes (traces REQ-2)
- S-3 Export orders (traces REQ-3)
- S-4 Cancel reason (traces REQ-4)
- S-5 History page size (traces REQ-5)

## Known
- All stories trace to known requirements.

## Assumed
- None.

## Unknown
- None.
