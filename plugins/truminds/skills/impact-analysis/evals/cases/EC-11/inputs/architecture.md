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
The web app calls the api over HTTP. The api owns the orders and customers tables. Several web pages
show order lists; the page-to-route calls are not recorded here.
Sources: context/generated/module-map.json#module:sample-orders:api/src/orders

## Authentication {#authentication}
Customers sign in with a session cookie. Every order endpoint requires a session.
Sources: sample-orders:api/src/auth/session.js#L10
