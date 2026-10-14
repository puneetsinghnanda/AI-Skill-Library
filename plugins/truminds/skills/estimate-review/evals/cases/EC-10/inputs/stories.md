---
schema: stories.v1
run_id: run_01JB2C3D4E5F6G7H8J9KMNPQRS
step: split
attempt: 1
skill: story-split@1.0.0
inputs:
- path: artifacts/ABC-546/run_01JB2C3D4E5F6G7H8J9KMNPQRS/req.md
  sha256: c0ebe708766475e99ee1d477768c9f9e898afa5b257abe31b1345164ca1ede96
pack_sha:
  sample-orders: 027888fd2691ff989b311a894b217a5fa72ed4d1
claims: []
trace:
- REQ-1
known:
- S-1
assumed: []
unknown: []
stories:
- id: S-1
  title: Change delivery address
  trace:
  - REQ-1
  acceptance_criteria:
  - id: AC1
    text: Given a placed order, when the customer changes the address, then the new address is stored
---
# Stories: ABC-546

## Stories
- S-1 Change delivery address (traces REQ-1)

## Known
- All stories trace to known requirements.

## Assumed
- None.

## Unknown
- None.
