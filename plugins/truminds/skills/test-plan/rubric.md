---
schema: rubric.v1
skill: test-plan
criteria:
- id: TP-R1
  name: Every criterion covered
  weight: 0.35
- id: TP-R2
  name: Right level
  weight: 0.2
- id: TP-R3
  name: Negative and boundary tests
  weight: 0.2
- id: TP-R4
  name: Follows strategy
  weight: 0.15
- id: TP-R5
  name: Clarity
  weight: 0.1
severity_triggers:
  blocker:
  - Plan claims coverage of a criterion that does not exist
  major:
  - Acceptance criterion without a test
  - No negative test for a new endpoint
  minor:
  - Test naming
  - Level could be lower
---
# Rubric: test-plan

You score one artifact written by the `test-plan` skill. Read its inputs and the context sections
it cites before you score.

Score every criterion 1 to 5. Use the descriptors for 1, 3 and 5; 2 and 4 sit between them.
tsl computes S3 as the weighted mean. You never compute it.

| Id | Criterion | Weight | 1 | 3 | 5 |
| --- | --- | --- | --- | --- | --- |
| TP-R1 | Every criterion covered | 0.35 | Criteria untested | One criterion untested | Every criterion covered |
| TP-R2 | Right level | 0.20 | Everything e2e or manual | Some levels too high | Cheapest level that proves it |
| TP-R3 | Negative and boundary tests | 0.20 | None | Some | Every new endpoint and field |
| TP-R4 | Follows strategy | 0.15 | Ignores the strategy | Minor deviations | Matches tools and folders |
| TP-R5 | Clarity | 0.10 | Hard to read | Readable | Clear titles a tester can run |

## Severity triggers (DEF-09)

| Severity | Trigger |
| --- | --- |
| Blocker | Plan claims coverage of a criterion that does not exist |
| Major | Acceptance criterion without a test |
| Major | No negative test for a new endpoint |
| Minor | Test naming |
| Minor | Level could be lower |

## Citations

Every finding cites at least one `path#anchor` that proves it (DEF-08). Findings without a citation that
code can verify are dropped by `tsl decide` (R-13), so do not report them.
