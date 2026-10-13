---
schema: design.v1
run_id: run_01JB2C3D4E5F6G7H8J9KMNPQRS
step: design
attempt: 1
skill: design@1.4.0
inputs:
- path: artifacts/ABC-341/run_01JB2C3D4E5F6G7H8J9KMNPQRS/impact.md
  sha256: da2b579dc0d84c3b82a4ccfa87983a919cd9329ac59a2c27a9f51bcebda904b7
- path: artifacts/ABC-341/run_01JB2C3D4E5F6G7H8J9KMNPQRS/split.md
  sha256: c65fb04488515eb7eed3192b1ea77ac36c11e43c043af0c69012113644d9528a
pack_sha:
  sample-orders: c366911bfcba82f67946eecd101282e6494612ef
claims: []
trace:
- REQ-1
- REQ-2
known: []
assumed: []
unknown: []
components:
- name: NotesService
  module: module:sample-orders:api/src/notes
  change: changed
endpoints:
- method: POST
  path: /api/orders/:id/notes
  change: new
---
# Design: ABC-341

## Overview
Invented fixture.

## Components
- NotesService in module:sample-orders:api/src/notes (changed)

## Known
- Components sit on existing modules.

## Assumed
- None.

## Unknown
- None.
