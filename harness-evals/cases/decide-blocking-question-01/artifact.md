---
schema: intent.v1
run_id: run_01J9ZK2M4Q8X7T3B5N6R0VWYCD
step: req
attempt: 1
skill: requirement-review@1.0.0
inputs: []
pack_sha: {}
claims:
- id: C1
  text: Order events are kept `24 hours`
  cites:
  - context/intent-baseline.md#data-retention
trace:
- REQ-1
- REQ-2
known:
- REQ-1
assumed:
- REQ-2
unknown:
- U-1
requirements:
- id: REQ-1
  title: Show order history
  type: functional
  status: known
  statement: The order page shows past orders, newest first.
  cites:
  - inputs/ticket.md#L10
- id: REQ-2
  title: Page size
  type: functional
  status: assumed
  statement: The list shows 20 orders per page.
  basis: The ticket asks for it
  cites:
  - inputs/ticket.md#L11
unknowns:
- id: U-1
  text: Retention differs
  question: Q-01
questions:
- id: Q-01
  blocking: true
  ask: product owner
  text: Ticket wants history; the baseline keeps 24 hours. Which applies?
  why: Decides retention
  evidence:
  - context/intent-baseline.md#data-retention
  options:
  - Extend retention
  - Keep 24 hours
  default: null
glossary:
- term: Order history
  found: true
---

# Requirements review

## Summary
The ticket asks for order history on the order page.

## Requirements
REQ-1 history list; REQ-2 page size.

## Known
REQ-1 from the ticket.

## Assumed
REQ-2 page size.

## Unknown
U-1 retention.

## Open questions
Q-01 (U-1).

## Out of scope
Nothing.
