---
schema: stories.v1
run_id: run_01JB2C3D4E5F6G7H8J9KMNPQRS
step: split
attempt: 1
skill: story-split@1.0.0
inputs:
- path: artifacts/ABC-443/run_01JB2C3D4E5F6G7H8J9KMNPQRS/req.md
  sha256: 498cc59fbcdd9831e6c577498bdf80e92677bf0e51ab481de5d0bb06d66bfb35
pack_sha:
  sample-library: 563a666a3c7e59d2e95ce9c5eef5f3d0df73c661
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
    text: Given a loan never renewed, when the member renews, then the due date moves 21 days
  - id: AC2
    text: Given a loan renewed once, when the member renews again, then the request is refused
---
# Stories: ABC-443

## Stories
- S-1 Renew a loan once (traces REQ-1)

## Known
- All stories trace to known requirements.

## Assumed
- None.

## Unknown
- None.
