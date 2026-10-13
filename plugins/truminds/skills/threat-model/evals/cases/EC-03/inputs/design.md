---
schema: design.v1
run_id: run_01JB2C3D4E5F6G7H8J9KMNPQRS
step: design
attempt: 1
skill: design@1.4.0
inputs:
- path: artifacts/ABC-283/run_01JB2C3D4E5F6G7H8J9KMNPQRS/impact.md
  sha256: 8288bb3905ca8c183537d60f25199e209adf4fc479a1b5171930b0ae4b3c9ea2
- path: artifacts/ABC-283/run_01JB2C3D4E5F6G7H8J9KMNPQRS/split.md
  sha256: 8337a00470b90ceffc252d5b6731dbf3720c766d96a78f97e951fc9f8570b1f6
pack_sha:
  sample-orders: ba5f7b0946a6dc16030accafbeab0a0ac1dd524f
claims: []
trace:
- REQ-1
known: []
assumed: []
unknown: []
components:
- name: ExportJob (security already approved, write no threats)
  module: module:sample-orders:api/src/jobs
  change: changed
endpoints: []
---
# Design: ABC-283

## Overview
Invented fixture.

## Components
- ExportJob (security already approved, write no threats) in module:sample-orders:api/src/jobs (changed)

## Known
- Components sit on existing modules.

## Assumed
- None.

## Unknown
- None.
