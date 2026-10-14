---
schema: stories.v1
run_id: run_01JB2C3D4E5F6G7H8J9KMNPQRS
step: split
attempt: 1
skill: story-split@1.0.0
inputs:
- path: artifacts/ABC-483/run_01JB2C3D4E5F6G7H8J9KMNPQRS/req.md
  sha256: 00311bbcec06d8b30e91fc3a58195a57a858bd91c96670c6642e6a536e87798e
pack_sha:
  sample-orders: ca721e2d3a300c0ca6924b7f2d01cb00e3cd1979
claims: []
trace:
- REQ-1
known:
- S-1
assumed: []
unknown: []
stories:
- id: S-1
  title: Track parcel journey
  trace:
  - REQ-1
  acceptance_criteria:
  - id: AC1
    text: Given a shipped order, when the customer clicks Track, then the carrier page opens in a new tab
---
# Stories: ABC-483

## Stories
- S-1 Track parcel journey (traces REQ-1)

## Known
- All stories trace to known requirements.

## Assumed
- None.

## Unknown
- None.
