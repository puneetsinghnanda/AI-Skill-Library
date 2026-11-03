---
schema: stories.v1
run_id: run_01JB2C3D4E5F6G7H8J9KMNPQS2
step: split
attempt: 1
skill: story-split@1.0.0
inputs:
- path: artifacts/ABC-172/run_01JB2C3D4E5F6G7H8J9KMNPQS2/req.md
  sha256: 5b1f0c7e2d4a9e8b3c6f1a0d9e8c7b6a5f4e3d2c1b0a9f8e7d6c5b4a3f2e1d0c
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
  title: See how many items each order holds
  trace:
  - REQ-1
  acceptance_criteria:
  - id: AC1
    text: Given an order with 3 order items, when the order list is fetched, then that order's row gives an item count of 3
  - id: AC2
    text: Given an order with no items, when the order list is fetched, then that order's row gives an item count of 0
  - id: AC3
    text: Given the api list row and the web list row, when the field is added, then both name it the same way
---
# Stories: ABC-172

## Stories
- S-1 See how many items each order holds (traces REQ-1)

## Known
- All stories trace to known requirements.

## Assumed
- None.

## Unknown
- None.
