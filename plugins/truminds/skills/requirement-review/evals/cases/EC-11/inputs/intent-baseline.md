---
schema: context-section.v1
section: intent-baseline
owner: tl-7a1c
origin: human
status: reviewed
verified_at:
  sample-orders: e3a054f780e3f42c42cffe8a80166e9506254962
---
# Intent baseline {#intent-baseline}

## Goals {#goals}
Customers can see where their orders are and what has changed.
Support staff can answer order questions without opening the database.

## Constraints {#constraints}
The order page loads only the data of one customer.
Lists show 20 items per page and newest items first.

## Order states {#order-states}
An order moves through placed, packed, shipped and delivered.
An order can be cancelled only while it is placed or packed.

## Data retention {#data-retention}
Order status history is kept for 90 days.
