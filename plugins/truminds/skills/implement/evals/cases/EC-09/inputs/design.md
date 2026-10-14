---
schema: design.v1
run_id: run_01JB2C3D4E5F6G7H8J9KMNPQRS
step: design
attempt: 1
skill: design@1.4.0
inputs:
- path: artifacts/ABC-435/run_01JB2C3D4E5F6G7H8J9KMNPQRS/impact.md
  sha256: 28798dbbc46be207dd9ed371d4d93bc18d6cd82defea248d190378d5a6d66ff3
- path: artifacts/ABC-435/run_01JB2C3D4E5F6G7H8J9KMNPQRS/split.md
  sha256: 93513cf193608e7ef38e9db0d7aa0fbae136bd3ffdab99d793c2764bf751a927
pack_sha:
  sample-orders: 454709095c3a9fa8d97e065344c1c3e40c4ff4c1
claims: []
trace:
- REQ-1
known: []
assumed: []
unknown: []
components:
- name: NotesPanel
  module: module:sample-orders:web/src/orders
  change: changed
---
# Design: ABC-435

## Overview
Keep order notes in the browser's local storage. No api change.

## Components
- NotesPanel in module:sample-orders:web/src/orders (changed)

## Known
- Components sit on existing modules.

## Assumed
- None.

## Unknown
- None.
