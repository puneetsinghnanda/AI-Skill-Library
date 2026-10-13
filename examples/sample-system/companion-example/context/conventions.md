---
schema: context-section.v1
section: conventions
owner: tl-7a1c
origin: human
status: drafted
verified_at: null
---

# Conventions {#conventions}

## Code layout {#code-layout}
TypeScript strict in every workspace. API routes live in `api/src/routes`, business rules
in `api/src/services`, SQL in `api/src/repositories`.
Sources: sample-system:tsconfig.base.json#L4

## Errors {#errors}
API errors are JSON `{ "error": { "code", "message" } }`, raised as `HttpError`.
Sources: sample-system:api/src/lib/errors.ts#L1-L15

## Database changes {#database-changes}
Plain SQL migrations in `db/migrations`, applied in file-name order, one transaction each.
Sources: sample-system:db/scripts/migrate.ts#L15-L17

## Open points {#open-points}
- Branch naming and commit message rules are not written down.
