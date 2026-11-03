---
schema: design.v1
run_id: run_01JB2C3D4E5F6G7H8J9KMNPQRS
step: design
attempt: 1
skill: design@1.4.0
inputs:
- path: artifacts/ABC-261/run_01JB2C3D4E5F6G7H8J9KMNPQRS/impact.md
  sha256: 30f186a511c542be7c2c90f661fb47a4468fbdd796fe91bcfdf45d8a790532e5
- path: artifacts/ABC-261/run_01JB2C3D4E5F6G7H8J9KMNPQRS/split.md
  sha256: 0d5782e1665248a584c599d5faef57cd6e0e855fffcb9ef6678ecf2e44faa128
pack_sha:
  sample-orders: 802a9431245e837a8b8eeb9a5a94284ef079c8f9
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
# Design: ABC-261

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
