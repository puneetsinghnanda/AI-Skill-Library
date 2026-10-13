---
schema: rubric.v1
skill: ux-flow-review
criteria:
- id: UF-R1
  name: Flow problems found
  weight: 0.35
- id: UF-R2
  name: Exact nodes
  weight: 0.25
- id: UF-R3
  name: User impact stated
  weight: 0.25
- id: UF-R4
  name: Clarity
  weight: 0.15
severity_triggers:
  blocker:
  - A flow with no way to complete the task not reported
  major:
  - Dead end not reported
  - Finding without a node
  minor:
  - Wording
  - Label preference
---
# Rubric: ux-flow-review

You score one artifact written by the `ux-flow-review` skill. Read its inputs and the context sections
it cites before you score.

Score every criterion 1 to 5. Use the descriptors for 1, 3 and 5; 2 and 4 sit between them.
tsl computes S3 as the weighted mean. You never compute it.

| Id | Criterion | Weight | 1 | 3 | 5 |
| --- | --- | --- | --- | --- | --- |
| UF-R1 | Flow problems found | 0.35 | Dead ends missed | Some missed | Every dead end and missing state found |
| UF-R2 | Exact nodes | 0.25 | Nodes not cited | Some wrong | Every finding on its node |
| UF-R3 | User impact stated | 0.25 | Taste only | Mixed | Every finding states the user impact |
| UF-R4 | Clarity | 0.15 | Hard to read | Readable | Clear and ordered by severity |

## Severity triggers (DEF-09)

| Severity | Trigger |
| --- | --- |
| Blocker | A flow with no way to complete the task not reported |
| Major | Dead end not reported |
| Major | Finding without a node |
| Minor | Wording |
| Minor | Label preference |

## Citations

Every finding cites at least one `path#anchor` that proves it (DEF-08). Findings without a citation that
code can verify are dropped by `tsl decide` (R-13), so do not report them.
