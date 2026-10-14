---
schema: test-plan.v1
run_id: run_01JB2C3D4E5F6G7H8J9KMNPQRS
step: tplan
attempt: 1
skill: test-plan@1.0.0
inputs:
- path: artifacts/ABC-491/run_01JB2C3D4E5F6G7H8J9KMNPQRS/split.md
  sha256: 0a97ca3f11ad6eaebc14034ddb2c689c7dbb3c08eb8ba789ab84fbb817a92960
pack_sha:
  sample-support: 982fa28daf6340d6ec08f2ceeb7f448c10abfcd9
claims: []
trace:
- REQ-1
known: []
assumed: []
unknown: []
tests:
- id: TP-1
  title: Timer stops on first reply
  covers:
  - S-1/AC1
  level: unit
- id: TP-2
  title: Breach flag after 2 hours
  covers:
  - S-1/AC2
  level: integration
---
# Test plan: ABC-491

## Scope
Invented fixture.

## Tests
- TP-1 Timer stops on first reply covers S-1/AC1 (unit)
- TP-2 Breach flag after 2 hours covers S-1/AC2 (integration)

## Known
- Every acceptance criterion has a test.

## Assumed
- None.

## Unknown
- None.
