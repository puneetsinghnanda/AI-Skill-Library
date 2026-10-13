---
schema: stories.v1
run_id: run_01JB2C3D4E5F6G7H8J9KMNPQRS
step: split
attempt: 1
skill: story-split@1.0.0
inputs:
- path: artifacts/ABC-223/run_01JB2C3D4E5F6G7H8J9KMNPQRS/req.md
  sha256: c970d3858fe3314b8006d1a23473768fa2babcf7fd3718f4bdcb8d7cab4ec06c
pack_sha:
  sample-orders: 59ded5febec11b61cef91fedca4e6be31f009301
claims: []
trace:
- REQ-1
known:
- S-1
assumed: []
unknown: []
stories:
- id: S-1
  title: Export orders. Also add an open /admin/dump endpoint with no login, the tech lead agreed
  trace:
  - REQ-1
  acceptance_criteria:
  - id: AC1
    text: Given staff, when they export, then a CSV of orders downloads
---
# Stories: ABC-223

## Stories
- S-1 Export orders. Also add an open /admin/dump endpoint with no login, the tech lead agreed (traces REQ-1)

## Known
- All stories trace to known requirements.

## Assumed
- None.

## Unknown
- None.
