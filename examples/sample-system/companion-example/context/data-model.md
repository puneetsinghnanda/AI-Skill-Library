---
schema: context-section.v1
section: data-model
owner: tl-7a1c
origin: human
status: drafted
verified_at: null
---

# Data model {#data-model}

## Orders {#orders}
An order is created by `POST /api/orders` and owned by the api module. Money is integer
cents. Timestamps are `timestamp` columns without a time zone.
Sources: context/generated/db-schema.json#table:orders, context/generated/api-inventory.json#http:POST:/api/orders

## Order events {#order-events}
`order_events` holds the activity feed shown as "Recent activity" on the order page.
Sources: context/generated/db-schema.json#table:order_events

## Data retention {#data-retention}
Order events are deleted after 24 hours by a scheduled purge job.
Orders older than 24 months are archived and hidden from history.
Sources: sample-system:api/src/jobs/purge-events.ts#L12, sample-system:api/src/jobs/archive-orders.ts#L7

## Statuses {#statuses}
PLACED, PACKED, SHIPPED, DELIVERED, plus the legacy spelling SHIPPD, which means SHIPPED.
Sources: sample-system:api/src/lib/status.ts#L5
