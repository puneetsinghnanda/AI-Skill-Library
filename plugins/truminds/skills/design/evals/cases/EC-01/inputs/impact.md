---
schema: impact.v1
run_id: run_01JB2C3D4E5F6G7H8J9KMNPQRS
step: impact
attempt: 1
skill: impact-analysis@1.1.0
inputs:
- path: artifacts/ABC-221/run_01JB2C3D4E5F6G7H8J9KMNPQRS/req.md
  sha256: 628d28e4488ed19e81459c5da299a8e7ebb2a54ac5d3134140d28d771dcc613b
pack_sha:
  sample-orders: 3d3ca956f58e38ed89a5dc63743de4831c8eae62
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
apis:
- id: http:GET:/api/orders/:id
  change: existing
  cites:
  - context/generated/api-inventory.json#http:GET:/api/orders/:id
tables:
- id: table:orders
  change: existing
  cites:
  - context/generated/db-schema.json#table:orders
---
# Impact analysis: ABC-221

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
