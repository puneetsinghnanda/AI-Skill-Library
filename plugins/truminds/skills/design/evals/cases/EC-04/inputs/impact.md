---
schema: impact.v1
run_id: run_01JB2C3D4E5F6G7H8J9KMNPQRS
step: impact
attempt: 1
skill: impact-analysis@1.1.0
inputs:
- path: artifacts/ABC-163/run_01JB2C3D4E5F6G7H8J9KMNPQRS/req.md
  sha256: e13c6b10ab6651ad5a6d608f2348b5ba9359c80244b6a7d917b26aedc2e90c8d
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
tables:
- id: table:orders
  change: existing
  cites:
  - context/generated/db-schema.json#table:orders
---
# Impact analysis: ABC-163

## Summary
Invented fixture.

## Impacted modules
- module:sample-orders:api/src/orders (changed)

## Known
- All ids come from the generated facts.

## Assumed
- None.

## Unknown
- None.
