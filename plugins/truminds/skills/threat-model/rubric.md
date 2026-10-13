---
schema: rubric.v1
skill: threat-model
criteria:
- id: TM-R1
  name: Every component modelled
  weight: 0.3
- id: TM-R2
  name: Relevant threats
  weight: 0.25
- id: TM-R3
  name: Concrete mitigations
  weight: 0.25
- id: TM-R4
  name: Honest gaps
  weight: 0.1
- id: TM-R5
  name: Clarity
  weight: 0.1
severity_triggers:
  blocker:
  - A component that handles personal data or credentials has no threat
  major:
  - Component missing
  - Mitigation missing
  - Exploit detail included
  minor:
  - Wording
  - Ordering
---
# Rubric: threat-model

You score one artifact written by the `threat-model` skill. Read its inputs and the context sections
it cites before you score.

Score every criterion 1 to 5. Use the descriptors for 1, 3 and 5; 2 and 4 sit between them.
tsl computes S3 as the weighted mean. You never compute it.

| Id | Criterion | Weight | 1 | 3 | 5 |
| --- | --- | --- | --- | --- | --- |
| TM-R1 | Every component modelled | 0.30 | Components missing | One missing | Every component has threats |
| TM-R2 | Relevant threats | 0.25 | Generic or wrong threats | Some generic | Threats specific to the component |
| TM-R3 | Concrete mitigations | 0.25 | No mitigations | Vague mitigations | Cited or clearly new controls |
| TM-R4 | Honest gaps | 0.10 | Gaps hidden | Some stated | Every gap asked |
| TM-R5 | Clarity | 0.10 | Hard to read | Readable | Clear and ordered by risk |

## Severity triggers (DEF-09)

| Severity | Trigger |
| --- | --- |
| Blocker | A component that handles personal data or credentials has no threat |
| Major | Component missing |
| Major | Mitigation missing |
| Major | Exploit detail included |
| Minor | Wording |
| Minor | Ordering |

## Citations

Every finding cites at least one `path#anchor` that proves it (DEF-08). Findings without a citation that
code can verify are dropped by `tsl decide` (R-13), so do not report them.
