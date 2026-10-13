---
schema: rubric.v1
skill: secure-code-review
criteria:
- id: SC-R1
  name: Weaknesses found
  weight: 0.35
- id: SC-R2
  name: Precise citations
  weight: 0.2
- id: SC-R3
  name: Right severity
  weight: 0.2
- id: SC-R4
  name: Actionable fixes
  weight: 0.15
- id: SC-R5
  name: No false alarms
  weight: 0.1
severity_triggers:
  blocker:
  - Secret value copied into the artifact
  - New route without authorisation not reported
  major:
  - Injection or missing validation not reported
  - Scan not attached
  minor:
  - Wording
  - Severity one level off
---
# Rubric: secure-code-review

You score one artifact written by the `secure-code-review` skill. Read its inputs and the context sections
it cites before you score.

Score every criterion 1 to 5. Use the descriptors for 1, 3 and 5; 2 and 4 sit between them.
tsl computes S3 as the weighted mean. You never compute it.

| Id | Criterion | Weight | 1 | 3 | 5 |
| --- | --- | --- | --- | --- | --- |
| SC-R1 | Weaknesses found | 0.35 | Obvious issues missed | Some missed | Every real issue found |
| SC-R2 | Precise citations | 0.20 | Findings not located | Some imprecise | Every finding on the exact line |
| SC-R3 | Right severity | 0.20 | Severities wrong | Some off | Severities match impact |
| SC-R4 | Actionable fixes | 0.15 | No direction | Vague | Clear fix direction |
| SC-R5 | No false alarms | 0.10 | Many false positives | Some | None |

## Severity triggers (DEF-09)

| Severity | Trigger |
| --- | --- |
| Blocker | Secret value copied into the artifact |
| Blocker | New route without authorisation not reported |
| Major | Injection or missing validation not reported |
| Major | Scan not attached |
| Minor | Wording |
| Minor | Severity one level off |

## Citations

Every finding cites at least one `path#anchor` that proves it (DEF-08). Findings without a citation that
code can verify are dropped by `tsl decide` (R-13), so do not report them.
