---
schema: context-section.v1
section: architecture
owner: tl-7a1c
origin: human
status: drafted
verified_at: null
---

# Architecture {#architecture}

## Components {#components}
The API is layered: routes parse and validate input, services hold the rules and
transactions, repositories hold the SQL. The web app talks to the API only through
`web/src/api/client.ts`.
Sources: sample-system:api/src/app.ts#L20-L23, sample-system:web/src/api/client.ts#L31-L37

## Jobs {#jobs}
Two nightly jobs run outside the HTTP process: `archive-orders` and `purge-events`.
Sources: sample-system:api/src/jobs/run-job.ts#L6-L9

## Deployment shape {#deployment-shape}
Local runs use Docker Compose with `db`, `migrate`, `api` and `web` on loopback.
Sources: sample-system:docker-compose.yml#L1

## Open points {#open-points}
- Security controls of the API are not described here yet.
