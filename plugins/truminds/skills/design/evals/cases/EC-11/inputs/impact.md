---
schema: impact.v1
run_id: run_01JB2C3D4E5F6G7H8J9KMNPQS1
step: impact
attempt: 1
skill: impact-analysis@1.1.0
inputs:
- path: artifacts/ABC-171/run_01JB2C3D4E5F6G7H8J9KMNPQS1/req.md
  sha256: 5b1f0c7e2d4a9e8b3c6f1a0d9e8c7b6a5f4e3d2c1b0a9f8e7d6c5b4a3f2e1d0c
pack_sha:
  sample-orders: 0472a951131fb46c7547e1400c4a3d5d7d7202f4
claims: []
trace:
- REQ-1
known: []
assumed: []
unknown: []
modules:
- id: module:sample-orders:api/src/orders
  change: changed
  cites:
  - context/generated/module-map.json#module:sample-orders:api/src/orders
- id: module:sample-orders:web/src/orders
  change: changed
  cites:
  - context/generated/module-map.json#module:sample-orders:web/src/orders
apis:
- id: http:GET:/api/orders
  change: changed
  cites:
  - context/generated/api-inventory.json#http:GET:/api/orders
tables:
- id: table:shipments
  change: existing
  cites:
  - context/generated/db-schema.json#table:shipments
---
# Impact analysis: ABC-171

## Summary
Invented fixture. The order list response gains one value per row; no new endpoint or table.

## Impacted modules
- module:sample-orders:api/src/orders (changed)
- module:sample-orders:web/src/orders (changed)
- http:GET:/api/orders (changed)

## Known
- All ids come from the generated facts.

## Assumed
- None.

## Unknown
- None.
