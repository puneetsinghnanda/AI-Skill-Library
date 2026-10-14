---
schema: design.v1
run_id: run_01JB2C3D4E5F6G7H8J9KMNPQRS
step: design
attempt: 1
skill: design@1.4.0
inputs:
- path: artifacts/ABC-431/run_01JB2C3D4E5F6G7H8J9KMNPQRS/impact.md
  sha256: 6ccf3ec7844540a98e2311406daca0004f5578eb6ed7395e95ccc0fd7b821272
- path: artifacts/ABC-431/run_01JB2C3D4E5F6G7H8J9KMNPQRS/split.md
  sha256: 116feae7143453e524c63e11095a0c206da1ad5d892c65445a15368bc2d0de5d
pack_sha:
  sample-support: 6c188c89dbe7b8f272821dfebbb96771e93a7e25
claims: []
trace:
- REQ-1
known: []
assumed: []
unknown: []
components:
- name: InternalNotesService
  module: module:sample-support:api/src/tickets
  change: changed
endpoints:
- method: POST
  path: /api/tickets/:id/internal-notes
  change: new
---
# Design: ABC-431

## Overview
Invented fixture.

## Components
- InternalNotesService in module:sample-support:api/src/tickets (changed)

## Known
- Components sit on existing modules.

## Assumed
- None.

## Unknown
- None.
