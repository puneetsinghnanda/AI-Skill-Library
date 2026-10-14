---
schema: test-plan.v1
run_id: run_01JB2C3D4E5F6G7H8J9KMNPQRS
step: tplan
attempt: 1
skill: test-plan@1.0.0
inputs:
- path: artifacts/ABC-494/run_01JB2C3D4E5F6G7H8J9KMNPQRS/split.md
  sha256: 4dabb3e2f03d73aa9524c545b2eed7f520866327374b866a1a968d18dc0af662
pack_sha:
  sample-orders: 99a55fa2e61f6b6e3122db5f93c19b182d2ecc20
claims: []
trace:
- REQ-1
known: []
assumed: []
unknown: []
tests:
- id: TP-1
  title: Check it works
  covers:
  - S-1/AC1
  level: integration
- id: TP-2
  title: List shows 20 orders
  covers:
  - S-1/AC2
  level: unit
---
# Test plan: ABC-494

## Scope
Invented fixture.

## Tests
- TP-1 Check it works covers S-1/AC1 (integration)
- TP-2 List shows 20 orders covers S-1/AC2 (unit)

## Known
- Every acceptance criterion has a test.

## Assumed
- None.

## Unknown
- None.
