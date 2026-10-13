---
schema: context-section.v1
section: system-baseline
owner: tl-7a1c
origin: human
status: drafted
verified_at: null
---

# System baseline {#system-baseline}

## Purpose {#purpose}
Order Tracker lets support staff and customers see orders, their items and their status.
Sources: sample-system:docs/REQUIREMENTS.md#L5-L12

## Modules {#modules}
Three npm workspaces: `api` (Express HTTP API), `web` (React single-page app) and `db`
(SQL migrations and the seed script).
Sources: sample-system:package.json#L10-L14

## Key flows {#key-flows}
Order history: the web page calls `GET /api/orders` with a date range and a page number.
Status change: the order page calls `PATCH /api/orders/:id/status`.
Sources: sample-system:api/src/routes/orders.ts#L12-L14, sample-system:api/src/routes/orders.ts#L73-L75

## Open points {#open-points}
- Who owns the nightly jobs in production is not recorded.
