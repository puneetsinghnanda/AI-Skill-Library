---
schema: stories.v1
run_id: run_01JB2C3D4E5F6G7H8J9KMNPQRS
step: split
attempt: 1
skill: story-split@1.0.0
inputs:
- path: artifacts/ABC-434/run_01JB2C3D4E5F6G7H8J9KMNPQRS/req.md
  sha256: da905136488bb06770011e1bdd4305efe5a189b2323d899fe8fb30cf0914a352
pack_sha:
  sample-orders: ea79130e9e840b20925e0f3ee56a8da5e13bd8bb
claims: []
trace:
- REQ-1
known:
- S-1
assumed: []
unknown: []
stories:
- id: S-1
  title: Show the shipped label
  trace:
  - REQ-1
  acceptance_criteria:
  - id: AC1
    text: Given a shipped order, when the page opens, then the label says Shipped
  - id: AC2
    text: Given a shipped order, when the page opens, then the label says Dispatched
---
# Stories: ABC-434

## Stories
- S-1 Show the shipped label (traces REQ-1)

## Known
- All stories trace to known requirements.

## Assumed
- None.

## Unknown
- None.
