---
schema: intent.v1
run_id: run_01JB2C3D4E5F6G7H8J9KMNPQRS
step: req
attempt: 1
skill: requirement-review@1.0.0
inputs:
- path: artifacts/ABC-103/run_01JB2C3D4E5F6G7H8J9KMNPQRS/ticket.md
  sha256: 24637948bc94898f8ff81a4273aa3491919ecc847e03ef206531f4ece0c02832
- path: context/intent-baseline.md
  sha256: 457606b8582af25d2d1a1d308b8f6564401f88202afa0d159087c969e1981fbc
pack_sha:
  sample-orders: 77064e0db4faef779dd595048f5572673d6311fd
claims:
- id: C1
  text: Order history is kept for 24 hours
  cites:
  - context/intent-baseline.md#data-retention
trace:
- REQ-1
- REQ-2
- REQ-3
known:
- REQ-1
- REQ-3
assumed:
- REQ-2
unknown:
- U-1
requirements:
- id: REQ-1
  title: Show order history list
  type: functional
  status: known
  statement: The order page shows the order history within 2 seconds.
  cites:
  - artifacts/ABC-103/run_01JB2C3D4E5F6G7H8J9KMNPQRS/ticket.md#L12
- id: REQ-2
  title: Page size
  type: functional
  status: assumed
  statement: The history list shows 20 entries per page.
  basis: Matches the list rule in the baseline
  cites:
  - context/intent-baseline.md#constraints
- id: REQ-3
  title: History window
  type: constraint
  status: known
  statement: History covers the last 30 days.
  cites:
  - artifacts/ABC-103/run_01JB2C3D4E5F6G7H8J9KMNPQRS/ticket.md#L13
unknowns:
- id: U-1
  text: Ticket asks for 30 days; baseline keeps order history 24 hours
  question: Q-01
questions:
- id: Q-01
  blocking: true
  ask: product owner
  text: Ticket asks for 30 days of history; the baseline keeps order history 24 hours. Which applies?
  why: Decides whether the design must extend retention
  evidence:
  - context/intent-baseline.md#data-retention
  - artifacts/ABC-103/run_01JB2C3D4E5F6G7H8J9KMNPQRS/ticket.md#L13
  options:
  - Extend retention to 30 days
  - Keep 24 hours and change the requirement
  default: null
glossary:
- term: Order history
  found: true
---
<!-- expect_fail: [H4] -->
# Requirements review: ABC-103

## Summary
The ticket asks for the order history on the order page, covering the last 30 days, newest first.
The baseline keeps order history for 24 hours only, so the ticket and the baseline conflict.
Design cannot start until the product owner decides which window applies.

## Requirements
- REQ-1 Show order history list (known): The order page shows the order history within 2 seconds.
- REQ-2 Page size (assumed): The history list shows 20 entries per page.
- REQ-3 History window (known): History covers the last 30 days.

## Known
- REQ-1: stated in the ticket, line 12.
- REQ-3: stated in the ticket, line 13.

## Assumed
- REQ-2: 20 entries per page, because the baseline says lists show 20 items per page.

## Unknown
- U-1: the ticket asks for 30 days but the baseline keeps 24 hours. Raises Q-01.

## Open questions
- Q-01 (blocking, product owner): Ticket asks for 30 days of history; the baseline keeps order history 24 hours. Which applies?

## Out of scope
- Sorting newest first is already the list rule in the baseline; no separate requirement was needed.
