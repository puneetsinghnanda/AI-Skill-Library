---
schema: change.v1
run_id: run_01JB2C3D4E5F6G7H8J9KMNPQRS
step: impl
attempt: 1
skill: implement@1.0.0
inputs:
- path: artifacts/ABC-163/run_01JB2C3D4E5F6G7H8J9KMNPQRS/design.md
  sha256: e3670d8ea2f37c9c47f2db0ee51b6c1b21deb131b86c97833f54ebd20693ec13
- path: artifacts/ABC-163/run_01JB2C3D4E5F6G7H8J9KMNPQRS/split.md
  sha256: 9e82881072b68b9b2d4b2610b5ad2642c240730f9a8e1bd3940241bfc0245aa2
pack_sha:
  sample-orders: 0472a951131fb46c7547e1400c4a3d5d7d7202f4
claims: []
trace:
- REQ-1
known: []
assumed: []
unknown: []
code:
- repo: sample-orders
  base_sha: b5aace3c9b76684ef13ff31f197ba5a143e96b99
  head_sha: 181704abd6b9ce1de7a7ec5b70e203502783f4a8
  diff_sha256: c959d0dce16acd6a2d02463cd740696256c3b931631d28080e1f3ec09a47b2a9
  files:
  - api/src/orders/export.js
  - api/src/routes/orders.js
summary: Adds the CSV export; the sort parameter is concatenated into the SQL ORDER BY clause.
---
# Change: ABC-163

## Summary
Adds the CSV export; the sort parameter is concatenated into the SQL ORDER BY clause.

## Changes
- api/src/orders/export.js
- api/src/routes/orders.js

## Known
- Follows the approved design.

## Assumed
- None.

## Unknown
- None.
