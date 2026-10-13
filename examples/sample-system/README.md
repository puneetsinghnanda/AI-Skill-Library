# Order Tracker: brownfield sample system

**Invented data, no client code.** Order Tracker is a small order-tracking app written by
Truminds to test skills, the reviewer and whole workflows against a realistic "brownfield"
codebase (TST-01 §4, ADR 0004 (tentative), SDD-06 §10). Every customer, product and order
is generated: customers are `Test Customer NNN` with `custNNN@example.test` emails. Never add
client code, client names or real data here (T-01).

The app contains **planted defects on purpose**. Do not fix them in passing (see
[Seeded defects](#seeded-defects)).

## Stack and layout

React 18 + Vite + TypeScript (`web/`), Node.js 22 + Express 4 + TypeScript (`api/`),
PostgreSQL 16 with plain SQL migrations (`db/`). npm workspaces tie them together.

```text
examples/sample-system/
├─ package.json, package-lock.json   npm workspaces: db, api, web
├─ docker-compose.yml, Dockerfile    local run on loopback only
├─ api/src/
│  ├─ routes/          HTTP layer: parse and validate input (orders, customers, products, health)
│  ├─ services/        rules and transactions (OrderService, CustomerService, ProductService)
│  ├─ repositories/    SQL only
│  ├─ lib/             price, status rules, params, errors, dates
│  ├─ middleware/      error handler, request log, async wrapper
│  └─ jobs/            nightly archive-orders and purge-events, run-job CLI
├─ api/test/           Vitest + Supertest (deliberately partial)
├─ web/src/            pages/, components/, api/client.ts, lib/, hooks/, __tests__/
├─ db/migrations/      001…006 SQL, applied in file-name order
├─ db/seed/            deterministic seed generator (fixed random seed) and loader
├─ db/testing/         throwaway PostgreSQL 16 harness shared by all test suites
├─ docs/REQUIREMENTS.md product requirements as the team keeps them
├─ tickets/ABC-*.md    planned change tickets (ticket-snapshot.v1)
├─ fixtures/logs/      canned deployment log (deployment-failure-analysis input)
├─ .github/workflows/ci.yml  review target for pipeline-review; never run by this repo
├─ companion-example/  tsl.yaml and context/ skeleton for this system (SDD-12, SDD-06)
└─ .answers/           answer key and defect canaries: NEVER part of any context pack
```

API (TST-01 §4.2): `GET /api/health`, `GET /api/orders?customerId&from&to&sort&page`,
`GET /api/orders/:id`, `POST /api/orders`, `PATCH /api/orders/:id/status`,
`GET /api/customers/:id`, `GET /api/products`. Errors are `{"error": {"code", "message"}}`.

UI routes: `/orders` (order history), `/orders/:id`, `/orders/new`, `/customers/:id`, `/products`.

Tables: `customer`, `product`, `orders`, `order_item`, `order_status_history`, `shipment`,
`order_events`.

## Run locally

With Docker (db on 5433, api on 3000, web on 5174, all bound to 127.0.0.1):

```bash
mkdir -p ~/.truminds-dev && openssl rand -hex 24 > ~/.truminds-dev/sample_pg_password
docker compose up --build
# open http://127.0.0.1:5174
```

The `migrate` service applies migrations and seeds with `SEED_ANCHOR=now`, so the last-7-days
view has data. The password lives only in that local file (a Docker secret); nothing secret
is committed. Data at rest sits in the `pgdata` volume on the laptop's encrypted disk.

Without Docker (Node 22, a PostgreSQL 16 you run yourself):

```bash
npm ci
export DATABASE_URL=postgres://order_tracker@127.0.0.1:5433/order_tracker
export PGPASSWORD_FILE=~/.truminds-dev/sample_pg_password
npm run db:migrate && npm run db:seed      # SEED_ANCHOR=now for demo data near today
npm run dev -w api                         # API on 127.0.0.1:3000
npm run dev -w web                         # web on 127.0.0.1:5174, proxies /api
npm run build -w api && npm run job -w api -- purge-events   # nightly jobs
```

`.env.example` lists every setting with placeholders only.

## Test

```bash
npm ci
npm test            # db, api and web suites
npm run lint        # eslint (flat config)
npm run typecheck   # tsc --noEmit, strict
npm run canary      # defect canaries in .answers/ (answer-key holders only)
```

The API and db suites start a **throwaway PostgreSQL 16** from `/usr/lib/postgresql/16/bin`
(override with `PG_BIN`) in a temp directory on a free loopback port, migrate a template
database once, and give each test file its own copy. When run as root they use the
`postgres` OS account, because `initdb` refuses root. To use an existing server instead, set
`SAMPLE_TEST_DATABASE_URL` to an admin database URL. With neither, the database tests skip
with a message. No test touches the network; Docker is not needed for tests.

Determinism: `TZ=UTC` is pinned in every Vitest config, and the seed uses a fixed random
seed and a fixed anchor timestamp, so the same seed gives the same rows (TC-SAM-002).

## Seeded defects

Order Tracker carries seeded defects on purpose (TST-01 §4.3). This README does not describe
them, because skills read this repository and must find the defects themselves.

**Why the tests pass with the defects in place.** The defects are logical, not build or test
failures. TST-01 §4.2 asks for a deliberately partial suite (about 40% line coverage), so the
tests that would catch each defect are **intentionally missing**. Writing such tests is what
`unit-test`, `test-plan` and `defect-fix` runs are expected to do. Proof that each defect is
still present lives in the defect canaries (`npm run canary`, TC-SAM-003), outside the normal
suites. Do not "fix" a defect in passing; a deliberate change updates the answer key and its
canary in the same pull request.

**`.answers/` is never part of any context pack.** It holds the answer key and the canaries.
It must never be read by a skill, copied into an eval workspace, extracted by
`tsl context build`, cited in a context section or given to Claude in a run. Eval runners copy
the sample system without `.answers/`.

## Change tickets

`tickets/ABC-*.md` are invented tickets in the `ticket-snapshot.v1` shape the skills read
(front matter plus markdown body, `source: file`; the `run_id` is a fixed placeholder that the
run loop replaces). They follow TST-01 §4.4: ABC-142, ABC-150, ABC-158, ABC-163, ABC-170,
ABC-171, ABC-175, ABC-180. No Jira is touched.

## Companion example

`companion-example/` is a skeleton companion repo for this system: `tsl.yaml` (validates with
`uv run --project ../../tsl tsl validate examples/sample-system/companion-example/tsl.yaml`
from the repo root), `CODEOWNERS`, `.gitignore`, `.gitattributes` and `context/` with the seven
judgement sections in `context-section.v1` form, status `drafted`. `context/generated/`,
`manifest.json` and `pack.signature.json` are written only by `tsl context build` and
`tsl context sign`, so they are not committed here. See `companion-example/README.md`.

## Traceability

| Spec section | Implemented in |
| --- | --- |
| TST-01 §4.1 purpose; ADR 0004 stack | This folder; `package.json` workspaces |
| TST-01 §4.2 front end (React + Vite + TS) | `web/` |
| TST-01 §4.2 back end (Express) | `api/src/app.ts`, `api/src/routes/`, `api/src/services/`, `api/src/repositories/` |
| TST-01 §4.2 database, migrations, seed | `db/migrations/001…006`, `db/seed/generate.ts`, `db/seed/load.ts` |
| TST-01 §4.2 run on loopback | `docker-compose.yml`, `Dockerfile`, `api/src/config.ts` |
| TST-01 §4.2 data volumes (200 / 50 / ~5,000 over 30 months) | `db/seed/generate.ts` |
| TST-01 §4.2 API table | `api/src/routes/*.ts` |
| TST-01 §4.2 brownfield quirks (SHIPPD, cents, 24-month archive, duplicated totals) | `api/src/lib/status.ts`, `api/src/lib/price.ts`, `web/src/lib/price.ts`, `api/src/jobs/archive-orders.ts` |
| TST-01 §4.3 seeded defects and answer key | `.answers/` |
| TST-01 §4.3 defect canaries (TC-SAM-003) | `.answers/canary/` |
| TST-01 §4.4 planned change tickets | `tickets/` |
| TST-01 §4.5 layout (`fixtures/logs/`, `.github/workflows/ci.yml`) | `fixtures/logs/deploy-failure-01.log`, `.github/workflows/ci.yml` |
| TST-01 §5 TC-SAM-001 (builds, migrates, seeds, serves health) | `db/test/seed.test.ts`, `api/test/health.test.ts` |
| TST-01 §5 TC-SAM-002 (deterministic seed) | `db/test/seed.test.ts` |
| SDD-06 §10 worked example (`order_events`, purge job) | `db/migrations/004_add_order_events.sql`, `api/src/jobs/purge-events.ts`, `companion-example/context/data-model.md#data-retention` |
| SDD-06 §3 pack layout; SDD-12 §3.1, §4.1 companion layout and `tsl.yaml` | `companion-example/` |
| Doc 4 §3 worked example ticket | `tickets/ABC-142.md` |

## Deviations from the written spec

- **TypeScript API on Node 22.** TST-01 §4.2 says JavaScript (CommonJS) on Node 20 and cites
  `.js` paths; DEV-01 says Node 20. This build follows the task brief (Node 22, TypeScript
  compiled to CommonJS). Paths in TST-01 §3.1 and SDD-06 §10 read `.ts` here.
- **Answer key location.** TST-01 §4.3 puts it outside the system in
  `examples/sample-system-key/`. The task brief puts it in `.answers/` inside; the README rule
  above and the eval runner must exclude it.
- **Migrations path.** SDD-06 §7.2 and §10 use `api/migrations/`; TST-01 §4.5 uses
  `db/migrations/`, which this build follows. The companion `critical_paths` use `db/migrations/**`.
- **Jobs path.** TST-01 names `api/jobs/archive-orders.js`; SDD-06 names
  `api/src/jobs/purge-events.js`. Both jobs live in `api/src/jobs/`.
- **Tables.** TST-01 lists 6 tables; SDD-06's example adds `order_events`. Both are here (7).
