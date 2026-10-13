---
schema: rubric.v1
skill: status-report
criteria:
- id: SR-R1
  name: Accurate
  weight: 0.4
- id: SR-R2
  name: Waits explained
  weight: 0.3
- id: SR-R3
  name: Neutral and private
  weight: 0.15
- id: SR-R4
  name: Clarity
  weight: 0.15
severity_triggers:
  blocker:
  - A real person's name in the report
  major:
  - Count does not match the files
  - Paused run without its wait reason
  minor:
  - Wording
---
# Rubric: status-report

You score one artifact written by the `status-report` skill. Read its inputs and the context sections
it cites before you score.

Score every criterion 1 to 5. Use the descriptors for 1, 3 and 5; 2 and 4 sit between them.
tsl computes S3 as the weighted mean. You never compute it.

| Id | Criterion | Weight | 1 | 3 | 5 |
| --- | --- | --- | --- | --- | --- |
| SR-R1 | Accurate | 0.40 | Counts or statuses wrong | Minor slips | Everything matches the files |
| SR-R2 | Waits explained | 0.30 | Paused runs unexplained | Some explained | Every pause explained |
| SR-R3 | Neutral and private | 0.15 | Names or judgements | Some judgement | Pseudonyms only, neutral |
| SR-R4 | Clarity | 0.15 | Hard to read | Readable | Clear at a glance |

## Severity triggers (DEF-09)

| Severity | Trigger |
| --- | --- |
| Blocker | A real person's name in the report |
| Major | Count does not match the files |
| Major | Paused run without its wait reason |
| Minor | Wording |

## Citations

Every finding cites at least one `path#anchor` that proves it (DEF-08). Findings without a citation that
code can verify are dropped by `tsl decide` (R-13), so do not report them.
