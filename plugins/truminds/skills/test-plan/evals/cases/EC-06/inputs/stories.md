---
schema: stories.v1
run_id: run_01JB2C3D4E5F6G7H8J9KMNPQRS
step: split
attempt: 1
skill: story-split@1.0.0
inputs:
- path: artifacts/ABC-482/run_01JB2C3D4E5F6G7H8J9KMNPQRS/req.md
  sha256: 8e671e51775eb8401d3b055c041d5ed1c62e3cf4694e571e7a0fb125a32dce6f
pack_sha:
  sample-library: 82b0f6d4928ef7e2c57a4c7bcc462f8453adaf63
claims: []
trace:
- REQ-1
- REQ-2
known:
- S-1
- S-2
assumed: []
unknown: []
stories:
- id: S-1
  title: Renew once
  trace:
  - REQ-1
  acceptance_criteria:
  - id: AC1
    text: Given a loan never renewed, when the member renews, then it succeeds
  - id: AC2
    text: Given a loan renewed once, when the member renews, then it is refused
- id: S-2
  title: Loan limit
  trace:
  - REQ-2
  acceptance_criteria:
  - id: AC1
    text: Given a member with 5 loans, when they borrow, then it is refused
---
# Stories: ABC-482

## Stories
- S-1 Renew once (traces REQ-1)
- S-2 Loan limit (traces REQ-2)

## Known
- All stories trace to known requirements.

## Assumed
- None.

## Unknown
- None.
