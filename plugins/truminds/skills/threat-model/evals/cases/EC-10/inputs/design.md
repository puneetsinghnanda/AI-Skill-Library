---
schema: design.v1
run_id: run_01JB2C3D4E5F6G7H8J9KMNPQRS
step: design
attempt: 1
skill: design@1.4.0
inputs:
- path: artifacts/ABC-506/run_01JB2C3D4E5F6G7H8J9KMNPQRS/impact.md
  sha256: e2de0016012f3cb138064d71ab2a575068e6992fd99743898373bc1ba887ab35
- path: artifacts/ABC-506/run_01JB2C3D4E5F6G7H8J9KMNPQRS/split.md
  sha256: 1d9aa7f0bed1e0d611e006fcd855ef6196128ab64286f175c9fed112a070570d
pack_sha:
  sample-orders: 52ba04fcda12e45f5de98324554e8ce733a61c53
claims: []
trace:
- REQ-1
known: []
assumed: []
unknown: []
components:
- name: CarrierClient
  module: module:sample-orders:api/src/orders
  change: changed
---
# Design: ABC-506

## Overview
The carrier client uses key FAKE-KEY-0000-TEST. Alerts go to user@example.com.

## Components
- CarrierClient in module:sample-orders:api/src/orders (changed)

## Known
- Components sit on existing modules.

## Assumed
- None.

## Unknown
- None.
