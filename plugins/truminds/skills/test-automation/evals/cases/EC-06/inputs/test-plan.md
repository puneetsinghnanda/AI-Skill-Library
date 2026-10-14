---
schema: test-plan.v1
run_id: run_01JB2C3D4E5F6G7H8J9KMNPQRS
step: tplan
attempt: 1
skill: test-plan@1.0.0
inputs:
- path: artifacts/ABC-492/run_01JB2C3D4E5F6G7H8J9KMNPQRS/split.md
  sha256: 7c331eaa3d2544bc3f97c003f10adc5825bf332e82eef437fb1561da089f9cb5
pack_sha:
  sample-library: 8c27711aef75516bb64d7e165a0fe4a16c0c6d24
claims: []
trace:
- REQ-1
known: []
assumed: []
unknown: []
tests:
- id: TP-1
  title: First renew succeeds
  covers:
  - S-1/AC1
  level: unit
- id: TP-2
  title: Second renew refused
  covers:
  - S-1/AC2
  level: unit
- id: TP-3
  title: Sixth loan refused
  covers:
  - S-2/AC1
  level: integration
---
# Test plan: ABC-492

## Scope
Invented fixture.

## Tests
- TP-1 First renew succeeds covers S-1/AC1 (unit)
- TP-2 Second renew refused covers S-1/AC2 (unit)
- TP-3 Sixth loan refused covers S-2/AC1 (integration)

## Known
- Every acceptance criterion has a test.

## Assumed
- None.

## Unknown
- None.
