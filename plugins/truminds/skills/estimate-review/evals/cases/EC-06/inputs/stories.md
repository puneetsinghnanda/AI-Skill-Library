---
schema: stories.v1
run_id: run_01JB2C3D4E5F6G7H8J9KMNPQRS
step: split
attempt: 1
skill: story-split@1.0.0
inputs:
- path: artifacts/ABC-542/run_01JB2C3D4E5F6G7H8J9KMNPQRS/req.md
  sha256: 1c2c5ef4afb55497173ade664df954bf7e6c6d4497cb71b5387dfc127471f795
pack_sha:
  sample-library: 3b9ca72b446b3d7e6ec31bf066cf1663e311c5bf
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
    text: Given a renewed loan, when renewed again, then it is refused
- id: S-2
  title: Loan limit
  trace:
  - REQ-2
  acceptance_criteria:
  - id: AC1
    text: Given 5 loans, when the member borrows, then it is refused
---
# Stories: ABC-542

## Stories
- S-1 Renew once (traces REQ-1)
- S-2 Loan limit (traces REQ-2)

## Known
- All stories trace to known requirements.

## Assumed
- None.

## Unknown
- None.
