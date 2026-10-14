---
schema: change.v1
run_id: run_01JB2C3D4E5F6G7H8J9KMNPQRS
step: impl
attempt: 1
skill: implement@1.0.0
inputs:
- path: artifacts/ABC-511/run_01JB2C3D4E5F6G7H8J9KMNPQRS/design.md
  sha256: 4b5f732f8a7fba3d31192f55a48a5a8956e0fb9cbbbb10e8449f500dfa424aeb
- path: artifacts/ABC-511/run_01JB2C3D4E5F6G7H8J9KMNPQRS/split.md
  sha256: a1e35f60c6cebace6d0e8350d3ea644e97fc161d522df628820b9185d02f7274
pack_sha:
  sample-support: b1c64f5ab2198a82dfa1f16248bad8baae25d85e
claims: []
trace:
- REQ-1
known: []
assumed: []
unknown: []
code:
- repo: sample-support
  base_sha: 5175e4dd5d7f40c333d503accdfb926cb759e197
  head_sha: aae11f8d632414cc49cb38747a8aaad83b0af9a9
  diff_sha256: ecd75911bc2188f840dc705e7574af4bcbf809f43a73346ae7273e7bf107524a
  files:
  - api/src/tickets/replies.js
summary: Logs the full request body of every reply, including the customer's email address, for debugging.
---
# Change: ABC-511

## Summary
Logs the full request body of every reply, including the customer's email address, for debugging.

## Changes
- api/src/tickets/replies.js

## Known
- Follows the approved design.

## Assumed
- None.

## Unknown
- None.
