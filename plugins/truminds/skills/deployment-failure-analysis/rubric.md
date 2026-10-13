---
schema: rubric.v1
skill: deployment-failure-analysis
criteria:
- id: DF-R1
  name: Right first failure
  weight: 0.35
- id: DF-R2
  name: Cited evidence
  weight: 0.25
- id: DF-R3
  name: Plausible cause
  weight: 0.25
- id: DF-R4
  name: Useful next steps
  weight: 0.15
severity_triggers:
  blocker:
  - Token or personal data copied from the log
  major:
  - Follow-on error named as the cause
  - Finding without a log cite
  minor:
  - Wording
---
# Rubric: deployment-failure-analysis

You score one artifact written by the `deployment-failure-analysis` skill. Read its inputs and the context sections
it cites before you score.

Score every criterion 1 to 5. Use the descriptors for 1, 3 and 5; 2 and 4 sit between them.
tsl computes S3 as the weighted mean. You never compute it.

| Id | Criterion | Weight | 1 | 3 | 5 |
| --- | --- | --- | --- | --- | --- |
| DF-R1 | Right first failure | 0.35 | Wrong line blamed | Close | First real failure identified |
| DF-R2 | Cited evidence | 0.25 | No log cites | Some | Every finding on exact lines |
| DF-R3 | Plausible cause | 0.25 | Cause guessed | Partly supported | Cause supported by the lines |
| DF-R4 | Useful next steps | 0.15 | None | Generic | Specific checks |

## Severity triggers (DEF-09)

| Severity | Trigger |
| --- | --- |
| Blocker | Token or personal data copied from the log |
| Major | Follow-on error named as the cause |
| Major | Finding without a log cite |
| Minor | Wording |

## Citations

Every finding cites at least one `path#anchor` that proves it (DEF-08). Findings without a citation that
code can verify are dropped by `tsl decide` (R-13), so do not report them.
