---
schema: intent.v1
run_id: run_01JB2C3D4E5F6G7H8J9KMNPQRS
step: req
attempt: 1
skill: requirement-review@1.0.0
inputs:
- path: artifacts/ABC-474/run_01JB2C3D4E5F6G7H8J9KMNPQRS/ticket.md
  sha256: 7152c02c9e4c1974017b2d08f41c8e224d78ff4282a4c5c3f000e051a2602435
pack_sha:
  sample-orders: ae734db72057985ad24952be26c56edd3be159e7
claims: []
trace:
- REQ-1
- REQ-2
- REQ-3
- REQ-4
- REQ-5
- REQ-6
- REQ-7
- REQ-8
known:
- REQ-1
- REQ-2
- REQ-3
- REQ-4
- REQ-5
- REQ-6
- REQ-7
- REQ-8
assumed: []
unknown: []
requirements:
- id: REQ-1
  title: Filter by status
  type: functional
  status: known
  statement: Customers can filter the order list by status.
  cites:
  - artifacts/ABC-474/run_01JB2C3D4E5F6G7H8J9KMNPQRS/ticket.md#L12
- id: REQ-2
  title: Filter by date
  type: functional
  status: known
  statement: Customers can filter the order list by created date.
  cites:
  - artifacts/ABC-474/run_01JB2C3D4E5F6G7H8J9KMNPQRS/ticket.md#L13
- id: REQ-3
  title: Sort by total
  type: functional
  status: known
  statement: Customers can sort the order list by total.
  cites:
  - artifacts/ABC-474/run_01JB2C3D4E5F6G7H8J9KMNPQRS/ticket.md#L14
- id: REQ-4
  title: Page size
  type: functional
  status: known
  statement: The order list shows 20 orders per page.
  cites:
  - artifacts/ABC-474/run_01JB2C3D4E5F6G7H8J9KMNPQRS/ticket.md#L15
- id: REQ-5
  title: Empty state
  type: functional
  status: known
  statement: An empty list shows the text 'No orders yet'.
  cites:
  - artifacts/ABC-474/run_01JB2C3D4E5F6G7H8J9KMNPQRS/ticket.md#L16
- id: REQ-6
  title: Keep filters
  type: functional
  status: known
  statement: Filters stay set when the customer returns to the list.
  cites:
  - artifacts/ABC-474/run_01JB2C3D4E5F6G7H8J9KMNPQRS/ticket.md#L17
- id: REQ-7
  title: Reset filters
  type: functional
  status: known
  statement: One button clears every filter.
  cites:
  - artifacts/ABC-474/run_01JB2C3D4E5F6G7H8J9KMNPQRS/ticket.md#L18
- id: REQ-8
  title: Count
  type: functional
  status: known
  statement: The list shows the number of matching orders.
  cites:
  - artifacts/ABC-474/run_01JB2C3D4E5F6G7H8J9KMNPQRS/ticket.md#L19
unknowns: []
questions: []
glossary: []
---
# Requirements review: ABC-474

## Summary
Invented fixture.

## Requirements
- REQ-1 Filter by status (known): Customers can filter the order list by status.
- REQ-2 Filter by date (known): Customers can filter the order list by created date.
- REQ-3 Sort by total (known): Customers can sort the order list by total.
- REQ-4 Page size (known): The order list shows 20 orders per page.
- REQ-5 Empty state (known): An empty list shows the text 'No orders yet'.
- REQ-6 Keep filters (known): Filters stay set when the customer returns to the list.
- REQ-7 Reset filters (known): One button clears every filter.
- REQ-8 Count (known): The list shows the number of matching orders.

## Known
- REQ-1: stated in the ticket.
- REQ-2: stated in the ticket.
- REQ-3: stated in the ticket.
- REQ-4: stated in the ticket.
- REQ-5: stated in the ticket.
- REQ-6: stated in the ticket.
- REQ-7: stated in the ticket.
- REQ-8: stated in the ticket.

## Assumed
- None.

## Unknown
- None.

## Open questions
- None.

## Out of scope
- None.
