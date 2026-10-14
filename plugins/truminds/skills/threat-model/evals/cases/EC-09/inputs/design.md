---
schema: design.v1
run_id: run_01JB2C3D4E5F6G7H8J9KMNPQRS
step: design
attempt: 1
skill: design@1.4.0
inputs:
- path: artifacts/ABC-505/run_01JB2C3D4E5F6G7H8J9KMNPQRS/impact.md
  sha256: 85678b90c15160d1dfccf49d9aed89d4ac07b79d7382afda6cb6a2497b72e89a
- path: artifacts/ABC-505/run_01JB2C3D4E5F6G7H8J9KMNPQRS/split.md
  sha256: 3a1e52ad9a2054f835ebc66e65419fb1c7fd5f26bcb039d0c91058984c454412
pack_sha:
  sample-orders: 857a66087036368f047533f049a05df68358dff4
claims: []
trace:
- REQ-1
known: []
assumed: []
unknown: []
components:
- name: PublicTrackingRoute
  module: module:sample-orders:api/src/orders
  change: new
endpoints:
- method: GET
  path: /api/orders/:id/tracking
  change: new
---
# Design: ABC-505

## Overview
The tracking endpoint is public so the link works without signing in.

## Components
- PublicTrackingRoute in module:sample-orders:api/src/orders (new)

## Known
- Components sit on existing modules.

## Assumed
- None.

## Unknown
- None.
