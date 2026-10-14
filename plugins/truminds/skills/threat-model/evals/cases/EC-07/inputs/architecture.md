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
The web app calls the api over HTTP. The api owns the orders, order_events and customers tables.
Sources: context/generated/module-map.json#module:sample-orders:api/src/orders

## Jobs {#jobs}
A nightly purge job in api/src/jobs deletes order events older than the retention window of 90 days.
Sources: context/generated/module-map.json#module:sample-orders:api/src/jobs
