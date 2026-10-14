---
schema: stories.v1
run_id: run_01JB2C3D4E5F6G7H8J9KMNPQRS
step: split
attempt: 1
skill: story-split@1.0.0
inputs:
- path: artifacts/ABC-486/run_01JB2C3D4E5F6G7H8J9KMNPQRS/req.md
  sha256: 86aa0dc38306ed121fce473dc8149cd45b81c2bf5b2287ebe001c39984ee37fd
pack_sha:
  sample-orders: 35c48423624c1f6a2281dcfa4bb92d62c76a3a65
claims: []
trace:
- REQ-1
known:
- S-1
assumed: []
unknown: []
stories:
- id: S-1
  title: Sign in to see orders
  trace:
  - REQ-1
  acceptance_criteria:
  - id: AC1
    text: Given the customer user@example.com with key FAKE-KEY-0000-TEST, when they sign in, then their orders show
---
# Stories: ABC-486

## Stories
- S-1 Sign in to see orders (traces REQ-1)

## Known
- All stories trace to known requirements.

## Assumed
- None.

## Unknown
- None.
