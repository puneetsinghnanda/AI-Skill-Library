---
schema: test-plan.v1
run_id: run_01JB2C3D4E5F6G7H8J9KMNPQRS
step: tplan
attempt: 1
skill: test-plan@1.0.0
inputs:
- path: artifacts/ABC-496/run_01JB2C3D4E5F6G7H8J9KMNPQRS/split.md
  sha256: 5db1fbef187a5be3226c29e1d91f8dcbf7c1e7dfde0ac74c503329750848a916
pack_sha:
  sample-orders: 34b896c223e38d0babe005c178924c4b1e9d4f3b
claims: []
trace:
- REQ-1
known: []
assumed: []
unknown: []
tests:
- id: TP-1
  title: Sign in as user@example.com with FAKE-KEY-0000-TEST shows orders
  covers:
  - S-1/AC1
  level: e2e
---
# Test plan: ABC-496

## Scope
Invented fixture.

## Tests
- TP-1 Sign in as user@example.com with FAKE-KEY-0000-TEST shows orders covers S-1/AC1 (e2e)

## Known
- Every acceptance criterion has a test.

## Assumed
- None.

## Unknown
- None.
