---
schema: rubric.v1
skill: implement
criteria:
- id: IM-R1
  name: Implements the design
  weight: 0.3
- id: IM-R2
  name: Follows conventions
  weight: 0.2
- id: IM-R3
  name: Minimal change
  weight: 0.2
- id: IM-R4
  name: Error and edge handling
  weight: 0.2
- id: IM-R5
  name: Accurate summary
  weight: 0.1
severity_triggers:
  blocker:
  - Change needs a sensitive path or more than the limits and the artifact did not ask
  major:
  - Design component not implemented
  - Unrelated file changed
  - Error handling missing on a new endpoint
  minor:
  - Naming
  - Comment wording
  - Summary ordering
---
# Rubric: implement

You score one artifact written by the `implement` skill. Read its inputs and the context sections
it cites before you score.

Score every criterion 1 to 5. Use the descriptors for 1, 3 and 5; 2 and 4 sit between them.
tsl computes S3 as the weighted mean. You never compute it.

| Id | Criterion | Weight | 1 | 3 | 5 |
| --- | --- | --- | --- | --- | --- |
| IM-R1 | Implements the design | 0.30 | Parts of the design missing or changed | Small gaps | Exactly the design |
| IM-R2 | Follows conventions | 0.20 | Ignores conventions | Some deviations | Matches every convention |
| IM-R3 | Minimal change | 0.20 | Unrelated edits | Some noise | Only needed edits, inside limits |
| IM-R4 | Error and edge handling | 0.20 | Errors unhandled | Some cases missing | Errors and edges handled per conventions |
| IM-R5 | Accurate summary | 0.10 | Summary does not match diff | Partly matches | Summary matches the diff line for line |

## Severity triggers (DEF-09)

| Severity | Trigger |
| --- | --- |
| Blocker | Change needs a sensitive path or more than the limits and the artifact did not ask |
| Major | Design component not implemented |
| Major | Unrelated file changed |
| Major | Error handling missing on a new endpoint |
| Minor | Naming |
| Minor | Comment wording |
| Minor | Summary ordering |

## Citations

Every finding cites at least one `path#anchor` that proves it (DEF-08). Findings without a citation that
code can verify are dropped by `tsl decide` (R-13), so do not report them.
