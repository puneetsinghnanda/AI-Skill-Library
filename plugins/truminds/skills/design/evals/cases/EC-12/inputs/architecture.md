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
The web app calls the api over HTTP through web/src/orders. The api owns the orders, order_items and customers tables.
Sources: context/generated/module-map.json#module:sample-orders:api/src/orders

## Shared types {#shared-types}
Shared constants and response types live in `api/src/types.js`; the web app keeps its own copy of the response types.
Sources: context/generated/module-map.json#sym:sample-orders:api/src/types.js:ORDER_STATUSES

## Lists {#lists}
Lists answer `{ items, page, page_size, total }`, 20 per page.
Sources: sample-orders:api/src/orders/list.js#L12
