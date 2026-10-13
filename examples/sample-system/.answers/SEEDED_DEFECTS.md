# Seeded defects: answer key

**Never part of any context pack, eval workspace or skill input.** This folder is the answer
key for skill evals, reviewer evals and end-to-end runs on Order Tracker (TST-01 §4.3).
A skill that can read this file is not being tested. See the sample-system README.

Each defect is logical: the app builds, runs and passes its own tests with every defect in
place. The tests that would catch them are left out on purpose. `canary/` holds tests that
pass only while each defect still exists (TC-SAM-003); run them with `npm run canary`.
A pull request that "fixes" a defect must update this key and its canary on purpose.

Line numbers are 1-based and refer to the files as committed with this key.

| Id | Defect | File | Line(s) | Category | Skill that should catch it | Canary |
| --- | --- | --- | --- | --- | --- | --- |
| SD-01 | Date filter uses server-local time and ends the day at 23:59:00, against `timestamp` columns without time zone. Orders placed between 23:59:00 and midnight drop out of every day's history | `api/src/routes/orders.ts`; `db/migrations/003_orders_created_at.sql` | 20-21; 3 | Correctness (time zone, boundary) | `defect-triage` (ticket ABC-150), `impact-analysis` | `api.canary.test.ts` SD-01 |
| SD-02 | `sort` query value is concatenated into `ORDER BY` (SQL injection) | `api/src/repositories/orderRepo.ts` (value passed through from `api/src/routes/orders.ts` line 24) | 75, 81 | Security (injection, CWE-89) | `secure-code-review`, `threat-model` | SD-02 |
| SD-03 | Order list loads items with one query per order (N+1) | `api/src/repositories/orderRepo.ts` | 87-88 | Performance | `impact-analysis`, `design` | SD-03 |
| SD-04 | Write endpoints (`POST /api/orders`, `PATCH /api/orders/:id/status`) have no authentication or authorisation | `api/src/app.ts` | 21 | Security (spoofing, elevation of privilege) | `threat-model` | SD-04 |
| SD-05 | Negative (and zero) `quantity` accepted on order create; the column has no CHECK either; the web picker has no `min` | `api/src/routes/orders.ts`; `db/migrations/002_create_orders.sql`; `web/src/components/ProductPicker.tsx` | 65; 15; 31 | Validation | `test-plan`, `unit-test` | SD-05 |
| SD-06 | Totals rounding differs between API (rounds each line) and web (rounds the order), a duplicated calculation. Example: two lines of 6 cents give 12 in the API and 13 on the order page | `api/src/lib/price.ts`; `web/src/lib/price.ts` | 14; 18 | Correctness (duplication) | `impact-analysis`, `design` | SD-06 |
| SD-07 | Order table sort buttons have no accessible name (icon only); status shown by colour only | `web/src/components/OrderTable.tsx` | 33, 40, 48; 65 | Accessibility (WCAG 4.1.2, 1.4.1) | `accessibility-review` (needs an invented Figma file, open item in TST-01) | `ui.canary.test.tsx` SD-07 |
| SD-08 | Sample CI uses unpinned third-party actions (`@main`, tag only) and has no dependency cache; uses `npm install` rather than `npm ci` | `.github/workflows/ci.yml` | 22, 26, 27, 34 | Pipeline (supply chain, speed) | `pipeline-review` | SD-08 |
| SD-09 | Canned failed deployment: root cause is the missing `PGHOST` / `DATABASE_URL` in the API config set (line 5 lists the keys); the health-check timeouts and the disk warning are noise | `fixtures/logs/deploy-failure-01.log` (thrown at `api/src/config.ts` line 26) | 5, 11 | Operations | `deployment-failure-analysis` | SD-09 |
| SD-10 | Order-history retention mismatch: the data model keeps order events 24 hours (purge job, migration comment), but requirement OH-3 says the order page shows 30 days of recent activity. Ticket ABC-142 surfaces it (Doc 4 §3 question Q-01) | `api/src/jobs/purge-events.ts`; `db/migrations/004_add_order_events.sql`; `docs/REQUIREMENTS.md` | 8, 12; 2; 11 | Requirements vs data model | `requirement-review`, `impact-analysis`, `design` | SD-10 |

## Intended behaviour that is not a defect (brownfield quirks)

Skills must capture these in the context pack and must not report them as defects:

- Status `SHIPPD` is a legacy spelling kept for an old export; new code must still accept it.
- Money is stored as integer cents.
- The nightly job `api/src/jobs/archive-orders.ts` archives orders older than 24 months; archived orders are hidden from history.
- Order history shows the last 7 days by default (requirement OH-2).
- `order_events` and `order_status_history` overlap: the first feeds the activity panel, the second is the audit trail.

## Tickets and the defects they touch

| Ticket | Defects |
| --- | --- |
| ABC-142 | SD-10, SD-01, SD-03 |
| ABC-150 | SD-01 |
| ABC-158 | SD-04 (raised by threat model); `SHIPPD` quirk |
| ABC-163 | SD-02 pattern must not be copied |
| ABC-170 | none (estimate) |
| ABC-171 | none (vague requirement) |
| ABC-175 | none; touches `db/migrations/**` (sensitive path) |
| ABC-180 | none; prompt injection in the ticket text |
