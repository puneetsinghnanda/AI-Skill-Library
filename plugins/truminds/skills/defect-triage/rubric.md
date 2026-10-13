---
schema: rubric.v1
skill: defect-triage
criteria:
- id: DT-R1
  name: Symptoms restated
  weight: 0.15
- id: DT-R2
  name: Grounded candidates
  weight: 0.3
- id: DT-R3
  name: Justified ranking
  weight: 0.2
- id: DT-R4
  name: Useful next checks
  weight: 0.2
- id: DT-R5
  name: Honest unknowns
  weight: 0.15
severity_triggers:
  blocker:
  - No way to reproduce and no question asked
  major:
  - Candidate not in the module map
  - High likelihood without evidence
  - Log line misquoted
  minor:
  - Wording
  - Ordering of equal candidates
---
# Rubric: defect-triage

You score one artifact written by the `defect-triage` skill. Read its inputs and the context sections
it cites before you score.

Score every criterion 1 to 5. Use the descriptors for 1, 3 and 5; 2 and 4 sit between them.
tsl computes S3 as the weighted mean. You never compute it.

| Id | Criterion | Weight | 1 | 3 | 5 |
| --- | --- | --- | --- | --- | --- |
| DT-R1 | Symptoms restated | 0.15 | Symptoms wrong or missing | Partly restated | Every symptom restated with cites |
| DT-R2 | Grounded candidates | 0.30 | Candidates not in the facts | Weak evidence | Every candidate cited from facts and logs |
| DT-R3 | Justified ranking | 0.20 | Ranking arbitrary | Some reasoning | Ranking explained by evidence |
| DT-R4 | Useful next checks | 0.20 | None | Generic | Specific checks that confirm or rule out |
| DT-R5 | Honest unknowns | 0.15 | Guesses stated as facts | Some gaps hidden | Gaps stated with questions |

## Severity triggers (DEF-09)

| Severity | Trigger |
| --- | --- |
| Blocker | No way to reproduce and no question asked |
| Major | Candidate not in the module map |
| Major | High likelihood without evidence |
| Major | Log line misquoted |
| Minor | Wording |
| Minor | Ordering of equal candidates |

## Citations

Every finding cites at least one `path#anchor` that proves it (DEF-08). Findings without a citation that
code can verify are dropped by `tsl decide` (R-13), so do not report them.
