---
schema: design.v1
run_id: run_01JB2C3D4E5F6G7H8J9KMNPQRS
step: design
attempt: 1
skill: design@1.4.0
inputs:
- path: artifacts/ABC-501/run_01JB2C3D4E5F6G7H8J9KMNPQRS/impact.md
  sha256: fc777e1465fbd2a98f24669e77c3f047581c178b9249e306f23f405819bad085
- path: artifacts/ABC-501/run_01JB2C3D4E5F6G7H8J9KMNPQRS/split.md
  sha256: e864ab73af1cc32014762e9dec24c37ad2cf0e50b3a035d79a00dc7a6ffc1e3b
pack_sha:
  sample-support: b03e781a8b05b956c6ce2f0c675a73be13ae7321
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
# Design: ABC-501

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
