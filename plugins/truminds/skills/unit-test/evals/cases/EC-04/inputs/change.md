---
schema: change.v1
run_id: run_01JB2C3D4E5F6G7H8J9KMNPQRS
step: impl
attempt: 1
skill: implement@1.0.0
inputs:
- path: artifacts/ABC-441/run_01JB2C3D4E5F6G7H8J9KMNPQRS/design.md
  sha256: 9d657357bfc4fef445295bc16d7bc170e0d572b702d5c3ef043f8f48dfc764fa
- path: artifacts/ABC-441/run_01JB2C3D4E5F6G7H8J9KMNPQRS/split.md
  sha256: 66af50e1aa1aea90110903c90ce139a4a39e9bdecbc69c4e48728f9d77f01ced
pack_sha:
  sample-orders: 37945644298815008b2199e05aea77d04f9a9a94
claims: []
trace:
- REQ-1
known: []
assumed: []
unknown: []
code:
- repo: sample-orders
  base_sha: 7da80c8942194c219eb6b22103514cff761368b1
  head_sha: c2fb3e27198a936051a454c7f04be4e6f1451fa4
  diff_sha256: f1d9592576f5cd503aa3dcca460df7d259608180a2bdd84885f74733d161e091
  files:
  - api/src/orders/export.js
  - api/src/routes/orders.js
summary: Adds GET /api/customers/:code/orders/export returning CSV.
---
# Change: ABC-441

## Summary
Adds GET /api/customers/:code/orders/export returning CSV.

## Changes
- api/src/orders/export.js
- api/src/routes/orders.js

## Known
- Follows the approved design.

## Assumed
- None.

## Unknown
- None.
