# Deploy: single-VM baseline (OPS-01, option H1)

This folder holds the deployment files for the insights service, the portal, PostgreSQL 16 and backups on one internal Linux VM with Docker Compose v2. Staging and prod use the same files. Only the host's env files, its secrets and its DNS name differ.

`deploy/**` contains secret names only, never values. Real values live in the host secret store and reach containers as tmpfs files.

```text
deploy/
├─ compose/
│  ├─ compose.prod.yml            # edge, api x2, worker, migrate, admin (profile), portal, postgres, backup
│  ├─ .env.example                # compose interpolation: registry and image digests
│  ├─ env/prod.env.example        # insights runtime config (non-secret), -> /etc/truminds/prod.env
│  ├─ env/backup.env.example      # pgBackRest repository location, -> /etc/truminds/backup.env
│  ├─ edge/nginx.conf             # TLS, routing, internal-only paths, E1 public allowlist
│  ├─ postgres/pg_hba.conf        # TLS + SCRAM for the four insights roles only
│  └─ postgres-init/10-insights-roles.sh   # first start: owner role, database, runtime roles
├─ images/pg-backup/              # postgres:16 + pgBackRest (DB server and backup service)
├─ scripts/fetch-secrets.sh       # secret store -> /run/truminds-secrets (tmpfs)
├─ systemd/                       # truminds-secrets.service, truminds-insights.service
└─ tests/test_deploy.py           # static checks, compose validation, live edge allowlist test
```

## Images

| Image | Built from | Entry |
| --- | --- | --- |
| `truminds/insights` | `services/insights/Dockerfile` (context: repo root) | `python -m app.entry api\|worker\|migrate\|admin\|probe` |
| `truminds/portal` | `portal/` (separate component) | nginx-unprivileged on 8080 |
| `truminds/pg-backup` | `deploy/images/pg-backup/Dockerfile` | `pg-backup-entry schedule\|backup\|info\|check\|restore`; anything else runs the upstream postgres entrypoint |
| `nginx` | upstream, pinned by digest | `edge/nginx.conf` |

Every image is referenced by digest (`*_DIGEST` in `compose.env`). Only the release pipeline pushes images (OPS-03 §3).

## Host set-up (once per environment)

1. Put the data volume on LUKS or a hypervisor-encrypted disk, with its key outside the VM (OPS-01 §8.2). Then run `install -d -o 999 -g 999 -m 0700 /srv/truminds/pgdata /srv/truminds/pgspool`.
2. Create the secrets group: `groupadd -g 990 truminds-secrets`. Containers that read secrets run with `group_add: ["990"]`.
3. Copy `deploy/` to `/opt/truminds/deploy`. Fill `/etc/truminds/{compose.env,prod.env,backup.env}` from the `*.example` files.
4. Store these entries in the secret store. Names are in `fetch-secrets.sh`, and OPS-01 §7.3 gives each one's rotation:
   - DB passwords for `postgres`, `insights_owner`, `insights_app`, `insights_read` and `insights_reveal`;
   - the pepper;
   - the wrapped data key;
   - the catalogue read token;
   - the backup cipher key and storage keys;
   - the TLS files. Use the internal CA for `intranet.*`, a public CA for `public.*` (E1 only), and a DB server certificate for host `postgres` plus its CA.
5. Install both systemd units, then run `systemctl enable --now truminds-secrets truminds-insights`.
6. Create ingest tokens through the admin profile. Each token prints once, so store it straight into the secret store or managed settings:

   ```bash
   docker compose -f compose.prod.yml --env-file /etc/truminds/compose.env --profile admin \
     run --rm admin admin token create --kind ci --label example-org
   ```
7. Work through the hosting checklist in OPS-01 §11.

## Deploy a release (OPS-01 §8.3)

```bash
docker compose ... run --rm backup backup full                  # on-demand backup before migrating
sed -i 's/^INSIGHTS_DIGEST=.*/INSIGHTS_DIGEST=sha256:<new>/' /etc/truminds/compose.env
docker compose ... up -d migrate && docker compose ... up -d api worker   # api waits for migrate
curl -fsS https://<host>/v1/health                              # smoke test
```

Migrations are expand-only, so rolling back means redeploying the previous image digest (OPS-03 §5). The restore procedure is OPS-01 §9.3: `docker compose run --rm backup restore --type=time "--target=<UTC>"` with `api` and `worker` stopped.

## Network and exposure

- Only `edge` publishes ports. `app` and `db` are internal networks, so PostgreSQL and ports 9100 and 9101 are never reachable from outside.
- `egress` is the one outbound network. It is attached to `api` (Entra JWKS), `worker` (marketplace repo) and `backup` (backup store). The host firewall limits it to those destinations.
- The edge returns 404 for `/metrics` and `/v1/health/ready`.
- The public server on container port 9443 is the option E1 allowlist from OPS-01 §3.1:
  - `POST /v1/webhooks/github`;
  - `POST /v1/events`, `GET /v1/keys/key_<ULID>` and `POST /v1/signatures/verify`, each only with a CI ingest token (`tsi_ci_…`);
  - everything else returns 404.

  It is bound to `127.0.0.1` until Puneet chooses E1. Under E2, remove that server block.
- TLS 1.2 and 1.3 only, with HSTS. Services reach PostgreSQL with `sslmode=verify-full`.

## Test

```bash
# from the repository root, with the insights venv
services/insights/.venv/bin/python -m pytest deploy/tests          # set NGINX_BIN if nginx is not on PATH
```

The suite covers:

- Static checks: only the edge publishes ports, images are pinned by digest, the insights services are hardened, every secret is fetched, and no secret material is in `deploy/`.
- Bash syntax of every script.
- `docker compose config` validation, which needs the CLI but no daemon.
- A live nginx run against a stub upstream that checks intranet routing and the E1 allowlist. It is skipped when nginx is not installed.

## Traceability

| Spec section | File |
| --- | --- |
| OPS-01 §2 components, §6.2 compose baseline | `compose/compose.prod.yml` |
| OPS-01 §3.1–§3.2 path exposure, E1 allowlist | `compose/edge/nginx.conf` (public server), `tests/test_deploy.py::test_public_allowlist` |
| OPS-01 §5.2 `app.entry` dispatcher | `services/insights/app/entry.py`, `services/insights/Dockerfile` |
| OPS-01 §5.3 runtime configuration | `compose/env/prod.env.example`, `compose/.env.example` |
| OPS-01 §6.3 edge routing, §7.1 TLS | `compose/edge/nginx.conf` |
| OPS-01 §7.2–§7.3 secrets from the host store | `scripts/fetch-secrets.sh`, `systemd/truminds-secrets.service` |
| OPS-01 §8.1 DB roles and settings; SDD-08 §9.4; SDD-09 §5.3 reveal role | `compose/postgres-init/10-insights-roles.sh`, `compose/postgres/pg_hba.conf` |
| OPS-01 §8.2 encryption at rest | Host set-up step 1; backups encrypted by `repo1-cipher-type` |
| OPS-01 §9 backup and restore (pgBackRest, 35 days, WAL) | `images/pg-backup/*`, `backup` and `postgres` services |
| OPS-02 §4.1 probes | `api` and `worker` health checks in `compose.prod.yml` |

## Deviations from the OPS-01 sketch

Each of these is needed to make the sketch work. They should be folded back into OPS-01:

- **`egress` network.** In the sketch, `api` sits only on internal networks, so it cannot fetch the Entra JWKS and readiness would fail. The `worker` and `backup` services also need outbound access.
- **`postgres` runs the `pg-backup` image.** The upstream `postgres:16` image has no `pgbackrest`, so the sketch's `archive_command` cannot work. The pg-backup image is `postgres:16` plus pgBackRest.
- **Postgres and backup share a socket volume.** pgBackRest connects to the database only through the local socket.
- **`db_reveal_password` secret.** This is the `insights_reveal` role from SDD-09 §5.3; OPS-01 §7.3 predates it.
- **`db_ca`.** It is mounted for `sslmode=verify-full`.
- **Secrets group gid 990.** Docker file secrets keep host ownership, and the same files must be readable by uid 10001 (insights) and uid 999 (postgres init).
