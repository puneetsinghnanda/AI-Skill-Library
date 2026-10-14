---
schema: change.v1
run_id: run_01JB2C3D4E5F6G7H8J9KMNPQRS
step: impl
attempt: 1
skill: implement@1.0.0
inputs:
- path: artifacts/ABC-444/run_01JB2C3D4E5F6G7H8J9KMNPQRS/design.md
  sha256: 86ecb46e70bc641ad328235c68cb92d62b6e3ed9e5a5145d263b0c25da6aca34
- path: artifacts/ABC-444/run_01JB2C3D4E5F6G7H8J9KMNPQRS/split.md
  sha256: 3137f8153e81cca96df754e80e3923fda028d430f55ae43cddfa83bbcdc061a8
pack_sha:
  sample-orders: 01c407c6a673f13d572f1d24187a8849fc270eda
claims: []
trace:
- REQ-1
known: []
assumed: []
unknown: []
code:
- repo: sample-orders
  base_sha: 6a815f345aa1d0af4643db90458ef75b3d839bbe
  head_sha: 15f4ea2802b8d34587cbc68bfcf9191a92432d2e
  diff_sha256: 7cf7f9b10b527cf5ddf7377853dc134fb7e6f4af256b510eac807a2eaa4c3624
  files:
  - api/src/orders/total.js
summary: Rounds order totals to whole cents.
---
# Change: ABC-444

## Summary
Rounds order totals to whole cents.

## Changes
- api/src/orders/total.js

## Known
- Follows the approved design.

## Assumed
- None.

## Unknown
- None.
