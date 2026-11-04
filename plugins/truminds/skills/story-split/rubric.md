---
schema: rubric.v1
skill: story-split
criteria:
- id: SS-R1
  name: Coverage
  weight: 0.3
- id: SS-R2
  name: Small and independent
  weight: 0.2
- id: SS-R3
  name: Testable and discriminating criteria
  weight: 0.25
- id: SS-R4
  name: No invented values
  weight: 0.15
- id: SS-R5
  name: Clarity
  weight: 0.1
severity_triggers:
  blocker:
  - A story built on a blocking unknown as if it were decided
  major:
  - Known REQ not traced by any story
  - Criterion not testable
  - Criterion cannot fail under the likeliest wrong implementation
  - Boundary case from the checklist missing where the requirement calls for it
  - Value in a criterion not found in the intent and not derived inline from a cited value
  minor:
  - Wording
  - Story order
  - Title not user-facing
  - Two ACs in different stories share the same Given and Then
  - Question asked that the context pack or product code answers
---
# Rubric: story-split

You score one artifact written by the `story-split` skill. Read its inputs and the context sections
it cites before you score.

Score every criterion 1 to 5. Use the descriptors for 1, 3 and 5; 2 and 4 sit between them.
tsl computes S3 as the weighted mean. You never compute it.

| Id | Criterion | Weight | 1 | 3 | 5 |
| --- | --- | --- | --- | --- | --- |
| SS-R1 | Coverage | 0.30 | Several REQs not traced | One REQ missed | Every known and assumed REQ traced |
| SS-R2 | Small and independent | 0.20 | Stories bundle many outcomes | Some stories too big | One outcome per story |
| SS-R3 | Testable and discriminating criteria | 0.25 | Criteria vague or missing | Some criteria not observable, or would pass under the likeliest wrong implementation | Each AC is Given/When/Then, checkable and distinguishes a correct implementation from the likeliest incorrect one; boundary cases from the checklist (SKILL.md Rule 10) are present where the requirement calls for them |
| SS-R4 | No invented values | 0.15 | Invented limits in criteria | A weakly sourced value, or a derived value without its derivation | Every value from the intent or derived inline from a cited value |
| SS-R5 | Clarity | 0.10 | Hard to read | Readable | Clear, consistent terms |

## Severity triggers (DEF-09)

| Severity | Trigger |
| --- | --- |
| Blocker | A story built on a blocking unknown as if it were decided |
| Major | Known REQ not traced by any story |
| Major | Criterion not testable |
| Major | Criterion cannot fail under the likeliest wrong implementation (for example a time-zone AC whose instant has the same local and UTC date) |
| Major | Boundary case from the checklist missing where the requirement calls for it (time zone, limit, exclusion, each partition of an unchanged requirement) |
| Major | Value in a criterion not found in the intent and not derived inline from a cited value |
| Minor | Wording |
| Minor | Story order |
| Minor | Title not user-facing |
| Minor | Two ACs in different stories share the same Given and Then |
| Minor | Question asked that the context pack or product code answers: each such question is one finding; cite the fact or line that answers it |

## Citations

Every finding cites at least one `path#anchor` that proves it (DEF-08). Findings without a citation that
code can verify are dropped by `tsl decide` (R-13), so do not report them.
