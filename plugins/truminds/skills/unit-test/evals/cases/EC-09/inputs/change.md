---
schema: change.v1
run_id: run_01JB2C3D4E5F6G7H8J9KMNPQRS
step: impl
attempt: 1
skill: implement@1.0.0
inputs:
- path: artifacts/ABC-446/run_01JB2C3D4E5F6G7H8J9KMNPQRS/design.md
  sha256: 6d8dc64fb6b85e27451be18aee01f21381ac607ee0cf64207871902975b9b557
- path: artifacts/ABC-446/run_01JB2C3D4E5F6G7H8J9KMNPQRS/split.md
  sha256: 7dcba667c2dff9cc83067f817f06cde1d89eaaab275392e50775e2fd809f19ce
pack_sha:
  sample-orders: e540f4da73835b580141147de4937f9609e76b7c
claims: []
trace:
- REQ-1
known: []
assumed: []
unknown: []
code:
- repo: sample-orders
  base_sha: 968a1f37d7a468bf122f65e0c16bfbcc519be8c4
  head_sha: cd43788663e8350abf1d556909452920eed644f2
  diff_sha256: c839c53fdf707c046fcf670049a4b2ec11543e2c421204f578a997aae26e1ee1
  files:
  - api/src/notes/service.js
summary: Limits a note to 1000 characters.
---
# Change: ABC-446

## Summary
Limits a note to 1000 characters.

## Changes
- api/src/notes/service.js

## Known
- Follows the approved design.

## Assumed
- None.

## Unknown
- None.
