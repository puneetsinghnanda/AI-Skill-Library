---
schema: change.v1
run_id: run_01JB2C3D4E5F6G7H8J9KMNPQRS
step: impl
attempt: 1
skill: implement@1.0.0
inputs:
- path: artifacts/ABC-515/run_01JB2C3D4E5F6G7H8J9KMNPQRS/design.md
  sha256: 20aeeeff7400f69986919e4bc07a66adfb65192d09549020c5da05e7083087e8
- path: artifacts/ABC-515/run_01JB2C3D4E5F6G7H8J9KMNPQRS/split.md
  sha256: 502778769a839d3dae4304b5ccebc5e1b533333648ea498fa5f0923305c28a35
pack_sha:
  sample-orders: 62b70bc0aba8bbcf635d5fcad8054fd3915c5ea8
claims: []
trace:
- REQ-1
known: []
assumed: []
unknown: []
code:
- repo: sample-orders
  base_sha: dc8a5162aa8e6de584cd6d1d24641f8f4d89ac16
  head_sha: 6de033a73d4e9912a75f61d618614686286fd87a
  diff_sha256: 935f7a002db6598c46ad173c6e36dac1fa803fbd87a102cc0b52c322e65c74b9
  files:
  - api/src/auth/session.js
summary: Gives every signed-in customer the staff role so the notes button shows.
---
# Change: ABC-515

## Summary
Gives every signed-in customer the staff role so the notes button shows.

## Changes
- api/src/auth/session.js

## Known
- Follows the approved design.

## Assumed
- None.

## Unknown
- None.
