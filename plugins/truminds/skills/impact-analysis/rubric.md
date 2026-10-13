---
schema: rubric.v1
skill: impact-analysis
criteria:
- id: IA-R1
  name: Complete impact
  weight: 0.3
- id: IA-R2
  name: Grounded in facts
  weight: 0.25
- id: IA-R3
  name: Indirect effects
  weight: 0.2
- id: IA-R4
  name: Honest status
  weight: 0.15
- id: IA-R5
  name: Clarity
  weight: 0.1
severity_triggers:
  blocker:
  - The requirements need a system element that the facts contradict and the artifact did not ask
  major:
  - Changed table without its readers
  - Module id not in the generated facts
  - Missing trace to a REQ
  minor:
  - Wording
  - Ordering
  - Existing item marked changed without effect
---
# Rubric: impact-analysis

You score one artifact written by the `impact-analysis` skill. Read its inputs and the context sections
it cites before you score.

Score every criterion 1 to 5. Use the descriptors for 1, 3 and 5; 2 and 4 sit between them.
tsl computes S3 as the weighted mean. You never compute it.

| Id | Criterion | Weight | 1 | 3 | 5 |
| --- | --- | --- | --- | --- | --- |
| IA-R1 | Complete impact | 0.30 | Touched modules or tables missing | One indirect effect missed | Every touched element listed |
| IA-R2 | Grounded in facts | 0.25 | Ids not in the generated facts | Some ids weakly cited | Every id from the facts, cited |
| IA-R3 | Indirect effects | 0.20 | No callers or jobs considered | Some readers missed | Callers, jobs and readers covered |
| IA-R4 | Honest status | 0.15 | Guesses stated as facts | Weak bases on assumed items | Every status justified |
| IA-R5 | Clarity | 0.10 | Hard to read | Readable | Clear and ordered by risk |

## Severity triggers (DEF-09)

| Severity | Trigger |
| --- | --- |
| Blocker | The requirements need a system element that the facts contradict and the artifact did not ask |
| Major | Changed table without its readers |
| Major | Module id not in the generated facts |
| Major | Missing trace to a REQ |
| Minor | Wording |
| Minor | Ordering |
| Minor | Existing item marked changed without effect |

## Citations

Every finding cites at least one `path#anchor` that proves it (DEF-08). Findings without a citation that
code can verify are dropped by `tsl decide` (R-13), so do not report them.
