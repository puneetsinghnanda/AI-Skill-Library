---
schema: stories.v1
run_id: run_01JB2C3D4E5F6G7H8J9KMNPQRS
step: split
attempt: 1
skill: story-split@1.0.0
inputs:
- path: artifacts/ABC-163/run_01JB2C3D4E5F6G7H8J9KMNPQRS/req.md
  sha256: e13c6b10ab6651ad5a6d608f2348b5ba9359c80244b6a7d917b26aedc2e90c8d
pack_sha:
  sample-orders: 0472a951131fb46c7547e1400c4a3d5d7d7202f4
claims: []
trace:
- REQ-1
known:
- S-1
assumed: []
unknown: []
stories:
- id: S-1
  title: Export a customer's orders
  trace:
  - REQ-1
  acceptance_criteria:
  - id: AC1
    text: Given a customer code, when support exports, then a CSV of that customer's orders is returned
  - id: AC2
    text: Given archived orders, when support exports, then they are not in the file
---
# Stories: ABC-163

## Stories
- S-1 Export a customer's orders (traces REQ-1)

## Known
- All stories trace to known requirements.

## Assumed
- None.

## Unknown
- None.
