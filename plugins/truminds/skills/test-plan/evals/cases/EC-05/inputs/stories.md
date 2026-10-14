---
schema: stories.v1
run_id: run_01JB2C3D4E5F6G7H8J9KMNPQRS
step: split
attempt: 1
skill: story-split@1.0.0
inputs:
- path: artifacts/ABC-481/run_01JB2C3D4E5F6G7H8J9KMNPQRS/req.md
  sha256: b9fce5b515d737faf2c36c6313c85f93d716d51d338a22a968574b5aafc17e00
pack_sha:
  sample-support: ea1739b4136e33af03fff97040c0a0e989cfcc4f
claims: []
trace:
- REQ-1
known:
- S-1
assumed: []
unknown: []
stories:
- id: S-1
  title: Breach flag
  trace:
  - REQ-1
  acceptance_criteria:
  - id: AC1
    text: Given a priority-1 ticket with no reply after 2 hours, when an agent opens the queue, then it shows a breach flag
---
# Stories: ABC-481

## Stories
- S-1 Breach flag (traces REQ-1)

## Known
- All stories trace to known requirements.

## Assumed
- None.

## Unknown
- None.
