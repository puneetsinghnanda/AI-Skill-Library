---
schema: context-section.v1
section: architecture
owner: tl-7a1c
origin: human
status: reviewed
verified_at:
  sample-support: f98a0155c9dc0a854cfece718baaf43e6ca49a49
---
# Architecture {#architecture}

## Components {#components}
The web app calls the api over HTTP. The api owns the tickets, ticket_replies and sla_timers tables.
Sources: context/generated/module-map.json#module:sample-support:api/src/tickets

## SLA timer {#sla-timer}
The SLA module in api/src/sla starts a timer when a ticket is created and stops it on the first agent reply.
Sources: context/generated/module-map.json#module:sample-support:api/src/sla

## Authentication {#authentication}
Agents sign in with the agent role. Customers can only read and reply to their own tickets.
Sources: sample-support:api/src/auth/roles.js#L5
