# Insights service

The Truminds insights service is one FastAPI application (`app.main:app`) plus a worker. It does the following:

- receives telemetry from `tsl`, Claude Code (OTLP/HTTP) and GitHub (webhooks);
- holds the signing-key registry used by `tsl` and CI;
- projects events into PostgreSQL 16;
- serves the read API behind the web portal.

It never runs an LLM, and it never calls Jira, Confluence, GitHub write APIs or any client system.

| Process | Command | Role |
| --- | --- | --- |
| `api` | `python -m app.entry api` (uvicorn, 2 workers; `/metrics` on internal port 9100) | Ingest, keys, read API, admin routes |
| `worker` | `python -m app.entry worker` (`/metrics` and `/healthz` on 9101) | Projector, view refresh, retention, partitions, outbox gauges, improvement report |
| `migrate` | `python -m app.entry migrate` | `alembic upgrade head` as `insights_owner`, then the first partitions |
| `admin` | `python -m app.entry admin <area> <op>` | Ingest tokens, GitHub hooks, catalogue sync, views, retention, user erase |
| `probe` | `python -m app.entry probe ready\|live` | Container health checks |

`app.entry` accepts only these five modes. The image has no hidden or debug mode.

## Set up

You need Python 3.12 with [uv](https://docs.astral.sh/uv/), and the PostgreSQL 16 binaries for the tests (`/usr/lib/postgresql/16/bin`, or set `PG_BIN`).

```bash
cd services/insights
uv sync                                  # runtime + dev dependencies from uv.lock
cp .env.example .env                     # placeholders only; secrets are *_FILE paths
```

Configuration comes only from environment variables (`app/config.py`, OPS-01 §5.3). Secrets are read only from files named by `*_FILE` variables. No secret, token or key is committed.

The policy decisions that are still open (registry §11) are config values. Their defaults follow the registry's recommendations:

| Decision | Variable | Default |
| --- | --- | --- |
| RD-1 who sees real names | `RD1_NAME_REVEAL_ROLES` | `eng_lead,admin` |
| RD-2 engineer run scope | `RD2_ENGINEER_RUN_SCOPE` | `system` |
| RD-3 question text in cloud | `RD3_QUESTION_TEXT_IN_CLOUD` | `false` |
| RD-4 audit retention | `AUDIT_RETENTION_MONTHS` | `36` |
| RD-5 first-pass metric | `RD5_FIRST_PASS_METRIC` | `first_try` |
| RD-6 workflow names | `RD6_WORKFLOW_NAMES` (catalogue sync skips the other set) | `doc3` |

## Identity provider: Entra (default) or GitHub (interim, test phase)

`IDENTITY_PROVIDER` picks the provider (SDD-07 §1.4, ADR 0006). The default `entra` is the production path and is unchanged. `github` is the interim provider for the test phase while the Entra app registrations are pending; the service refuses to start with it when `ENV=prod`.

| Setting | Default | Meaning |
| --- | --- | --- |
| `IDENTITY_PROVIDER` | `entra` | `entra` or `github` |
| `ENVIRONMENT` (or `ENV`) | `dev` | `test` makes `GET /v1/status` return `"environment": "test"`; the portal shows a TEST ENVIRONMENT banner |
| `GITHUB_CLIENT_ID` | — | Client ID of the GitHub OAuth App (Device Flow enabled) |
| `GITHUB_CLIENT_SECRET_FILE` or `GITHUB_CLIENT_SECRET` | — | Client secret, from the secret store (file) or the host env file. Never in git |
| `GITHUB_API_URL`, `GITHUB_OAUTH_URL` | `https://api.github.com`, `https://github.com` | GitHub endpoints |
| `GITHUB_TOKEN_CACHE_S` | `300` | How long a `GET /user` answer is cached, keyed by the SHA-256 of the token |
| `BOOTSTRAP_ADMIN_GITHUB_LOGINS` | empty | Comma-separated GitHub logins that get the org `viewer` and `admin` grants when they sign in. Logged at startup (`identity provider github ...` line) and audited per grant (`audit_log.action = bootstrap_admin_grant`). Clear it once a second admin exists; while a login is listed its admin grant comes back at each sign-in |
| `SESSION_MAX_AGE_S` | `28800` | Portal session cookie lifetime |

How it works with `github`:

- A bearer token (from `tsl`) is checked with `GET {GITHUB_API_URL}/user`. The user is `github:<numeric id>`; `users.github_login` holds the login. The token is never stored or logged.
- Roles come only from `role_grants`, managed in the portal admin screens. App roles are derived from the grants (`viewer` → Business, `engineer`/`skill_owner` → Engineer, `tech_lead`/`stage_approver`/`eng_lead` → TechLead, `admin` → Admin). A new user gets 403 `E-AUTH-08` naming their pseudonym until an admin grants a role.
- The portal signs in through `GET /auth/github/login` → GitHub → `GET /auth/github/callback` (state + PKCE; code exchanged with the client secret on the server). The token is kept encrypted (data key) inside a signed, HttpOnly, SameSite=Lax session cookie (Secure when `PUBLIC_BASE_URL` is https). `POST /auth/logout` clears it.
- A bearer token counts as `Events.Write` + `Portal.Read`; the session cookie counts as `Portal.Read` + `Portal.Write`. Writes through the cookie need `X-Requested-With: truminds-portal` and an `Origin` equal to the `PUBLIC_BASE_URL` origin (`E-API-07`).

## Hosted test environment (`allinone`, Render + Neon)

`python -m app.entry allinone` runs the whole service in one process for a single-container host. At start it waits for the database, runs the migrations, gives the runtime roles their logins, ensures the partitions, syncs the catalogue from `CATALOGUE_SOURCE_DIR` and registers webhooks. It then runs the worker jobs in a thread behind the leader advisory lock, and uvicorn on `$PORT`. Set-up: [deploy/render/README.md](../../deploy/render/README.md). These settings are for the test phase only; the service refuses the value secrets when `ENV=prod`.

| Setting | Default | Meaning |
| --- | --- | --- |
| `DATABASE_URL` | — | Owner URL, for example Neon's **direct** connection string. Must use TLS for a remote host; a `-pooler` host is refused. Replaces the `DATABASE_HOST`/`*_PASSWORD_FILE` settings |
| `DATABASE_URL_MIGRATIONS` | `DATABASE_URL` | Optional separate owner URL for Alembic |
| `DB_ROLE_PASSWORD_KEY` | — | At least 32 characters. The passwords of `insights_app`, `insights_read` and `insights_reveal` are HMAC-SHA256 of this key, and are set at each start |
| `DATA_KEY`, `PSEUDONYM_PEPPER` | — | The same secrets as `DATA_KEY_FILE` and `PSEUDONYM_PEPPER_FILE`, given as values. A `*_FILE` setting wins when both are set |
| `SERVE_PORTAL_DIR` | — | Serve the built portal from this folder (`/assets`, `/brand` and an SPA fallback that never answers `/v1`, `/auth`, `/otel`, `/metrics`, `/healthz` or `/readyz`), with the `portal/nginx.conf` security headers and HSTS when `PUBLIC_BASE_URL` is https |
| `GITHUB_WEBHOOK_HOOKS`, `GITHUB_WEBHOOK_SECRET` | empty | `HOOK_ID:org[/repo],...` registered at start with that secret (encrypted); replaces `admin hook create` where there is no shell |
| `PORT` | `10000` | HTTP port (also used by `probe`) |

`GET /healthz` (liveness) and `GET /readyz` (database, migration head, secrets; answers only ok or fail) are the platform probes. They are not in the OpenAPI file. In GitHub mode, readiness skips the Entra JWKS check.

## Run locally

```bash
uv run python -m app.entry migrate       # needs a database with insights_owner (see deploy/compose/postgres-init)
uv run python -m app.entry api
uv run python -m app.entry worker
uv run python seed/generate.py --catalogue ../..   # invented data; refuses ENV=prod
```

Regenerate the committed OpenAPI file after any route change. A test fails if it drifts.

```bash
uv run python -m app.openapi_dump > openapi/openapi.json
```

The image build context is the repository root, because ingest validates events against `schemas/`:

```bash
docker build -f services/insights/Dockerfile -t truminds/insights:X.Y.Z .
```

Deployment is in [`deploy/`](../../deploy/README.md) and monitoring is in [`ops/monitoring/`](../../ops/monitoring/README.md).

## Test

```bash
uv run pytest            # real PostgreSQL 16 (initdb + pg_ctl on a random port), no network, no Docker
INSIGHTS_TEST_PG_PORT=5432 uv run pytest   # CI: an empty postgres:16 service container that trusts `postgres`
uv run ruff check . && uv run ruff format --check .
uv run mypy              # strict, app + tests + seed
```

The tests work as follows:

- A session fixture creates a throwaway cluster with `initdb` and `pg_ctl` in a temporary directory, and runs the Alembic chain against it.
- Authentication uses a locally generated RSA key, published as a JWKS file through `ENTRA_JWKS_FILE`. The service validates those tokens with PyJWT exactly as it validates Entra tokens: signature, `iss`, `aud`, `tid`, `exp`, `nbf`, client id and scope. There is no bypass flag anywhere.
- `tests/test_tsl_contract.py` imports the real `tsl` client code from `tsl/src`: the outbox `events flush`, and key register and revoke. It drives that code against this service, so the wire shapes cannot drift apart.

| Area | Tests |
| --- | --- |
| Every endpoint in registry §4 | `test_health_obs.py::test_openapi_covers_registry_and_is_committed` plus a route-specific test per module |
| Ingest, idempotency, per-event codes E-ING-01..07, deny-list | `test_events.py` |
| Entra JWT through JWKS, wrong key, `alg=none`, HS256, audience, tenant, scope, app roles, ingest tokens | `test_auth.py` |
| HMAC rejection, delivery dedupe, `run_id` join with PR events | `test_webhook.py` |
| Keys: register, idempotent, E-KEY-02..06, revoked key rejected, `roles_at` history, signatures verify | `test_keys.py`, `test_tsl_contract.py` |
| Role filtering (business users see aggregates only), scope, name rule (RD-1), reveal role | `test_read_api.py` |
| Projection, order independence, parked events, sessions and devices | `test_projection.py` |
| OTLP JSON and protobuf, gzip, allowlist, content attributes dropped | `test_otel.py` |
| View refresh, partitions, retention and rollups, audit floor, outbox gauges, worker tick | `test_jobs.py` |
| Improvement flags and report job, `improvement.proposed` | `test_improvement.py` |
| Admin routes, self-grant refused (E-ADM-01), consent, deactivate, app-role sync | `test_admin.py` |
| GitHub provider (ADR 0006): `/user` validation and failure, 5-minute token cache keyed by SHA-256, GitHub down (E-AUTH-10), bootstrap admin, grants → app roles, cookie flow with state and PKCE, state mismatch (E-AUTH-09), open redirect, CSRF header and Origin (E-API-07), prod refusal, Entra JWT refused by a GitHub app | `test_github_auth.py` |
| Admin lists: admin only (403 otherwise), pagination, filters, RD-1 names | `test_admin_lists.py` |
| Health, readiness, `/metrics` labels, log redaction, entry modes, no committed secrets | `test_health_obs.py` |
| Seed refuses prod, seed loads | `test_seed.py` |

## Traceability

| Spec section | Module or file |
| --- | --- |
| SDD-08 §3.1 layout, §3.2 processes; OPS-01 §5.2 dispatcher | `app/main.py`, `app/entry.py`, `app/worker.py`, `Dockerfile` |
| SDD-08 §3.3 endpoint list; registry §4 | `app/api/v1/*`, `openapi/openapi.json` |
| SDD-08 §4.1–§4.2 `POST /v1/events`, one transaction per batch, idempotent on `event_id` | `app/api/v1/events.py`, `app/ingest/service.py` |
| SDD-08 §4.3 ingest codes; registry §2 service codes | `app/errors.py` |
| SDD-08 §4.4 content rules, SEC-01 §7.4 deny-list | `app/ingest/denylist.py`, `app/api/v1/policy.py`, migration `0005_denylist` |
| SDD-08 §4.5 event schemas through `schemas/index.json` (N and N-1) | `app/ingest/schemas.py` |
| SDD-08 §5 OTLP/HTTP logs and metrics, allowlist, run join | `app/api/v1/otel.py`, `app/otel/decode.py`, `app/otel/allowlist.yaml` |
| SDD-08 §6.1 GitHub webhook, HMAC `X-Hub-Signature-256` | `app/api/v1/webhooks_github.py`, `app/auth/github_hmac.py` |
| SDD-08 §6.2, SDD-07 §5.2–§5.6 keys: register, get, revoke, own keys | `app/api/v1/keys.py`, `app/keyreg.py` |
| SDD-07 §7.2 signature facts and anchors | `app/api/v1/signatures.py`, `app/projector/handlers.py` (anchors) |
| SDD-07 §9, ADR 0002 Entra JWT validation (PyJWT, JWKS) | `app/auth/entra.py`, `app/auth/principal.py`, `app/auth/scope.py` |
| SDD-07 §1.4, SDD-09 §3.4.1, ADR 0006 GitHub interim provider | `app/auth/github.py`, `app/auth/session.py`, `app/api/auth_github.py`, `app/auth/users.py` (`resolve_github_user`), `app/auth/principal.py` (`_github_principal`) |
| SDD-07 §3.3–§3.4 users, app-role sync, role grants | `app/auth/users.py` |
| SDD-08 §6.4 catalogue sync | `app/catalogue/sync.py` |
| SDD-08 §7 projector and the `run_id` join, order independence | `app/projector/loop.py`, `app/projector/handlers.py` |
| SDD-08 §8.1 pseudonymisation (`eng-xxxx`, peppered) | `app/auth/users.py`, `app/crypto.py` |
| SDD-08 §8.2 retention; RD-4 | `app/jobs/retention.py` |
| SDD-08 §9.2 column encryption (data key) | `app/crypto.py` |
| SDD-08 §9.3 ingest tokens (OTel, CI) | `app/auth/ingest_tokens.py`, `app/admin.py` |
| SDD-08 §9.4 DB roles; SDD-09 §5.3 `insights_reveal` | migration `0001_initial` (roles, grants, SECURITY DEFINER functions), `app/db.py`, `app/read/names.py` |
| SDD-08 §10.2 DDL | `alembic/versions/0001_initial.py` |
| SDD-08 §10.3 materialized views and views | `alembic/versions/0002_views.py`, `app/jobs/refresh_views.py` |
| SDD-08 §10.4 metric catalogue M-01..M-38 | `app/api/v1/read/insights.py`, `app/api/v1/read/catalogue.py` |
| SDD-08 §10.5, SDD-11 §4.5 improvement tables, `skill_window_stats` | `alembic/versions/0004_improvement.py` |
| SDD-08 §11.1 migrations and partitions | `alembic/`, `app/jobs/partitions.py` |
| SDD-08 §11.3 seed data | `seed/generate.py` |
| SDD-09 §5 read API E02–E22, role and scope filtering, classes A and B | `app/api/v1/read/*`, `app/read/access.py`, `app/read/common.py`, `app/read/labels.py` |
| SDD-09 §5.6.1 `/v1/me` | `app/api/v1/me.py` |
| SDD-10 §6 pods (cards, detail, metrics, runs, fit, one-pager) | `app/api/v1/read/pods.py` |
| SDD-11 §5.4 improvement endpoints; §3 signals; report job | `app/api/v1/improvement.py`, `app/jobs/improvement_report.py`, `app/improvement_thresholds.yaml` |
| SDD-12 §5.3 `GET /v1/systems/{code}` | `app/api/v1/systems.py` |
| SDD-13 §7.2 admin routes | `app/api/v1/admin.py` |
| SDD-13 §5.3, §7.2 admin lists | `app/api/v1/admin_lists.py` |
| OPS-02 §4 health and readiness | `app/api/v1/health.py`, `app/obs/probe.py` |
| OPS-02 §5 metrics, §6 logs | `app/obs/metrics.py`, `app/obs/logging.py` |
| OPS-02 §8.3 outbox backlog | `app/jobs/outbox_watch.py` |

## Not implemented here (by design)

- SDD-08 §3.2 serves the portal's static files from this image only when `SERVE_PORTAL=true`. The portal build itself belongs to `portal/`.
- Option E2 (OPS-01 §3.2), the GitHub polling relay, is not built: the edge is decided at hosting time (OQ-02).
