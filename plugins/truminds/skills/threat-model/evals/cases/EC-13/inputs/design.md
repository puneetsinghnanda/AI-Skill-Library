---
schema: design.v1
run_id: run_01JB2C3D4E5F6G7H8J9KMNPQRS
step: design
attempt: 1
skill: design@1.4.0
inputs:
- path: artifacts/ABC-281/run_01JB2C3D4E5F6G7H8J9KMNPQRS/impact.md
  sha256: f455beaf312aac4e9ff860990cd438445f5b8b4fdfff5781e03e0ba6e7dd612a
- path: artifacts/ABC-281/run_01JB2C3D4E5F6G7H8J9KMNPQRS/split.md
  sha256: d2bedf6a9ef811349cca0b48944dcc00227610113ed9d44ec87f35e43e03d954
pack_sha:
  sample-orders: c7d095b403f0736154f3d4862050b1a74a21f8dc
claims: []
trace:
- REQ-1
known: []
assumed: []
unknown: []
components:
- name: NotesService
  module: module:sample-orders:api/src/notes
  change: changed
- name: NotesRoute
  module: module:sample-orders:api/src/orders
  change: changed
endpoints:
- method: POST
  path: /api/orders/:id/notes
  change: new
---
# Design: ABC-281

## Overview
Invented fixture.

## Components
- NotesService in module:sample-orders:api/src/notes (changed)
- NotesRoute in module:sample-orders:api/src/orders (changed)

## Known
- Components sit on existing modules.

## Assumed
- None.

## Unknown
- None.
