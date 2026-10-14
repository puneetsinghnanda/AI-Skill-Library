---
schema: design.v1
run_id: run_01JB2C3D4E5F6G7H8J9KMNPQRS
step: design
attempt: 1
skill: design@1.4.0
inputs:
- path: artifacts/ABC-163/run_01JB2C3D4E5F6G7H8J9KMNPQRS/impact.md
  sha256: 83800e154c5565774a34ea6560a49c213503e74b67cb7657f446ef2c8dea7da7
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
components:
- name: ExportService
  module: module:sample-orders:api/src/orders
  change: changed
- name: ExportRoute
  module: module:sample-orders:api/src/orders
  change: changed
endpoints:
- method: GET
  path: /api/customers/:code/orders/export
  change: new
---
# Design: ABC-163

## Overview
Invented fixture.

## Components
- ExportService in module:sample-orders:api/src/orders (changed)
- ExportRoute in module:sample-orders:api/src/orders (changed)

## Known
- Components sit on existing modules.

## Assumed
- None.

## Unknown
- None.
