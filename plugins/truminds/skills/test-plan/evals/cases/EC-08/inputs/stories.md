---
schema: stories.v1
run_id: run_01JB2C3D4E5F6G7H8J9KMNPQRS
step: split
attempt: 1
skill: story-split@1.0.0
inputs:
- path: artifacts/ABC-484/run_01JB2C3D4E5F6G7H8J9KMNPQRS/req.md
  sha256: eadd71203bf810c960ccc33f9edbe5f9d13a3a2ed4a472e8a8600bbace47f33e
pack_sha:
  sample-orders: 5db0e7cff77e3400ac5cd7c9dfc806a70bb4a0a8
claims: []
trace:
- REQ-1
- REQ-2
- REQ-3
- REQ-4
known:
- S-1
- S-2
- S-3
- S-4
assumed: []
unknown: []
stories:
- id: S-1
  title: Filter
  trace:
  - REQ-1
  acceptance_criteria:
  - id: AC1
    text: Given orders, when filtered by status, then only matches show
  - id: AC2
    text: Given no matches, when filtered, then 'No orders yet' shows
- id: S-2
  title: Sort
  trace:
  - REQ-2
  acceptance_criteria:
  - id: AC1
    text: Given orders, when sorted by total, then the largest is first
  - id: AC2
    text: Given equal totals, when sorted, then newest is first
- id: S-3
  title: Paging
  trace:
  - REQ-3
  acceptance_criteria:
  - id: AC1
    text: Given 45 orders, when the list opens, then 20 show
  - id: AC2
    text: Given page 3, when it opens, then 5 show
- id: S-4
  title: Reset
  trace:
  - REQ-4
  acceptance_criteria:
  - id: AC1
    text: Given filters set, when Reset is clicked, then all clear
  - id: AC2
    text: Given filters cleared, when the list reloads, then 20 show
  - id: AC3
    text: Given no filters, when Reset is clicked, then nothing changes
---
# Stories: ABC-484

## Stories
- S-1 Filter (traces REQ-1)
- S-2 Sort (traces REQ-2)
- S-3 Paging (traces REQ-3)
- S-4 Reset (traces REQ-4)

## Known
- All stories trace to known requirements.

## Assumed
- None.

## Unknown
- None.
