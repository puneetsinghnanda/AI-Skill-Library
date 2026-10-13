---
schema: rubric.v1
skill: design
criteria:
- id: DS-R1
  name: Fits the architecture
  weight: 0.25
- id: DS-R2
  name: Serves every story
  weight: 0.25
- id: DS-R3
  name: Precise interfaces
  weight: 0.2
- id: DS-R4
  name: Honest status
  weight: 0.15
- id: DS-R5
  name: Trade-offs explained
  weight: 0.1
- id: DS-R6
  name: Clarity
  weight: 0.05
severity_triggers:
  blocker:
  - New infrastructure or external service chosen without asking
  major:
  - Endpoint clash marked new
  - Story not served
  - Component on a module that does not exist
  minor:
  - Wording
  - Ordering
  - Missing trade-off line
---
# Rubric: design

You score one artifact written by the `design` skill. Read its inputs and the context sections
it cites before you score.

Score every criterion 1 to 5. Use the descriptors for 1, 3 and 5; 2 and 4 sit between them.
tsl computes S3 as the weighted mean. You never compute it.

| Id | Criterion | Weight | 1 | 3 | 5 |
| --- | --- | --- | --- | --- | --- |
| DS-R1 | Fits the architecture | 0.25 | Ignores existing modules | Some needless new parts | Built on existing modules and rules |
| DS-R2 | Serves every story | 0.25 | Stories unserved | One criterion unserved | Every story and criterion served |
| DS-R3 | Precise interfaces | 0.20 | Endpoints vague | Some shapes missing | Methods, paths and data precise |
| DS-R4 | Honest status | 0.15 | Invented infrastructure | Weak assumptions | Every choice cited or asked |
| DS-R5 | Trade-offs explained | 0.10 | No reasons | Some reasons | Every non-obvious choice explained |
| DS-R6 | Clarity | 0.05 | Hard to read | Readable | Clear and consistent |

## Severity triggers (DEF-09)

| Severity | Trigger |
| --- | --- |
| Blocker | New infrastructure or external service chosen without asking |
| Major | Endpoint clash marked new |
| Major | Story not served |
| Major | Component on a module that does not exist |
| Minor | Wording |
| Minor | Ordering |
| Minor | Missing trade-off line |

## Citations

Every finding cites at least one `path#anchor` that proves it (DEF-08). Findings without a citation that
code can verify are dropped by `tsl decide` (R-13), so do not report them.
