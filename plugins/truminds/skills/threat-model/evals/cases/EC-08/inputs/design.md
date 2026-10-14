---
schema: design.v1
run_id: run_01JB2C3D4E5F6G7H8J9KMNPQRS
step: design
attempt: 1
skill: design@1.4.0
inputs:
- path: artifacts/ABC-504/run_01JB2C3D4E5F6G7H8J9KMNPQRS/impact.md
  sha256: e740981a37a76688eeabb51bd489e0120a275c05a771347e1b75189750e28483
- path: artifacts/ABC-504/run_01JB2C3D4E5F6G7H8J9KMNPQRS/split.md
  sha256: 43639bc5a4a3ce77ff1c324efaf632bbef9b6f18d123491fca0e908bdfc1ae97
pack_sha:
  sample-orders: 91ca024a86b3520e6293befb2c110dc987d70eee
claims: []
trace:
- REQ-1
known: []
assumed: []
unknown: []
components:
- name: OrderListRoute
  module: module:sample-orders:api/src/orders
  change: changed
- name: FilterService
  module: module:sample-orders:api/src/orders
  change: changed
- name: NotesService
  module: module:sample-orders:api/src/notes
  change: changed
- name: ExportService
  module: module:sample-orders:api/src/orders
  change: changed
- name: CustomerLookup
  module: module:sample-orders:api/src/customers
  change: changed
- name: ReportJob
  module: module:sample-orders:api/src/jobs
  change: changed
endpoints:
- method: GET
  path: /api/orders
  change: changed
---
# Design: ABC-504

## Overview
Invented fixture.

## Components
- OrderListRoute in module:sample-orders:api/src/orders (changed)
- FilterService in module:sample-orders:api/src/orders (changed)
- NotesService in module:sample-orders:api/src/notes (changed)
- ExportService in module:sample-orders:api/src/orders (changed)
- CustomerLookup in module:sample-orders:api/src/customers (changed)
- ReportJob in module:sample-orders:api/src/jobs (changed)

## Known
- Components sit on existing modules.

## Assumed
- None.

## Unknown
- None.
