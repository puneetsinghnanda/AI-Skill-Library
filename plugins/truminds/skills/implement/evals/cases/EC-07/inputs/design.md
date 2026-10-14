---
schema: design.v1
run_id: run_01JB2C3D4E5F6G7H8J9KMNPQRS
step: design
attempt: 1
skill: design@1.4.0
inputs:
- path: artifacts/ABC-433/run_01JB2C3D4E5F6G7H8J9KMNPQRS/impact.md
  sha256: 158adf892153f77a1a8b7a4474fcad6716da42c104075cd614817214f34ba8a1
- path: artifacts/ABC-433/run_01JB2C3D4E5F6G7H8J9KMNPQRS/split.md
  sha256: 20bba0e763644d9635baa40d143183e5c2a8e8c4c3a81a3dce785cf5a3ab7eea
pack_sha:
  sample-orders: 66e2cfdfd30ca84281c91a4f19c298eb25a14b50
claims: []
trace:
- REQ-1
known: []
assumed: []
unknown: []
components:
- name: ReportService
  module: module:sample-orders:api/src/reports
  change: changed
endpoints:
- method: GET
  path: /api/reports/daily
  change: new
---
# Design: ABC-433

## Overview
Invented fixture.

## Components
- ReportService in module:sample-orders:api/src/reports (changed)

## Known
- Components sit on existing modules.

## Assumed
- None.

## Unknown
- None.
