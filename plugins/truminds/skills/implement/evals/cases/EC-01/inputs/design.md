---
schema: design.v1
run_id: run_01JB2C3D4E5F6G7H8J9KMNPQRS
step: design
attempt: 1
skill: design@1.4.0
inputs:
- path: artifacts/ABC-231/run_01JB2C3D4E5F6G7H8J9KMNPQRS/impact.md
  sha256: 6d52ae5754ffb083faf3a2da644433736c8a8996beb14ad26fe62eef8b6965a7
- path: artifacts/ABC-231/run_01JB2C3D4E5F6G7H8J9KMNPQRS/split.md
  sha256: 2b2b2269eb7fc8f47bba34dfd6b3864f5c92f9e586ee2ddab4092fb93a1694ca
pack_sha:
  sample-orders: c5ddc1175d171a5498bb9fb8e1de18e4d130b0f4
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
endpoints:
- method: POST
  path: /api/orders/:id/notes
  change: new
---
# Design: ABC-231

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
