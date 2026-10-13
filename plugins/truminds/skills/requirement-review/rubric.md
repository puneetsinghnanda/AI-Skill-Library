---
schema: rubric.v1
skill: requirement-review
criteria:
- {id: RR-R1, name: Completeness, weight: 0.25}
- {id: RR-R2, name: Atomic and testable, weight: 0.20}
- {id: RR-R3, name: Honest status, weight: 0.25}
- {id: RR-R4, name: Conflicts surfaced, weight: 0.15}
- {id: RR-R5, name: Question quality, weight: 0.10}
- {id: RR-R6, name: Clarity, weight: 0.05}
severity_triggers:
  blocker:
  - A contradiction between ticket and baseline that the artifact resolved silently instead of asking
  major:
  - Invented value marked known
  - Ask missing
  - Compound requirement
  - Question routed to the wrong role
  - Conflict raised without both cites
  minor:
  - Wording
  - Ordering
  - A missing Out-of-scope reason
  - Glossary inconsistency
---

# Rubric: requirement-review

You score one `intent.v1` artifact. Read the ticket snapshot and the intent baseline sections it
cites. Score every criterion 1 to 5 using the descriptors below; 2 and 4 sit between them.
`tsl` computes S3 as the weighted mean, rounded to one decimal. You never compute S3.

| Id | Criterion | Weight | 1 | 3 | 5 |
| --- | --- | --- | --- | --- | --- |
| RR-R1 | Completeness: every distinct ask in the ticket is a requirement or is listed under Out of scope with a reason | 0.25 | Several asks missing | One ask missing or merged | Every ask accounted for |
| RR-R2 | Atomic and testable: one behaviour per REQ, with a condition a tester could check | 0.20 | Most REQs compound or vague | Some compound or vague | All atomic and checkable |
| RR-R3 | Honest status: nothing invented; assumed items have a real basis | 0.25 | An invented value marked known | Weak bases on assumed items | Every status justified by a cite |
| RR-R4 | Conflicts surfaced: every clash with the baseline is a question citing both sides | 0.15 | A clear conflict missed | Conflict noted but not as a question | All conflicts raised with both cites |
| RR-R5 | Question quality: blocking only when needed, right person to ask, real options | 0.10 | Questions block needlessly or ask the wrong role | Mixed | Precise, minimal, well routed |
| RR-R6 | Clarity: plain words, glossary terms used consistently | 0.05 | Hard to read | Readable | Clear and consistent |

## Severity triggers (DEF-09)

| Severity | Trigger |
| --- | --- |
| Blocker | A contradiction between ticket and baseline that the artifact resolved silently instead of asking |
| Major | Invented value marked known; ask missing; compound requirement; question routed to the wrong role; conflict raised without both cites |
| Minor | Wording, ordering, a missing Out-of-scope reason, glossary inconsistency |

## Citations

Every finding cites at least one `path#anchor` that proves it (DEF-08), for example
`artifacts/<ticket>/<run_id>/ticket.md#L6` or `context/intent-baseline.md#data-retention`.
Findings without a citation that code can verify are dropped by `tsl decide` (R-13).
