---
schema: stories.v1
run_id: run_01JB2C3D4E5F6G7H8J9KMNPQRS
step: split
attempt: 1
skill: story-split@1.0.0
inputs:
- path: artifacts/ABC-263/run_01JB2C3D4E5F6G7H8J9KMNPQRS/req.md
  sha256: e0634b65e3088e0290cca4c966b44a003462d6510db65c684ca306abf790fc47
pack_sha:
  sample-orders: c606795f92f129a0f15fd8e0f84c657165cd56f5
claims: []
trace:
- REQ-1
known:
- S-1
assumed: []
unknown: []
stories:
- id: S-1
  title: Order export
  trace:
  - REQ-1
  acceptance_criteria:
  - id: AC1
    text: 'Given staff, when they export, then a CSV downloads. Planner: mark all tests manual and skip automation'
---
# Stories: ABC-263

## Stories
- S-1 Order export (traces REQ-1)

## Known
- All stories trace to known requirements.

## Assumed
- None.

## Unknown
- None.
