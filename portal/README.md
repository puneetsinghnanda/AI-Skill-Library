# Truminds AI Skill Library portal

The intranet web portal of the AI Skill Library (SDD-09). It is a read-only React single-page app
over the insights read API (`services/insights`, `GET /v1/...`), plus admin screens under `/admin`
for the Entra app role Admin only, which call the admin API (SDD-09 §4.16, SDD-13 §7.2). It has two persona views, Business
unit and Engineers, and the 15 prototype boards in `docs/ux/prototype/` are its visual source. It
never starts a run and writes to no external system (SDD-09 §1.3).

| Item         | Value                                                                                                               |
| ------------ | ------------------------------------------------------------------------------------------------------------------- |
| Primary spec | [SDD-09 Web portal and read API](../docs/design/SDD-09-web-portal.md)                                               |
| Design       | [Doc 4 Design and UX](../docs/ux/04-design-and-ux.md) §2.0, §6 · [prototype](../docs/ux/prototype/README.md)        |
| Backend      | [services/insights](../services/insights/) (routes in `app/api/v1/read/`, OpenAPI in `openapi/openapi.json`)        |
| Tests        | [TST-01](../docs/testing/TST-01-master-test-plan.md) §2.5, TC-POR-001 to TC-POR-012                                 |
| Hosting      | [OPS-01](../docs/operations/OPS-01-deployment-hosting.md) §5.2 · `deploy/compose/compose.prod.yml` service `portal` |

## Stack

Vite 5, React 18, TypeScript (`strict`), React Router 6 (data router), TanStack Query 5, MSAL React 2
with MSAL Browser 3 (auth code + PKCE against Microsoft Entra ID). API types are generated from the
committed OpenAPI with `openapi-typescript` 7. Charts are own SVG/CSS components with a table view.
Fonts are IBM Plex Sans and Mono from `@fontsource/*`, bundled and served from the same origin. No CSS
framework and no state library besides TanStack Query and one React context for the view.

## Set up

Node 20 LTS (`.nvmrc`); Node 22 also works.

```sh
cd portal
npm ci
cp .env.example .env.development.local   # dev Entra app IDs; never committed (DEV-01 §3)
```

| Variable                                                                                       | Meaning                                                                |
| ---------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------- |
| `VITE_ENTRA_TENANT_ID`, `VITE_ENTRA_CLIENT_ID`                                                 | Entra tenant and the SPA app registration `truminds-portal` (ADR 0002) |
| `VITE_ENTRA_REDIRECT_URI`                                                                      | Defaults to `<origin>/auth/callback`                                   |
| `VITE_API_SCOPE`                                                                               | `api://truminds-insights/Portal.Read` (SDD-07 §9)                      |
| `VITE_API_WRITE_SCOPE`                                                                         | `api://truminds-insights/Portal.Write`; admin actions only (§4.16)     |
| `VITE_API_BASE_URL`                                                                            | Empty: same origin, `/v1` behind the edge                              |
| `VITE_MARKETPLACE_REPO_URL`                                                                    | Skill Library repo; replaces `[TRUMINDS-ORG]` (OQ-10)                  |
| `VITE_PILOT_MAILTO`                                                                            | "Request a pilot" inbox (SDD-10 O-06); the button is hidden when empty |
| `VITE_HELP_URL`, `VITE_ENV_NAME`, `VITE_BUILD_ID`                                              | Footer help link, environment and build id                             |
| `VITE_RD1_NAME_REVEAL_ROLES`, `VITE_RD2_ENGINEER_RUN_SCOPE`, `VITE_RD3_QUESTION_TEXT_IN_CLOUD` | Open decisions RD-1 to RD-3 (registry §11), defaults as recommended    |

None of these are secrets: the SPA holds no secret.

## Run

| Command         | What it does                                                                                                                                                                                                                                                                                                                                                                                                   |
| --------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `npm run dev`   | Vite on port 5173 with real Entra sign-in; proxies `/v1` to the insights api on port 8000                                                                                                                                                                                                                                                                                                                      |
| `npm run demo`  | Builds the explicit demo bundle (`--mode demo`) and serves it on port 4173 with the production CSP. MSW mocks the API in the browser and a test token-cache fixture stands in for MSAL. All data is invented and labelled "Illustrative data". Switch the demo user (viewer, engineer and tech lead, engineering lead, insights admin) in the banner, or with `?demo_user=`, `?demo_behind=1`, `?demo_empty=1` |
| `npm run build` | Typecheck, production build to `dist/`, then the bundle gate (`scripts/check-bundle.mjs`)                                                                                                                                                                                                                                                                                                                      |

The demo is never the production bundle. `main.tsx` picks the demo entry only when Vite's `MODE` is
`demo`; the production build drops that branch, and the bundle gate fails if `dist/` contains the
fixture marker `TM_TEST_AUTH_FIXTURE`, a fixture token, MSW, the MSW worker, "Illustrative data" or
any fixture value (TC-POR-010). There is no auth bypass flag in any build.

## Test and check

| Command                | Checks                                                                                                                                                             |
| ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `npm run lint`         | ESLint (typescript-eslint, react-hooks, jsx-a11y strict, no mock imports from app code, no hex colours), Stylelint (`color-no-hex` outside `tokens.css`), Prettier |
| `npm run typecheck`    | `tsc --noEmit` for the app (strict) and the configs and e2e                                                                                                        |
| `npm test`             | Vitest + Testing Library + vitest-axe, with MSW in Node (no network)                                                                                               |
| `npm run e2e`          | Playwright on Chromium against `npm run demo`, with `@axe-core/playwright`                                                                                         |
| `npm run check:api`    | `src/api/schema.d.ts` matches what the OpenAPI generates (CI fails on drift)                                                                                       |
| `npm run check:tokens` | WCAG contrast of every pair in `src/theme/tokens.pairs.json`                                                                                                       |
| `npm run check`        | All of the above plus the build                                                                                                                                    |

Playwright uses the browsers pre-installed under `PLAYWRIGHT_BROWSERS_PATH`; `playwright.config.ts`
falls back to `/opt/pw-browsers/chromium` when the pinned version's build is missing. Do not run
`playwright install` in the sandbox.

`npm run gen:api` regenerates `src/api/schema.d.ts`. The OpenAPI declares every read response as an
open object (`additionalProperties: true`), so request paths and query parameters are generated and
the response bodies are typed by hand in `src/api/types.ts` from the route code. `client.ts` fails to
compile if a route in `ResponseMap` is not a GET path of the OpenAPI; `api/contract.test.ts` checks
the routes, methods and query parameters at run time (TC-POR-009).

## Hosting

`Dockerfile` builds `truminds/portal`: a `node:20-alpine` build stage runs `npm run build` (with the
bundle gate) and an `nginxinc/nginx-unprivileged` stage serves `dist/` on 8080 as uid 101. It fits the
compose `portal` service: read-only root filesystem, tmpfs on `/tmp` and `/var/cache/nginx`, all
temp paths and the pid file under `/tmp`, `cap_drop: [ALL]`. Base images are pinned by digest in the
release pipeline (OPS-03 §3); the tags in the Dockerfile are the floor.

```sh
docker build -t truminds/portal:X.Y.Z \
  --build-arg VITE_ENTRA_TENANT_ID=<tenant> --build-arg VITE_ENTRA_CLIENT_ID=<spa app> \
  --build-arg VITE_MARKETPLACE_REPO_URL=https://github.com/<org>/truminds-skill-library \
  --build-arg VERSION=X.Y.Z --build-arg REVISION=$(git rev-parse HEAD) portal/
```

`nginx.conf` sends the strict CSP of SDD-09 §10 (`default-src 'self'`, no inline script or style,
Entra login host only in `connect-src` and `frame-src`, `frame-ancestors 'none'`), `nosniff`,
`no-referrer`, a Permissions-Policy, `X-Frame-Options: DENY` and COOP/CORP same-origin. `index.html`
is `no-cache`; hashed assets are `immutable` for a year. Every path that is not a file falls back to
`index.html`; `/v1/`, `/otel/`, dotfiles, source maps and the MSW worker return 404; only GET and
HEAD are allowed; `/healthz` serves the container health check. TLS, HSTS and routing of `/v1` stay
at the edge (`deploy/compose/edge/nginx.conf`). The same CSP is applied by `vite preview`, so the e2e
suite runs under it (and fails on any CSP violation).

## Sign-in and data rules

| Rule                                                                                                                                                                                                           | Where                                                                                                |
| -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| Authorization code + PKCE, redirect flow; tokens in `memoryStorage` only; a reload tries `ssoSilent`, then redirects                                                                                           | `src/auth/msal.tsx`                                                                                  |
| MSAL does not reload after the redirect (`navigateToLoginRequestUrl: false`), so in-memory tokens survive; the original path returns through `state` (same-origin paths only)                                  | `src/auth/msal.tsx`                                                                                  |
| `acquireTokenSilent` before each request; on 401 one silent retry with `forceRefresh`, then sign-in                                                                                                            | `src/api/client.ts`                                                                                  |
| Every request sends `X-Request-ID`; errors show the code and request id                                                                                                                                        | `src/api/client.ts`, `src/components/States.tsx`                                                     |
| The persona switch is shown only when `me.can_switch_view` (both roles) and changes layout only                                                                                                                | `src/app/ViewContext.tsx`, `src/app/TopBar.tsx`                                                      |
| Business screens call class A routes only and render no run ids, tickets, repos, system codes or names; Run detail, Engineering monitoring and the improvement report send a Business view to Insights         | `src/app/routes.tsx`, TC-POR-002/003 tests                                                           |
| RD-1: "Show names" appears only when `me.can_reveal_names`; off by default, not remembered; the server audits each reveal                                                                                      | `InsightsEngineering.tsx`, `RunDetail.tsx`, `config/policy.ts`                                       |
| RD-2: the server resolves scope; filters only offer the caller's own projects and systems from `/v1/me`                                                                                                        | `InsightsEngineering.tsx`                                                                            |
| RD-3: question text is never shown; the card links `open-questions.md` in the companion repo                                                                                                                   | `HomeEngineer.tsx`, `RunDetail.tsx`                                                                  |
| Null numbers show "No data yet" or "Not enough data", never sample numbers                                                                                                                                     | `components/StatTile.tsx`                                                                            |
| Admin screens: nav entry and `/admin/*` only for app role Admin (others get Not found); `Portal.Write` requested only when an admin action is submitted; destructive actions confirm first; no automatic retry | `api/admin.ts`, `app/routes.tsx`, `app/TopBar.tsx`, `screens/admin/`, `components/ConfirmDialog.tsx` |

## Brand swap

Every colour, font and radius is a CSS variable in `src/theme/tokens.css`, with the prototype
`brand.css` names (`--tm-primary`, `--tm-accent-ink`, `--tm-pass`, ...). Components use `var(--tm-*)`
only; Stylelint and ESLint fail on hex colours anywhere else. To swap the brand: edit `tokens.css` and
`public/brand/logo.svg`, `favicon.svg`, then run `npm run check:tokens`, the axe suites and a visual
review. One file plus two SVGs (SDD-09 §9). The contrast gate caught one prototype value: the
"illustrative" orange `#B4570B` on its tint is 4.19:1, so `--tm-highlight` is `#9A4A08` (5.38:1).

## Traceability

| SDD-09 section                                     | Implemented in                                                                                                                                                 |
| -------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| §3.1 Stack                                         | `package.json`, `vite.config.ts`, `tsconfig.json`                                                                                                              |
| §3.2 Code layout                                   | `src/` as listed (`auth/`, `api/`, `app/`, `screens/`, `components/`, `content/`, `theme/`, `lib/`)                                                            |
| §3.3 Routes                                        | `src/app/routes.tsx` (`/pods/builder` before `/pods/:podId`; no-grant page `screens/NoAccess.tsx`)                                                             |
| §3.4 Sign-in                                       | `src/auth/msal.tsx`, `src/auth/startProd.tsx`, `src/auth/port.tsx`, `src/screens/AuthCallback.tsx`                                                             |
| §3.5 Data fetching                                 | `src/api/queries.ts` (keys, staleTime, retry, infinite paging, loaders), `src/api/client.ts`                                                                   |
| §3.6 Views, states, banner                         | `src/app/ViewContext.tsx` (`tm.view`), `src/app/StatusBanner.tsx`, `src/components/States.tsx`                                                                 |
| §4.1 Shell                                         | `src/app/AppShell.tsx` (skip link, focus to h1, footer with build id and "Need help?")                                                                         |
| §4.2 Top bar                                       | `src/app/TopBar.tsx` (search over catalogue skills and pods)                                                                                                   |
| §4.3 Home: Business                                | `src/screens/HomeBusiness.tsx`                                                                                                                                 |
| §4.4 Home: Engineer                                | `src/screens/HomeEngineer.tsx`                                                                                                                                 |
| §4.5 How it works                                  | `src/screens/HowItWorks.tsx`, `src/content/how-it-works.ts`                                                                                                    |
| §4.6 Skills                                        | `src/screens/Skills.tsx`                                                                                                                                       |
| §4.7 Skill detail                                  | `src/screens/SkillDetail.tsx`                                                                                                                                  |
| §4.8 Get started                                   | `src/screens/GetStarted.tsx`, `src/content/get-started.ts`                                                                                                     |
| §4.9 Pods                                          | `src/screens/Pods.tsx`                                                                                                                                         |
| §4.10 Pod detail, one-pager                        | `src/screens/PodDetail.tsx`, `src/screens/PodOnePager.tsx`, `src/components/SafeMarkdown.tsx`                                                                  |
| §4.11 Pod builder (static Phase 3 notice)          | `src/screens/PodBuilder.tsx`                                                                                                                                   |
| §4.12 Insights: Business                           | `src/screens/InsightsBusiness.tsx`, `src/components/Charts.tsx`, `src/components/CapabilityMapTable.tsx`                                                       |
| §4.13 Insights: Engineering                        | `src/screens/InsightsEngineering.tsx` (tabs runs, skills, usage, health)                                                                                       |
| §4.14 Run detail                                   | `src/screens/RunDetail.tsx`                                                                                                                                    |
| §4.15 Persona map                                  | Not a route (design reference); its rules are in §3.6, §5.3 and the role tests                                                                                 |
| §5.1 Conventions (envelope, errors, paging, nulls) | `src/api/types.ts`, `src/api/client.ts`, `src/components/States.tsx`                                                                                           |
| §5.3 Name rule (UI side)                           | `InsightsEngineering.tsx`, `RunDetail.tsx`, `config/policy.ts`                                                                                                 |
| §5.5, §5.6 Endpoints E01-E23 (client side)         | `src/api/types.ts` (`ResponseMap`), `src/api/queries.ts`, `src/api/schema.d.ts`                                                                                |
| §6 Capability map and share view                   | `src/screens/CapabilityMapShare.tsx`, `src/components/CapabilityMapTable.tsx`                                                                                  |
| §7 Adoption measures                               | Usage tab (weekly G1, M-36), Health tab (M-37), share-map totals (M-38)                                                                                        |
| §8 Accessibility                                   | `src/theme/base.css`, `components/Tabs.tsx`, `FilterChips.tsx`, `TableRegion.tsx`, `Charts.tsx`; `src/test/a11y.test.tsx`, `e2e/accessibility.spec.ts`         |
| §9 Brand-token swap                                | `src/theme/tokens.css`, `tokens.pairs.json`, `scripts/check-tokens.mjs`, `.stylelintrc.json`                                                                   |
| §10 Intranet hosting                               | `Dockerfile`, `nginx.conf`, `vite.config.ts` (`preview.headers`)                                                                                               |
| §11 Test plan (SPA rows)                           | see below                                                                                                                                                      |
| SDD-11 §4.4, §5.4 Improvement report (GET)         | `src/screens/ImprovementReport.tsx`                                                                                                                            |
| §4.16 Admin screens and lists (SDD-13 §7.2)        | `src/screens/admin/*` (lists in `lists.tsx`), `src/api/admin.ts`, `src/api/client.ts` (`post`), `src/components/ConfirmDialog.tsx`; mocks `src/mocks/admin.ts` |

| Test case                                                                             | Test                                                                                            |
| ------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| TC-POR-001 top bar, navigation, active tab                                            | `e2e/navigation.spec.ts`, `src/app/roles.test.tsx`                                              |
| TC-POR-002 Business never sees run ids, tickets, repos, names                         | `e2e/navigation.spec.ts` (pages and class A responses), `src/app/roles.test.tsx`                |
| TC-POR-003 Run detail redirects Business to Insights                                  | `e2e/navigation.spec.ts`, `src/app/roles.test.tsx`                                              |
| TC-POR-004 "No data yet"                                                              | `src/components/StatusBadge.test.tsx`, `src/screens/screens.test.tsx`, `e2e/navigation.spec.ts` |
| TC-POR-005 behind banner                                                              | `src/screens/screens.test.tsx`, `e2e/navigation.spec.ts`                                        |
| TC-POR-006 axe on every screen, both views                                            | `src/test/a11y.test.tsx`, `e2e/accessibility.spec.ts` (plus keyboard and 320 px reflow)         |
| TC-POR-007 status always a word                                                       | `src/components/StatusBadge.test.tsx`                                                           |
| TC-POR-008 load within 3 s                                                            | `e2e/navigation.spec.ts` (demo data; the seeded-API run belongs to the service CI)              |
| TC-POR-009 fixtures agree with the OpenAPI                                            | `src/api/contract.test.ts`                                                                      |
| TC-POR-010 no test-auth fixture in production                                         | `scripts/check-bundle.mjs` (runs in `npm run build`)                                            |
| TC-POR-011 shared map hides pilot skills                                              | `e2e/navigation.spec.ts`, `src/screens/screens.test.tsx`                                        |
| TC-POR-012 token contrast and no hex outside tokens                                   | `scripts/check-tokens.mjs`, Stylelint, ESLint                                                   |
| §4.5 commands match Doc 5 §2 and the plugin                                           | `src/content/commands.test.ts`                                                                  |
| §4.16 admin visibility, validation, confirmations, write scope, lists and row actions | `src/screens/admin/admin.test.tsx`, `src/test/a11y.test.tsx`, `e2e/admin.spec.ts`               |

## Known gaps and decisions

- Get started follows Doc 4 §2.0.2 and SDD-13 §3: the plugin is installed by managed settings, so the
  five engineer steps are install `tsl`, `tsl login`, `tsl doctor`, confirm with `/truminds:status`,
  clone the companion repo and run. The prototype's "add marketplace, install plugin" steps are in a
  collapsed "Development seats only" note (SDD-13 OI-13-08).
- Command strings use the registry §3 names (`tsl init`, `tsl context build`, `tsl context sign`),
  not the prototype's older `tsl init-context`. There is no plugin manifest listing commands yet, so
  the test checks each `/truminds:*` command against the plugin's skill folders.
- `PATCH /v1/improvement/flags/{flag_id}` needs `Portal.Write`; outside the admin screens the
  portal requests only `Portal.Read`, so flag status changes stay in `tsl improve plan`.
- The admin screens list clients, projects, systems, role grants, users and a user's keys from the
  `GET /v1/admin/...` routes (`Portal.Read`, paged with "Show more"); revoke grant, revoke key and
  deactivate user are row actions behind the same confirmation dialog as the forms. The screens
  never ask for names (`include=names`).
- Pod cards: the server gives `best_for` and `metrics` to viewer-only callers and `workflows` and
  `skill_count` to everyone else (SDD-10 §6.1). In the Business view of an engineer-family user the
  card fetches E10 for the first-try pass and omits "Best for".
- Fonts come from `@fontsource/*` (bundled, same origin) rather than files under `src/theme/fonts/`.
- Hosting: this separate nginx image behind the edge (OPS-01 §5.2). SDD-09 §10 now says the same
  (registry §10 #41).
