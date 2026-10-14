---
schema: design.v1
run_id: run_01JB2C3D4E5F6G7H8J9KMNPQRS
step: design
attempt: 1
skill: design@1.4.0
inputs:
- path: artifacts/ABC-545/run_01JB2C3D4E5F6G7H8J9KMNPQRS/impact.md
  sha256: 06ec42aecec59c4bb707eb61ca8f070ec228d3566e74cd19c8e482dcfe812ae0
- path: artifacts/ABC-545/run_01JB2C3D4E5F6G7H8J9KMNPQRS/split.md
  sha256: c87fff7c65fcfca5d9c86298734fadcefcb2b490fcdbe157befdf84bd58a3732
pack_sha:
  sample-orders: 957d1d17a20a2dcdfbd721dc3ebd5c148c227ca0
claims: []
trace:
- REQ-1
known: []
assumed: []
unknown: []
components:
- name: SlotService
  module: module:sample-orders:api/src/orders
  change: new
- name: SlotPicker
  module: module:sample-orders:web/src/orders
  change: new
endpoints:
- method: POST
  path: /api/orders/:id/slot
  change: new
---
# Design: ABC-545

## Overview
Adds a delivery_slots table with a database migration, a new service and a new picker.

## Components
- SlotService in module:sample-orders:api/src/orders (new)
- SlotPicker in module:sample-orders:web/src/orders (new)

## Known
- Components sit on existing modules.

## Assumed
- None.

## Unknown
- None.
