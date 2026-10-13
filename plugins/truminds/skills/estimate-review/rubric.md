---
schema: rubric.v1
skill: estimate-review
criteria:
- id: ER-R1
  name: Evidence-based sizes
  weight: 0.35
- id: ER-R2
  name: Consistent scale
  weight: 0.25
- id: ER-R3
  name: Honest unsized
  weight: 0.25
- id: ER-R4
  name: Clarity
  weight: 0.15
severity_triggers:
  blocker:
  - Hours, days or dates given as an estimate
  major:
  - Sized story without evidence
  - Story missing
  minor:
  - Wording
---
# Rubric: estimate-review

You score one artifact written by the `estimate-review` skill. Read its inputs and the context sections
it cites before you score.

Score every criterion 1 to 5. Use the descriptors for 1, 3 and 5; 2 and 4 sit between them.
tsl computes S3 as the weighted mean. You never compute it.

| Id | Criterion | Weight | 1 | 3 | 5 |
| --- | --- | --- | --- | --- | --- |
| ER-R1 | Evidence-based sizes | 0.35 | Sizes without evidence | Weak evidence | Every size cited |
| ER-R2 | Consistent scale | 0.25 | Sizes contradict each other | Some inconsistent | Consistent relative scale |
| ER-R3 | Honest unsized | 0.25 | Guesses instead of UNSIZED | Some guesses | UNSIZED with a question where needed |
| ER-R4 | Clarity | 0.15 | Hard to read | Readable | Clear for planning |

## Severity triggers (DEF-09)

| Severity | Trigger |
| --- | --- |
| Blocker | Hours, days or dates given as an estimate |
| Major | Sized story without evidence |
| Major | Story missing |
| Minor | Wording |

## Citations

Every finding cites at least one `path#anchor` that proves it (DEF-08). Findings without a citation that
code can verify are dropped by `tsl decide` (R-13), so do not report them.
