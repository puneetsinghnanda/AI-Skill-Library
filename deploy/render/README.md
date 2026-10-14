# Hosted test environment: Render + Neon

This is the test environment for the six testers, hosted on the internet with GitHub sign-in ([ADR 0006](../../docs/adr/0006-interim-github-sign-in-for-test-phase.md) and its hosting addendum). **Test phase only.** It holds invented data, and no client repository is ever pointed at it.

```text
 testers' laptops                        Render (free web service)                  Neon (free)
 ┌──────────────────────────────┐ HTTPS  ┌──────────────────────────────────┐ TLS    ┌──────────────┐
 │ Claude Code + truminds plugin│──────► │ one container (deploy/render/    │──────► │ PostgreSQL   │
 │ tsl (login, verify, decide,  │        │ Dockerfile, `allinone`):         │        │ (database    │
 │      pr, events)             │        │  portal · insights API ·         │        │  `neondb`)   │
 │ browser → portal             │──────► │  GitHub sign-in · worker jobs    │        └──────────────┘
 └──────────────────────────────┘        └──────────────▲───────────────────┘
          │ git push, PRs                               │ webhooks (PR events)
          ▼                                             │
 GitHub: repos, PRs, CI, lead approval, OAuth App ──────┘
```

What runs where:

| Where | What |
| --- | --- |
| Render | One container: the portal, the insights API, GitHub sign-in and the background jobs (view refresh, retention, partitions, outbox gauges, improvement report) |
| Neon | The PostgreSQL database |
| Testers' laptops | Skills, Claude Code, `tsl` and every harness decision |
| GitHub | Repos, PRs, CI, lead approval, webhooks, and the OAuth App used for sign-in |

The order below matters: **A → B → C → D → E**, then **F** when PRs start.

**Before you start:** Render deploys what is on `main`. Apply the patch that adds this folder and `render.yaml`, then push it to `main`.

**Pick the service name now**, because every URL derives from it. This guide uses `truminds-skills-test`, so the URL is `https://truminds-skills-test.onrender.com`. If Render says the name is taken, it adds a suffix (for example `truminds-skills-test-a1b2`). Use the exact URL Render shows wherever this guide writes `https://<name>.onrender.com`.

## A. Neon (the database)

1. Go to <https://neon.com> and click **Sign up**. Choose **Continue with GitHub**.
2. Click **New project**:
   - **Project name:** `truminds-skills-test`
   - **Postgres version:** **16** (the code is tested on 16)
   - **Cloud provider / region:** **AWS Asia Pacific (Singapore)**. Neon has no region in India. Singapore is the closest one, and it sits next to Render's Singapore region, which matters more: only Render talks to the database.
   - **Database name:** leave `neondb`.
3. Click **Create project**.
4. On the project dashboard, click **Connect**. In the dialog:
   - **Branch** `main`, **Database** `neondb`, **Role** `neondb_owner`.
   - Turn **Connection pooling OFF**. The host name must **not** contain `-pooler`.
   - Copy the connection string. It looks like `postgresql://neondb_owner:…@ep-xxxx-xxxx.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require`.
5. Keep it for step C as `DATABASE_URL`. **Do not paste it anywhere else** (chat, issue, file in git).

Why the direct (non-pooled) string: the service keeps a session open for its job lock and per-session settings. Neon's pooler (PgBouncer in transaction mode) drops those, so the service refuses a `-pooler` host at start. Six testers need only a handful of connections, well within the direct limit.

You do not create any other role or table. At each start, the service runs the migrations as `neondb_owner`. That creates three NOLOGIN roles (`insights_app`, `insights_read`, `insights_reveal`), and the service then gives them logins with passwords derived from `DB_ROLE_PASSWORD_KEY`. The API itself never connects as the owner. This was tested on PostgreSQL 16 with an owner that is not a superuser and has CREATEROLE, which is what `neondb_owner` is.

## B. GitHub OAuth App (sign-in)

1. On GitHub: your avatar → **Settings** → **Developer settings** → **OAuth Apps** → **New OAuth App**. Use the test org's settings instead if you created one.
2. Fill in:

| Field | Value |
| --- | --- |
| Application name | `Truminds Skill Library (TEST)` |
| Homepage URL | `https://<name>.onrender.com` |
| Authorization callback URL | `https://<name>.onrender.com/auth/github/callback` |
| Enable Device Flow | **ticked** (`tsl login` uses it) |

3. Click **Register application**.
4. Copy the **Client ID**.
5. Click **Generate a new client secret** and copy the secret. It is shown once.

Keep both for step C.

## C. Render (the service)

1. Go to <https://dashboard.render.com> and sign in with **GitHub**.
2. When Render asks for repository access, choose **Only select repositories** → `puneetsinghnanda/AI-Skill-Library` → **Install**. You can change this later in GitHub → Settings → Applications → Render → Configure.
3. Click **New +** → **Blueprint**.
4. Pick `puneetsinghnanda/AI-Skill-Library`, then **Connect**. Render reads `render.yaml` from `main`.
5. Blueprint name: `truminds-skills-test`. Render lists one web service, `truminds-skills-test` (Docker, Free, Singapore).
6. Render asks for the values marked `sync: false`. Enter:

| Key | Value |
| --- | --- |
| `DATABASE_URL` | The Neon **direct** connection string from A.4 |
| `PUBLIC_BASE_URL` | `https://<name>.onrender.com` (no trailing slash) |
| `GITHUB_CLIENT_ID` | Client ID from B.4 |
| `GITHUB_CLIENT_SECRET` | Client secret from B.5 |
| `GITHUB_WEBHOOK_SECRET` | A new random value of at least 20 characters. In PowerShell: `[guid]::NewGuid().ToString('N') + [guid]::NewGuid().ToString('N')` (64 characters). Keep it for step F |
| `BOOTSTRAP_ADMIN_GITHUB_LOGINS` | Your GitHub login (for example `puneetsinghnanda`) |

   Render generates `DATA_KEY`, `PSEUDONYM_PEPPER` and `DB_ROLE_PASSWORD_KEY` itself and keeps them across deploys. **Never edit or delete those three while the database holds data.** `DATA_KEY` encrypts names and the session cookie, and the other two must match what is already in the database.
7. Click **Apply** (or **Deploy Blueprint**). The first build takes about 10 minutes.
8. Open the service → **Logs**. A good start shows, in order:
   - `Running upgrade … 0005_denylist`
   - `runtime role logins set`
   - `catalogue synced` (`17 skills, 9 workflows, 4 pods` or similar)
   - `identity provider github (interim, ADR 0006); environment=test; …`
   - `Uvicorn running on http://0.0.0.0:10000`
9. In a browser:
   - `https://<name>.onrender.com/healthz` shows `{"status":"ok"}`.
   - `https://<name>.onrender.com/readyz` shows `{"status":"ok"}` (database, migrations and secrets).
10. Open `https://<name>.onrender.com`. You see the **TEST ENVIRONMENT** banner. Click **Sign in with GitHub**, then authorize the app. You are admin, because your login is in `BOOTSTRAP_ADMIN_GITHUB_LOGINS`.

If the URL Render gave you differs from the one you entered in B, fix it in three places: the OAuth App (Homepage and callback), Render → Environment → `PUBLIC_BASE_URL` (then **Save, rebuild and deploy**), and the tsl org file in E.

Every push to `main` redeploys. The database and the three generated keys stay; the catalogue syncs again at start.

## D. Add the testers

1. Each tester signs in once at `https://<name>.onrender.com` with **Sign in with GitHub**, or runs `tsl login` (E.3). They see "No Truminds role yet" with their pseudonym, and their account now exists.
2. In the portal, go to **Admin**:
   - Create the client, project and systems the testers work on (invented names only, for example client `EXAMPLE`, system `sample-system`).
   - Open **Users** and click **Show names** (it shows `@<github login>`). Give each of the 6 testers every role: `viewer` (org), `engineer` and `tech_lead` on the systems, `skill_owner`, `stage_approver`, `eng_lead` and `admin`.
3. **Admins cannot grant themselves (E-ADM-01).** Make one tester admin first. That tester then grants you your own roles.
4. Once a second admin exists, clear `BOOTSTRAP_ADMIN_GITHUB_LOGINS` in Render → Environment. Otherwise your `admin` grant comes back at every sign-in.

## E. Tester set-up (each tester, Windows PowerShell)

Prerequisites: TST-02 §3 steps 1–3 (Git, uv, the repository cloned to `C:\dev\AI-Skill-Library`).

1. Create the org file (once):
   ```powershell
   cd C:\dev\AI-Skill-Library
   Copy-Item deploy\render\tsl-org.github.toml.example deploy\render\tsl-org.github.toml
   notepad deploy\render\tsl-org.github.toml
   ```
   Set `github_client_id` to the OAuth App's Client ID and `service_url` to `https://<name>.onrender.com`, then save. The file is git-ignored. It holds no secret.
2. Install `tsl` with the org file baked in:
   ```powershell
   $env:TSL_ORG_FILE = "$PWD\deploy\render\tsl-org.github.toml"
   uv tool install --python 3.12 --reinstall --no-cache .\tsl
   Remove-Item Env:TSL_ORG_FILE
   tsl --version
   ```
   `--reinstall --no-cache` forces uv to rebuild the wheel, so the build hook (`tsl/hatch_build.py`) bakes in this file. Without them, a cached build would keep the placeholder file. Do not use `--editable` for this install.
3. Open the portal URL in a browser first, to wake the service (see G). Then run `tsl login`: open `https://github.com/login/device`, type the code, and authorize. The first time, it answers "No Truminds role yet". After D.2, run `tsl login` again; this registers your signing key.
4. Run `tsl whoami`, then `tsl doctor`. The login check should say `provider github`, and the service check should point at `https://<name>.onrender.com`.
5. Install the plugin in Claude Code (the dev path, TST-02 VAL-EXE-02):
   ```powershell
   claude plugin marketplace add C:\dev\AI-Skill-Library
   claude plugin install truminds@truminds-skill-library
   ```
6. In the Claude Code desktop app, open a **local** session in the folder `C:\dev\AI-Skill-Library\examples\sample-system\companion-example`, the folder that holds `tsl.yaml`.
7. Start a run: `/truminds:run brownfield-change ABC-142`. Skills run only inside a run (TST-02 §3, T5–T6).

## F. GitHub webhook (PR events)

Do this per repository that `tsl pr` opens PRs in (or once on the test org).

1. In the repository (or org): **Settings** → **Webhooks** → **Add webhook**.

| Field | Value |
| --- | --- |
| Payload URL | `https://<name>.onrender.com/v1/webhooks/github` |
| Content type | `application/json` |
| Secret | The `GITHUB_WEBHOOK_SECRET` value from C.6 |
| SSL verification | Enable |
| Which events | **Let me select individual events**: Pull requests, Pull request reviews, Pull request review comments, Check runs, Releases |

2. Click **Add webhook**. Open it again and copy the **hook ID**, the number at the end of the page URL (`…/settings/hooks/<ID>`).
3. In Render → service → **Environment**, add `GITHUB_WEBHOOK_HOOKS` = `<ID>:<owner>/<repo>`. For several hooks, separate them with commas: `123:example-org/companion,456:example-org`. Click **Save, rebuild and deploy**. At start the service registers each hook with the secret, encrypted. The logs show `github webhooks registered`.

   Render's free plan has no shell, so this replaces `python -m app.entry admin hook create`. `GITHUB_WEBHOOK_HOOKS` is set in the dashboard only, not in `render.yaml`. Blueprint syncs manage only the keys listed in `render.yaml`.
4. Back on GitHub → the webhook → **Recent Deliveries**. Redeliver the first `ping`, which failed with 401 before step 3. It now shows **204**.
5. In the portal **Admin**, the repository must belong to a system. Events for unknown repositories are dropped.

## G. Free-tier behaviour and troubleshooting

- **Render free sleeps** after 15 minutes without incoming requests. The next request wakes it in **30–60 s**: the container starts, migrations are checked, and the catalogue syncs. Background jobs run only while it is awake.
- **Neon free scales to zero** after 5 minutes without queries. Waking takes about a second, and the service retries the database for up to 2 minutes at start.
- Nothing is stored on Render's disk. All state is in Neon, so a redeploy or restart loses nothing.
- One free instance, 512 MB RAM. The container uses about 80 MB at rest.
- Before a test session, open the portal once to wake everything; `tsl` commands then answer at normal speed.

| Symptom | Cause | Fix |
| --- | --- | --- |
| First page load takes up to a minute | Render free woke from sleep | Wait; then it is fast for the session |
| `tsl login` or `tsl doctor` times out | The service was asleep | Open the portal URL, wait for it, retry |
| Deploy fails, log says `DATABASE_URL is Neon's pooled endpoint (-pooler)` | Pooled connection string | In Neon, Connect with pooling **off**; replace `DATABASE_URL` |
| Log says `DATABASE_URL must use TLS` | `?sslmode=require` missing | Copy the full string from Neon again |
| Log repeats `database not reachable yet` with `password authentication failed` | Wrong or reset Neon password | Neon → Roles → reset `neondb_owner` password; paste the new string into `DATABASE_URL` |
| Log says `DATABASE_URL needs DB_ROLE_PASSWORD_KEY` | The generated key was deleted | Add `DB_ROLE_PASSWORD_KEY` back (any random 44+ characters); the next start sets the role passwords to match |
| GitHub sign-in says "redirect_uri is not associated with this application" | OAuth App callback differs from `PUBLIC_BASE_URL` | Make both exactly `https://<name>.onrender.com` (+ `/auth/github/callback`) |
| `tsl login` says device flow is disabled | Device Flow not ticked | OAuth App → tick **Enable Device Flow** → Update |
| `tsl doctor` says provider `entra` or service `insights.example.invalid` | `tsl` installed without the org file, or from a cached build | Repeat E.2 exactly, including `--reinstall --no-cache` |
| Portal says "No Truminds role yet" | Roles not granted | D.2 |
| Webhook deliveries show 401 | Hook not registered, or the secret differs | F.3; the secret in GitHub and `GITHUB_WEBHOOK_SECRET` must be identical |
| Webhook deliveries show 202/204 but nothing in the portal | Repository not in any system | F.5 |
| `/readyz` shows `fail` | Database down, migrations behind, or a missing key | Render → Logs: the line `readyz failed` names the failing check |

## H. Security notes

- **This is on the public internet.** Use only invented data and the sample system: no client names, client code or customer data. **Never** point a client repository, its webhooks or its CI at this environment.
- Secrets live only in Render's environment variables. Never put them in git, issues, chat or screenshots. `render.yaml` holds no secret: it only names the keys.
- The service refuses these variable-style secrets (`DATABASE_URL`, `DATA_KEY`, `PSEUDONYM_PEPPER`, `DB_ROLE_PASSWORD_KEY`) when `ENV=prod`, and refuses `IDENTITY_PROVIDER=github` in production. Production keeps Entra and file-based secrets ([ADR 0006](../../docs/adr/0006-interim-github-sign-in-for-test-phase.md)).
- Traffic is HTTPS end to end: Render terminates TLS, and the service sends HSTS. The connection to Neon is TLS (`sslmode=require`). Neon encrypts data at rest.
- The API connects as the least-privilege roles, never as the owner. The owner credentials are used only for migrations and start-up tasks.
- `/metrics` is not served on the public port. `/readyz` answers only ok or fail; the detail stays in the logs.
- **When the test phase ends** (or if anything leaks):
  1. Delete the Render service.
  2. Delete the Neon project.
  3. Delete the OAuth App's client secret, then the app.
  4. Delete the webhooks.
  5. Remove Render's access to the repository (GitHub → Settings → Applications).

  To rotate instead of delete: generate a new OAuth client secret, reset the Neon password, and replace `GITHUB_WEBHOOK_SECRET` in both GitHub and Render. Only rotate `DATA_KEY` with a fresh database.

### Admin commands without a shell

Render's free plan has no shell. Start-up already does what the one-machine set-up does with `admin`: migrations, catalogue sync and webhook registration. Ingest tokens for CI (`tsl ci-verify`) and OTel are not created at start yet. They come with the end-to-end GitHub test (handover §6).
