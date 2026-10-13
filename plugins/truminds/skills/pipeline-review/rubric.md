---
schema: rubric.v1
skill: pipeline-review
criteria:
- id: PL-R1
  name: Real risks found
  weight: 0.35
- id: PL-R2
  name: Exact job and step
  weight: 0.25
- id: PL-R3
  name: Right severity
  weight: 0.2
- id: PL-R4
  name: Actionable
  weight: 0.2
severity_triggers:
  blocker:
  - Secret value quoted in the artifact
  major:
  - Deploy without tests not reported
  - Finding cites a job that does not exist
  minor:
  - Wording
  - Severity one level off
---
# Rubric: pipeline-review

You score one artifact written by the `pipeline-review` skill. Read its inputs and the context sections
it cites before you score.

Score every criterion 1 to 5. Use the descriptors for 1, 3 and 5; 2 and 4 sit between them.
tsl computes S3 as the weighted mean. You never compute it.

| Id | Criterion | Weight | 1 | 3 | 5 |
| --- | --- | --- | --- | --- | --- |
| PL-R1 | Real risks found | 0.35 | Obvious gaps missed | Some missed | Every real gap found |
| PL-R2 | Exact job and step | 0.25 | Locations vague | Some imprecise | Every finding located exactly |
| PL-R3 | Right severity | 0.20 | Severities wrong | Some off | Severities match impact |
| PL-R4 | Actionable | 0.20 | No direction | Vague | Clear fix direction |

## Severity triggers (DEF-09)

| Severity | Trigger |
| --- | --- |
| Blocker | Secret value quoted in the artifact |
| Major | Deploy without tests not reported |
| Major | Finding cites a job that does not exist |
| Minor | Wording |
| Minor | Severity one level off |

## Citations

Every finding cites at least one `path#anchor` that proves it (DEF-08). Findings without a citation that
code can verify are dropped by `tsl decide` (R-13), so do not report them.
