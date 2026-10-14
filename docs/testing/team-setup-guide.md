# Team setup guide: set up your laptop and validate the Skill Library

| Field | Value |
| --- | --- |
| Status | Active |
| Owner | Puneet Singh Nanda |
| Approver | Puneet Singh Nanda |
| Audience | The six testers: Abhishek Verma, Ekjot Singh, Japman Singh, Yash Khorwal, Shubham Bansal, Gaurav Saini |
| Related | [TST-02 Team Validation Plan](TST-02-team-validation-plan.md) (the test scripts), [ADR 0006](../adr/0006-interim-github-sign-in-for-test-phase.md) (GitHub sign-in) |

This guide covers what each tester does on their own laptop. Commands are for **Windows PowerShell**. The test scripts themselves are in [TST-02 §5](TST-02-team-validation-plan.md#5-responsibilities-and-test-scripts-per-area).

**You do not set up any server or database.** Puneet runs the shared test environment. You get two things from him:

- the portal URL: `https://truminds-skills-test.onrender.com`
- the **GitHub OAuth Client ID** (not a secret)

## 1. The big picture

```text
 YOUR LAPTOP                                          SHARED (run by Puneet)
 ┌─────────────────────────────────────────┐         ┌──────────────────────────────┐
 │ Claude Code desktop app + truminds plugin│         │ Portal + insights service    │
 │ tsl  (gates, decide, signing, PRs)       │ ──────► │ https://truminds-skills-test │
 │ repo clone: code, tests, sample system   │  HTTPS  │        .onrender.com          │
 │ (optional) Docker: dev container, H3     │         │ sign-in with GitHub          │
 └─────────────────────────────────────────┘         └──────────────────────────────┘
```

Everything you test runs on your laptop. The shared service only signs you in, registers your signing key, and collects telemetry for the portal.

## 2. Do you need Docker?

**Not to start.** Install it only if your tests need it:

| You want to | Docker? |
| --- | --- |
| Install `tsl`, sign in, install the plugin, use the portal | **No** |
| Run skills and workflow steps that don't change code (requirement review, story split, impact analysis, design, threat model, estimate, test plan) | **No** |
| Run `tsl` tests, plugin tests, `tsl validate`, `tsl harness eval` | **No** (only uv) |
| Run portal tests | **No** (only Node.js) |
| Run **every** suite with one command (`make test-all`), including the insights service and sample-system tests that need PostgreSQL 16 | **Yes**, through the dev container (§4B) |
| Code steps of a workflow (`implement`, `unit-test`, `test-automation`): gate H3 runs lint and tests in a verifier container | **Yes**, and it is blocked for everyone today (see §9) |
| VAL-HAR-05 (verifier containers) | **Yes** |

By area:

| Area | Docker? |
| --- | --- |
| Abhishek, Ekjot (skills, workflows, roles) | Optional |
| Shubham (skill and hook execution, spikes) | Optional |
| Japman, Yash (harness) | **Yes**, for VAL-HAR-05 and H3 |
| Gaurav (telemetry, portal) | **Yes**, for the insights service tests (dev container) |

## 3. Install the basics (everyone, once)

| Tool | Install | Check |
| --- | --- | --- |
| Git 2.40+ | https://git-scm.com/download/win | `git --version` |
| uv | `powershell -c "irm https://astral.sh/uv/install.ps1 \| iex"` | `uv --version` |
| Node.js 22 LTS (portal and sample-system tests only) | https://nodejs.org | `node -v` |
| Claude Code desktop app | Company Claude seat; use a **local** session (not cloud, not Cowork) | The app opens and you are signed in |
| Docker Desktop (only if §2 says you need it) | https://www.docker.com/products/docker-desktop | Docker Desktop shows **Engine running** |

Clone the repo **outside OneDrive**:

```powershell
git clone https://github.com/puneetsinghnanda/AI-Skill-Library.git C:\dev\AI-Skill-Library
cd C:\dev\AI-Skill-Library
```

## 4. Run the test suites (phase A)

### 4A. Without Docker: run them directly

From `C:\dev\AI-Skill-Library`:

```powershell
cd tsl;                    uv run --python 3.12 pytest -q;  cd ..   # tsl, about 260 tests
cd schemas;                uv run --python 3.12 pytest -q;  cd ..   # schema fixtures
cd plugins\truminds\tests; uv run --python 3.12 pytest -q;  cd ..\..\..   # plugin, hooks
cd portal; npm ci; npm test; cd ..                                   # portal (Node), about 300 tests
```

The insights service and sample-system tests need PostgreSQL 16 binaries, so run those in the dev container (4B).

### 4B. With Docker: the dev container runs everything

1. Start **Docker Desktop** and wait until it shows **Engine running**.
2. In PowerShell, from the repo folder:
   ```powershell
   npx -y @devcontainers/cli up   --workspace-folder .        # first time 10–20 min; ends with "outcome":"success"
   npx -y @devcontainers/cli exec --workspace-folder . make test-all
   ```
   For a shell inside the container, use `npx -y @devcontainers/cli exec --workspace-folder . bash`.
3. Don't use VS Code's **Reopen in Container** button on Windows; use the commands above. Afterwards, VS Code can **Attach to Running Container**.

Every suite should pass. A failure is a finding (§8).

## 5. Install `tsl` connected to the test environment (everyone, once)

1. Create your settings file:
   ```powershell
   cd C:\dev\AI-Skill-Library
   Copy-Item deploy\render\tsl-org.github.toml.example deploy\render\tsl-org.github.toml
   notepad deploy\render\tsl-org.github.toml
   ```
   Change these two lines and save. The file is git-ignored, so it is never committed:
   ```toml
   github_client_id = "<Client ID from Puneet>"
   service_url = "https://truminds-skills-test.onrender.com"
   ```
2. Install:
   ```powershell
   $env:TSL_ORG_FILE = "$PWD\deploy\render\tsl-org.github.toml"
   uv tool install --python 3.12 --reinstall --no-cache .\tsl
   Remove-Item Env:TSL_ORG_FILE
   tsl --version          # tsl 0.1.0
   ```
   - Keep `--reinstall --no-cache`; without them, uv can reuse an old build that has no settings file.
   - Don't use `--editable`.
   - If `tsl` is "not recognized", run `uv tool update-shell` and reopen PowerShell.

## 6. Sign in (everyone, once)

1. Open `https://truminds-skills-test.onrender.com` in your browser. The first load can take up to a minute while the free service wakes up.
2. Click **Sign in with GitHub**, then **Authorize**. You see **"No Truminds role yet"** and a pseudonym like `eng-1a2b`. That's expected.
3. In PowerShell, run `tsl login`. Open `https://github.com/login/device`, type the code it shows, and click **Authorize**. It also says "No Truminds role yet".
4. **Post in the team channel that you've signed in.** Puneet (or the admin tester) gives you all roles in **Admin → Users**.
5. Once you have roles, run `tsl login` again. This registers your signing key.
6. Check:
   ```powershell
   tsl whoami      # your pseudonym and roles
   tsl doctor      # login: provider github; service: https://truminds-skills-test.onrender.com
   ```
   - In `doctor`, `docker` shows **warn** if Docker isn't running. That's fine unless §2 says you need Docker.
   - Paste the `doctor` output into your verdict notes.
7. Refresh the portal. It shows the **TEST ENVIRONMENT** banner and your role.

## 7. Install the plugin and run a workflow (phases B and C)

**Install the plugin** (once):

```powershell
claude plugin marketplace add C:\dev\AI-Skill-Library
claude plugin install truminds@truminds-skill-library
```

Restart the Claude Code app. Typing `/truminds:` should list `run`, `status` and `resume`.

**Point the sample companion repo at the sample system** (once; the file is git-ignored):

```powershell
cd C:\dev\AI-Skill-Library\examples\sample-system\companion-example
New-Item -ItemType Directory -Force .tsl | Out-Null
Set-Content .tsl\local.yaml "schema: tsl-local.v1`nproduct_repos:`n  sample-system: .."
```

**Run a workflow:**

1. In Claude Code, open a **local** session in `C:\dev\AI-Skill-Library\examples\sample-system\companion-example`, the folder with `tsl.yaml`. Not the repo root.
2. Type `/truminds:run brownfield-change ABC-142`.
   - Skills run **only inside a run**. A skill that "refuses" outside one is correct behaviour.
   - Use a different ticket from your teammates (`ABC-142` to `ABC-180`, in `examples\sample-system\tickets\`) so you don't block each other with locks.
3. Follow the run:
   - **Questions:** answer in `open-questions.md`, then type `/truminds:resume <run_id>`.
   - **Approval gate:** the approver runs `tsl approve`, then type `/truminds:resume <run_id>`.
   - **Progress:** type `/truminds:status`.
4. Check the portal: your run and its steps appear in the Engineer view.

**What to expect today:** the brownfield run goes through requirement review, story split, impact analysis, design and threat model. It **stops at `implement`** with **E-H3-07** because the verifier images don't exist yet (§9). That stop is a known blocker, not a finding. Workflows without code steps (`estimate`, `security-review`, `ux-review`, `pipeline-check`) can run end to end.

## 8. Validate and report

- **What to test:** your area's table in TST-02 §5 (VAL-SKL, VAL-HAR, VAL-EXE, VAL-TEL), in phase order A → B → C.
- **One finding = one GitHub issue**, using the **Validation finding** template. Severity is S1 Blocker, S2 Major, S3 Minor or S4 Idea. Include:
  - the test ID
  - the exact command
  - the error code
  - what you expected (cite the doc)
  - what happened
- **Blocked?** Open an issue with the label `validation:blocked` straight away.
- **Verdict:** each area submits `docs/testing/validation/<area>-verdict.md` by pull request (TST-02 §8).
- **Rules:**
  - Sample system and invented data only.
  - No client names, client code, customer data, tokens or keys in issues or screenshots.
  - Never point anything at Jira, Confluence or a client system.

| Area | Who | Tests |
| --- | --- | --- |
| Skills, workflows, roles | Abhishek Verma, Ekjot Singh | TST-02 §5.1 |
| Harness, execution, `tsl verify` | Japman Singh, Yash Khorwal | TST-02 §5.2 |
| Skill and hook execution, spikes | Shubham Bansal | TST-02 §5.3 |
| Telemetry, portal statistics | Gaurav Saini | TST-02 §5.4 |

## 9. Troubleshooting

| Symptom | Fix |
| --- | --- |
| Portal or `tsl` hangs up to a minute, then works | The shared service was asleep. Open the portal first, then retry |
| `tsl doctor` shows provider `entra` or service `insights.example.invalid` | `tsl` was installed without the settings file. Repeat §5 exactly |
| `tsl login` says device flow is disabled, or GitHub says "redirect_uri is not associated" | Tell Puneet (OAuth App setting) |
| Still "No Truminds role yet" | Ask for roles (§6.4), then run `tsl login` again |
| `/truminds:` commands missing | Repeat the plugin install (§7) and restart the Claude Code app |
| A skill refuses to run | Start a run first: `/truminds:run <workflow> <ticket>` |
| Claude can't find `tsl.yaml` | Wrong folder: open the session in `examples\sample-system\companion-example` |
| `E-LOCK` when starting a run | Someone holds that ticket; pick another |
| `E-H3-07` at `implement` or `unit-test` | Known blocker: verifier images not published yet (see Open items) |
| `devcontainers/cli` can't reach Docker | Start Docker Desktop and wait for **Engine running**; reopen VS Code if it was already open |
| `git commit` from Windows says `pre-commit not found` | Commit with `git commit --no-verify`, or commit inside the dev container |
| `git status` shows `.devcontainer/devcontainer-lock.json` | It's ignored on `main`; run `git pull` |

Still stuck? Open a `validation:blocked` issue with the command, the output (secrets removed) and your `tsl doctor` result.

## Done criteria

- Every tester has completed §3, §5, §6 and §7. `tsl doctor` shows `provider github` and the shared service, and the portal shows their roles.
- Every tester has run their phase A suites (§4) and started at least one run from `companion-example`.

## Open items

- **Verifier images (blocks code steps; decision for Puneet).** The H3 profiles in `plugins/truminds/verifiers/*/profile.yaml` reference `ghcr.io/<org>/…@sha256:000…0` placeholders, which `tsl` refuses with E-H3-07. Unblocking needs:
  1. A registry decision (OQ-10).
  2. A run of `.github/workflows/verifier-images.yml`.
  3. A reviewed PR with the real digests.

  Until then, `implement`, `unit-test` and `test-automation` stop at H3.
- CI and OTel ingest tokens are not yet created in the shared environment. They come with the end-to-end GitHub test.
- The test GitHub org and repos for real PRs (`tsl pr`, lead approval, `tsl ci-verify`): TBD by Puneet.
