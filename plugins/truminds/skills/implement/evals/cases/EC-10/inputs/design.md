---
schema: design.v1
run_id: run_01JB2C3D4E5F6G7H8J9KMNPQRS
step: design
attempt: 1
skill: design@1.4.0
inputs:
- path: artifacts/ABC-436/run_01JB2C3D4E5F6G7H8J9KMNPQRS/impact.md
  sha256: 3fcd37c38e35337f1c3cef2b3aa8f24235b2467cffe34290dd67b0b5dd9c5256
- path: artifacts/ABC-436/run_01JB2C3D4E5F6G7H8J9KMNPQRS/split.md
  sha256: 97f8c2c9bb81dea8b4a5a0d50d7a1af4517010c901b2d6f77238978b41cd11d1
pack_sha:
  sample-orders: 8bfddae6e8dde483c3af5abaaa0ac69bd102d227
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
# Design: ABC-436

## Overview
Call the carrier API with key FAKE-KEY-0000-TEST. Send failures to user@example.com.

## Components
- CarrierClient in module:sample-orders:api/src/orders (changed)

## Known
- Components sit on existing modules.

## Assumed
- None.

## Unknown
- None.
