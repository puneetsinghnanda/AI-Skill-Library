---
schema: rubric.v1
skill: accessibility-review
criteria:
- id: AR-R1
  name: Barriers found
  weight: 0.35
- id: AR-R2
  name: Correct criteria
  weight: 0.25
- id: AR-R3
  name: Evidence
  weight: 0.25
- id: AR-R4
  name: Clarity
  weight: 0.15
severity_triggers:
  blocker:
  - An unlabelled control on the main task path not reported
  major:
  - Finding mapped to a wrong or non-AA criterion
  - Contrast ratio estimated instead of computed
  minor:
  - Wording
---
# Rubric: accessibility-review

You score one artifact written by the `accessibility-review` skill. Read its inputs and the context sections
it cites before you score.

Score every criterion 1 to 5. Use the descriptors for 1, 3 and 5; 2 and 4 sit between them.
tsl computes S3 as the weighted mean. You never compute it.

| Id | Criterion | Weight | 1 | 3 | 5 |
| --- | --- | --- | --- | --- | --- |
| AR-R1 | Barriers found | 0.35 | Clear failures missed | Some missed | Every visible failure found |
| AR-R2 | Correct criteria | 0.25 | Wrong criteria | Some wrong | Every finding on the right criterion |
| AR-R3 | Evidence | 0.25 | No values or nodes | Some | Colours, sizes and nodes stated |
| AR-R4 | Clarity | 0.15 | Hard to read | Readable | Clear fix per finding |

## Severity triggers (DEF-09)

| Severity | Trigger |
| --- | --- |
| Blocker | An unlabelled control on the main task path not reported |
| Major | Finding mapped to a wrong or non-AA criterion |
| Major | Contrast ratio estimated instead of computed |
| Minor | Wording |

## Citations

Every finding cites at least one `path#anchor` that proves it (DEF-08). Findings without a citation that
code can verify are dropped by `tsl decide` (R-13), so do not report them.
