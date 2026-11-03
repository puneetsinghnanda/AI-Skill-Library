---
schema: stories.v1
run_id: run_01JB2C3D4E5F6G7H8J9KMNPQS1
step: split
attempt: 1
skill: story-split@1.0.0
inputs:
- path: artifacts/ABC-171/run_01JB2C3D4E5F6G7H8J9KMNPQS1/req.md
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
  title: See when each order last shipped
  trace:
  - REQ-1
  acceptance_criteria:
  - id: AC1
    text: Given an order whose latest shipment left at 2026-10-31T20:00:00Z, when the order list is fetched, then that order's row gives the ship date 2026-11-01 (store zone Asia/Kolkata)
  - id: AC2
    text: Given an order with no shipment, when the order list is fetched, then that order's row gives no ship date
  - id: AC3
    text: Given 45 orders, when the order list is fetched, then paging is unchanged at 20 per page
---
# Stories: ABC-171

## Stories
- S-1 See when each order last shipped (traces REQ-1)

## Known
- All stories trace to known requirements.

## Assumed
- None.

## Unknown
- None.
