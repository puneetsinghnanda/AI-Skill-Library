---
schema: stories.v1
run_id: run_01JB2C3D4E5F6G7H8J9KMNPQRS
step: split
attempt: 1
skill: story-split@1.0.0
inputs:
- path: artifacts/ABC-462/run_01JB2C3D4E5F6G7H8J9KMNPQRS/req.md
  sha256: c5d9c3419ac81db3b8c607b007285dbf2241f0d60dcedd6ca99046ee7e0604d6
pack_sha:
  sample-library: cd2083492d35cccb1749edc6d6d6d76e1ddc8c74
claims: []
trace:
- REQ-1
known:
- S-1
assumed: []
unknown: []
stories:
- id: S-1
  title: Renew a loan once
  trace:
  - REQ-1
  acceptance_criteria:
  - id: AC1
    text: Given a loan renewed once, when the member renews again, then the request is refused
---
# Stories: ABC-462

## Stories
- S-1 Renew a loan once (traces REQ-1)

## Known
- All stories trace to known requirements.

## Assumed
- None.

## Unknown
- None.
