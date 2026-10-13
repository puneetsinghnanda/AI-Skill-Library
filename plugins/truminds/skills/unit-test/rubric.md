---
schema: rubric.v1
skill: unit-test
criteria:
- id: UT-R1
  name: Covers changed behaviour
  weight: 0.3
- id: UT-R2
  name: Meaningful assertions
  weight: 0.25
- id: UT-R3
  name: Edge and error cases
  weight: 0.2
- id: UT-R4
  name: Follows test strategy
  weight: 0.15
- id: UT-R5
  name: Honest results
  weight: 0.1
severity_triggers:
  blocker:
  - Production code changed in the unit-test step
  major:
  - Changed endpoint without an error-path test
  - Coverage stated without verifier evidence
  minor:
  - Test naming
  - Duplicate setup code
---
# Rubric: unit-test

You score one artifact written by the `unit-test` skill. Read its inputs and the context sections
it cites before you score.

Score every criterion 1 to 5. Use the descriptors for 1, 3 and 5; 2 and 4 sit between them.
tsl computes S3 as the weighted mean. You never compute it.

| Id | Criterion | Weight | 1 | 3 | 5 |
| --- | --- | --- | --- | --- | --- |
| UT-R1 | Covers changed behaviour | 0.30 | Changed code untested | Some paths untested | Every changed path tested |
| UT-R2 | Meaningful assertions | 0.25 | Tests assert nothing useful | Some weak assertions | Assertions check observable results |
| UT-R3 | Edge and error cases | 0.20 | None | Some | Errors and edges covered |
| UT-R4 | Follows test strategy | 0.15 | Wrong place or framework | Minor deviations | Matches the strategy |
| UT-R5 | Honest results | 0.10 | Numbers invented | Numbers incomplete | Numbers from the verifier only |

## Severity triggers (DEF-09)

| Severity | Trigger |
| --- | --- |
| Blocker | Production code changed in the unit-test step |
| Major | Changed endpoint without an error-path test |
| Major | Coverage stated without verifier evidence |
| Minor | Test naming |
| Minor | Duplicate setup code |

## Citations

Every finding cites at least one `path#anchor` that proves it (DEF-08). Findings without a citation that
code can verify are dropped by `tsl decide` (R-13), so do not report them.
