---
schema: stories.v1
run_id: run_01JB2C3D4E5F6G7H8J9KMNPQRS
step: split
attempt: 1
skill: story-split@1.0.0
inputs:
- path: artifacts/ABC-465/run_01JB2C3D4E5F6G7H8J9KMNPQRS/req.md
  sha256: 08bc65e90f840fef315617963bc8aacd480fa1d39497e2eabbbf25bdd1cf54ff
pack_sha:
  sample-orders: 2f5ff05e63277815787a04f451de1bcefb9b201b
claims: []
trace:
- REQ-1
known:
- S-1
assumed: []
unknown: []
stories:
- id: S-1
  title: Carrier tracking link
  trace:
  - REQ-1
  acceptance_criteria:
  - id: AC1
    text: Given a shipped order, when it opens, then the carrier link is built with key FAKE-KEY-0000-TEST and errors go to
      user@example.com
---
# Stories: ABC-465

## Stories
- S-1 Carrier tracking link (traces REQ-1)

## Known
- All stories trace to known requirements.

## Assumed
- None.

## Unknown
- None.
