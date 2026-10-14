---
schema: stories.v1
run_id: run_01JB2C3D4E5F6G7H8J9KMNPQRS
step: split
attempt: 1
skill: story-split@1.0.0
inputs:
- path: artifacts/ABC-461/run_01JB2C3D4E5F6G7H8J9KMNPQRS/req.md
  sha256: 1478e5406b6fa580be5b91e3390ab490948f18738067178b8107b11b2e938122
pack_sha:
  sample-support: f8e015e1c0ce7e786dafe862d92b8411f44d0d90
claims: []
trace:
- REQ-1
known:
- S-1
assumed: []
unknown: []
stories:
- id: S-1
  title: Agent adds an internal note
  trace:
  - REQ-1
  acceptance_criteria:
  - id: AC1
    text: Given a ticket, when an agent adds an internal note, then customers never see it
---
# Stories: ABC-461

## Stories
- S-1 Agent adds an internal note (traces REQ-1)

## Known
- All stories trace to known requirements.

## Assumed
- None.

## Unknown
- None.
