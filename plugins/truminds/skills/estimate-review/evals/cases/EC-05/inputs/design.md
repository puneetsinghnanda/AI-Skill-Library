---
schema: design.v1
run_id: run_01JB2C3D4E5F6G7H8J9KMNPQRS
step: design
attempt: 1
skill: design@1.4.0
inputs:
- path: artifacts/ABC-541/run_01JB2C3D4E5F6G7H8J9KMNPQRS/impact.md
  sha256: 444cffab493eb8a237b2cf3f73d553009d1d2d18d3ad3375b813ded3a1ad9c30
- path: artifacts/ABC-541/run_01JB2C3D4E5F6G7H8J9KMNPQRS/split.md
  sha256: 1717ef278fa1aa0aea6229ad40950af9c83ed4233bc8ca25c11540473c6efb65
pack_sha:
  sample-support: dd7451d071e14a98e94dcda356497ae4e43bbed0
claims: []
trace:
- REQ-1
known: []
assumed: []
unknown: []
components:
- name: SlaTimer
  module: module:sample-support:api/src/sla
  change: changed
- name: QueueView
  module: module:sample-support:web/src/tickets
  change: changed
---
# Design: ABC-541

## Overview
Invented fixture.

## Components
- SlaTimer in module:sample-support:api/src/sla (changed)
- QueueView in module:sample-support:web/src/tickets (changed)

## Known
- Components sit on existing modules.

## Assumed
- None.

## Unknown
- None.
