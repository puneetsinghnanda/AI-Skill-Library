---
schema: design.v1
run_id: run_01JB2C3D4E5F6G7H8J9KMNPQRS
step: design
attempt: 1
skill: design@1.4.0
inputs:
- path: artifacts/ABC-232/run_01JB2C3D4E5F6G7H8J9KMNPQRS/impact.md
  sha256: a929d8e7625c6deac53835e7056bc8ea674f48588bea270fead77eab92b62301
- path: artifacts/ABC-232/run_01JB2C3D4E5F6G7H8J9KMNPQRS/split.md
  sha256: 909c70ac9f05f71fb2565b72cf6de180cb21ae6260ea712bbd6944f5050ebb30
pack_sha:
  sample-orders: 889222a765ee61c7d14126e8393638dc835a5621
claims: []
trace:
- REQ-1
known: []
assumed: []
unknown: []
components:
- name: Order reason column
  module: module:sample-orders:api/src/orders
  change: changed
endpoints: []
---
# Design: ABC-232

## Overview
Invented fixture.

## Components
- Order reason column in module:sample-orders:api/src/orders (changed)

## Known
- Components sit on existing modules.

## Assumed
- None.

## Unknown
- None.
