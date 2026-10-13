---
schema: rubric.v1
skill: test-automation
criteria:
- id: TA-R1
  name: Plan automated
  weight: 0.3
- id: TA-R2
  name: Meaningful assertions
  weight: 0.25
- id: TA-R3
  name: Results linked
  weight: 0.2
- id: TA-R4
  name: Follows strategy
  weight: 0.15
- id: TA-R5
  name: Honest results
  weight: 0.1
severity_triggers:
  blocker:
  - Production code changed in the test-automation step
  major:
  - Planned test not automated without a reason
  - Result linked to the wrong criterion
  minor:
  - Naming
  - Duplicate fixtures
---
# Rubric: test-automation

You score one artifact written by the `test-automation` skill. Read its inputs and the context sections
it cites before you score.

Score every criterion 1 to 5. Use the descriptors for 1, 3 and 5; 2 and 4 sit between them.
tsl computes S3 as the weighted mean. You never compute it.

| Id | Criterion | Weight | 1 | 3 | 5 |
| --- | --- | --- | --- | --- | --- |
| TA-R1 | Plan automated | 0.30 | Many planned tests missing | Some missing | Every non-manual test automated |
| TA-R2 | Meaningful assertions | 0.25 | Assertions trivial | Some weak | Assertions prove each criterion |
| TA-R3 | Results linked | 0.20 | Links missing | Some wrong | Every result linked to its criteria |
| TA-R4 | Follows strategy | 0.15 | Wrong framework or place | Minor deviations | Matches the strategy |
| TA-R5 | Honest results | 0.10 | Statuses guessed | Some unverified | Statuses from the verifier only |

## Severity triggers (DEF-09)

| Severity | Trigger |
| --- | --- |
| Blocker | Production code changed in the test-automation step |
| Major | Planned test not automated without a reason |
| Major | Result linked to the wrong criterion |
| Minor | Naming |
| Minor | Duplicate fixtures |

## Citations

Every finding cites at least one `path#anchor` that proves it (DEF-08). Findings without a citation that
code can verify are dropped by `tsl decide` (R-13), so do not report them.
