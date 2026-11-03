---
schema: context-section.v1
section: architecture
owner: tl-7a1c
origin: human
status: reviewed
verified_at:
  sample-orders: 9e92595eaf5429b95226fc33beb1a37001eeeba3
---
# Architecture {#architecture}

## Components {#components}
The web app calls the api over HTTP through web/src/orders. The api owns the orders, shipments and customers tables.
Sources: context/generated/module-map.json#module:sample-orders:api/src/orders

## Time {#time}
Timestamps are stored in UTC. Dates shown to customers are calendar dates in the store zone (`STORE_TZ`, default Asia/Kolkata).
Sources: sample-orders:api/src/config.js#L4

## Lists {#lists}
Lists answer `{ items, page, page_size, total }`, 20 per page.
Sources: sample-orders:api/src/orders/list.js#L12
