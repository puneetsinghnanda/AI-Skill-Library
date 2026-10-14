---
schema: context-section.v1
section: data-model
owner: tl-7a1c
origin: human
status: reviewed
verified_at:
  sample-orders: 9ae700bb9e373dbf56ada51809b241538064b355
---
# Data model {#data-model}

## Orders {#orders}
An order has an id, a customer id, a status and a total in cents.
Sources: context/generated/db-schema.json#table:orders

## Order events {#order-events}
Every status change writes one row to order_events with the new status and a reason.
Sources: context/generated/db-schema.json#table:order_events
