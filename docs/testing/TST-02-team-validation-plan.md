# TST-02 · Team Validation Plan: test the Skill Library and give a verdict

| Field | Value |
| --- | --- |
| Status | Active |
| Owner | Puneet Singh Nanda |
| Approver | Puneet Singh Nanda |
| Testers | Abhishek Verma, Ekjot Singh, Japman Singh, Yash Khorwal, Shubham Bansal, Gaurav Saini |
| Related | [TST-01](TST-01-master-test-plan.md), [traceability](../planning/traceability.md), [registry](../architecture/registry.md), [spikes](../../spikes/README.md), [Release 1 gate](../planning/release-1-gate-checklist.md) |

## 1. Purpose

Each of you owns one area of the library. Your job now is to **use it, try to break it, and give an honest verdict**: does it work as the documents say, is it usable by a Truminds engineer, and what must change before Release 1.

You are not expected to write new features. You are expected to:

1. run every test in your area (section 5) and record the result;
2. explore beyond the script: anything that looks wrong, confusing or slow is a finding;
3. raise each finding as a GitHub issue using the **Validation finding** template;
4. submit a verdict file for your area (section 8) by pull request.

```mermaid
flowchart LR
  A[Set up laptop<br/>§3] --> B[Phase A<br/>laptop only]
  B --> C[Phase B<br/>Claude seat, no login]
  C --> D[Phase C<br/>seat + Entra + test service]
  B & C & D --> E[Issues<br/>Validation finding]
  E --> F[Verdict file per area<br/>§8]
  F --> G[Puneet review<br/>Go / Go with fixes / No-go]
```

## 2. The three phases and what each needs

| Phase | What you can test | Needs | Status |
| --- | --- | --- | --- |
| **A. Laptop only** | All code, tests, schemas, `tsl validate/verify/decide` on sample files, skills content, insights service and portal locally, sample system | Laptop set up as in §3 | Can start now |
| **B. Claude seat, no login** | Plugin install in Claude Code, hooks, spikes S-01 to S-15 (S-09 runs the whole run loop with a stub `tsl`), skills tried by hand | A company Claude seat with the Claude Code desktop app (local session, not cloud, not Cowork) | Can start now |
| **C. Full run** | `/truminds:run brownfield-change ABC-142` end to end, signed records, telemetry reaching the portal | **Entra ID test app registration** (for `tsl login`), a **test insights instance** (Gaurav can run one with `deploy/` on a shared VM), a test GitHub org or repo for companion repos | Blocked until Puneet arranges the three items (§10) |

Why phase C is blocked: `tsl` signs every record with a key registered at `tsl login`, and login goes only through Microsoft Entra ID. There is deliberately no bypass or debug login (org rule). So a real run needs the Entra test app.

## 3. Laptop set-up (everyone, once)

Windows is the main target (Claude Code runs natively on Windows, not in WSL: C-17).

| Step | Command or action | Check |
| --- | --- | --- |
| 1 | Install **Git**, **Docker Desktop**, **Node.js 22 LTS** (and Node 20 if you test the portal CI matrix) | `git --version`, `docker version`, `node -v` |
| 2 | Install **uv**: `powershell -c "irm https://astral.sh/uv/install.ps1 \| iex"` | `uv --version` |
| 3 | Clone outside OneDrive: `git clone https://github.com/puneetsinghnanda/AI-Skill-Library.git C:\dev\AI-Skill-Library` | Repo opens |
| 4 | Start the dev container from PowerShell (proven on a Windows laptop; more reliable than the VS Code "Reopen in Container" button): `npx -y @devcontainers/cli up --workspace-folder .` (first build 10–20 min, ends with `"outcome":"success"`), then `npx -y @devcontainers/cli exec --workspace-folder . make test-all`. For a shell inside it: `... exec --workspace-folder . bash`. VS Code can then use **Dev Containers: Attach to Running Container**. Docker Desktop must show "Engine running" first | Every suite passes |
| 5 | Install `tsl` natively (for Windows and Claude Code tests): `uv tool install --python 3.12 C:\dev\AI-Skill-Library\tsl` | `tsl --version` prints `0.1.0` |
| 6 | Until the plugin is installed in Claude Code (phase B), tell `tsl` where the plugin is. PowerShell: `$env:CLAUDE_PLUGIN_ROOT="C:\dev\AI-Skill-Library\plugins\truminds"` (bash: `export CLAUDE_PLUGIN_ROOT=$PWD/plugins/truminds`). Without it, commands such as `tsl harness eval` stop with E-ENV-01 "truminds plugin" | `tsl validate plugins/truminds` prints `35 item(s) valid` |
| 7 | Run `tsl doctor`. In phases A and B the login, key and service checks are expected to fail; everything else should pass | Record the output in your verdict |

Rules while testing (they apply to every issue and file you write):

- Use only the sample system (`examples/sample-system/`) and invented data. **No client names, client code, customer data, tokens or keys** anywhere: issues, screenshots, logs.
- Never point any tool at Jira, Confluence or a client system. If a step seems to need it, stop and raise a finding.
- If a rule blocks you, report the conflict; do not work around it.

## 4. How to report a finding

Open a GitHub issue with the **Validation finding** template (`.github/ISSUE_TEMPLATE/validation-finding.yml`). One finding per issue.

| Severity | Meaning |
| --- | --- |
| **S1 Blocker** | Wrong decision, data leak, security gap, or the area cannot be used at all |
| **S2 Major** | Works but gives a wrong or misleading result in a common case, or a doc says something the code does not do |
| **S3 Minor** | Usability, wording, slow but within budget, missing example |
| **S4 Idea** | Improvement, not a defect |

Always include: test ID (e.g. `VAL-HAR-07`), component, exact command, error code from the output, what you expected (cite the doc section), and what happened.

## 5. Responsibilities and test scripts per area

Each test has an ID, steps and the expected result. **Pass** = matches the expected result. **Fail** = raise a finding. **Blocked** = say what blocked you.

---

### 5.1 Skills, workflows, roles: Abhishek Verma and Ekjot Singh

**Your question to answer:** *Are the skills, workflows, pods and role packs good enough that a Truminds engineer would trust the output, and can a new skill be authored from the guide alone?*

Read first: [SDD-01](../design/SDD-01-skill-authoring.md), [SDD-02](../design/SDD-02-workflow-orchestration.md), [SDD-10](../design/SDD-10-pods.md), `plugins/truminds/README.md`.

**Split of the 17 SDLC skills**

| Abhishek Verma | Ekjot Singh |
| --- | --- |
| requirement-review, story-split, estimate-review, impact-analysis, design, implement, unit-test, status-report | test-plan, test-automation, threat-model, secure-code-review, defect-triage, pipeline-review, deployment-failure-analysis, ux-flow-review, accessibility-review |
| Role packs: business-analyst, solution-architect, developer, delivery-manager | Role packs: qa-engineer, security, devops, ux-designer |
| Workflows: brownfield-change, greenfield-feature, estimate, defect-fix | Workflows: security-review, quality-uplift, pipeline-check, deploy-failure, ux-review |
| Pods: brownfield-change-pod, greenfield-feature-pod | Pods: quality-security-pod, ux-review-pod |

| ID | Phase | Test | Steps | Expected |
| --- | --- | --- | --- | --- |
| VAL-SKL-01 | A | Whole plugin validates | `tsl validate plugins/truminds` and `make test-plugin` | `ok: true`, 35 items valid; plugin tests pass |
| VAL-SKL-02 | A | Skill content review (each of your skills) | Read `SKILL.md`, `skill.yaml`, `rubric.md`, `checks.yaml`. Score each 1–5 on: clear instructions, correct inputs/outputs, rubric matches what a senior engineer would check, checks catch real problems | A filled table in your verdict, one row per skill, with the weakest point of each |
| VAL-SKL-03 | A | Eval quality (each of your skills) | Read all 10 cases in `evals/cases/`. Are they realistic? Do they cover happy path, missing input, ambiguous input, injection and edge cases (SDD-01 §10.3)? Is the expected outcome right? | Every skill has ≥ 10 sensible cases; list wrong or weak cases |
| VAL-SKL-04 | A | Validation catches bad skills | Copy a skill to a temp folder and break it one way at a time: remove `rubric.md`; change `version` to `1.0`; drop `disable-model-invocation` from a command skill; put `FAKE-KEY-0000-TEST` in `SKILL.md`; delete 5 eval cases. Run `tsl validate <folder>` each time | Each break gives a specific `SKL-Vnn` error naming the problem |
| VAL-SKL-05 | A | Author a new skill from the guide only | Follow SDD-01 to write a new skill, e.g. `api-contract-review`, with 10 evals, without copying another skill folder | `tsl validate` passes. Report every place the guide was unclear or missing a step. This is the most important usability test |
| VAL-SKL-06 | A | Workflow wiring | For each of your workflows check step order, inputs mapping from earlier artifacts, human gates and retry limits against SDD-02. Break one: point a step at a skill that does not exist; run `tsl validate` | Breaks are caught; order and gates make sense for real delivery |
| VAL-SKL-07 | A | Brownfield flow matches the UX | Compare `brownfield-change.workflow.yaml` with the Run detail screen (`docs/ux/prototype/RunDetail.dc.html`) | Same steps and gates, same order |
| VAL-SKL-08 | A | Pods and role packs reflect how Truminds works | Review pods and role packs: are the agents, skills per agent and people accountable right for a real engagement? Any role missing (e.g. Business Analyst agent: SDD-10 open item)? | Recommendations in your verdict |
| VAL-SKL-09 | A | Status consistency | Check `status:` in every `skill.yaml`. SDD-01 says new skills start as `draft`, but most say `production` while `requirement-review` says `draft` | Recommend one rule; raise a finding |
| VAL-SKL-10 | A | Eval plan | `tsl eval plan requirement-review` (and two of your skills) | Plan lists the cases and what is needed to run them |
| VAL-SKL-11 | B | Try skills by hand on a seat | In a local Claude Code session in the sample repo, ask Claude to follow `plugins/truminds/skills/requirement-review/SKILL.md` on `examples/sample-system/tickets/ABC-142.md`. Repeat for 2 of your skills with the matching ticket | Output follows the skill's template and rubric. Judge: would you accept it from a junior? Note hallucinated facts and missing citations |
| VAL-SKL-12 | B | Does it find the planted defects? | Run `impact-analysis`, `secure-code-review` and `defect-triage` by hand against the sample system. Then compare with `examples/sample-system/.answers/SEEDED_DEFECTS.md` **only after** the run | Count found / missed / false alarms per skill |
| VAL-SKL-13 | C | Real evals | `tsl eval run <skill>` for each of your skills | Pass rate per skill; ≥ 90 % is the proposed bar (Q26) |
| VAL-SKL-14 | C | Full brownfield run | `/truminds:run brownfield-change ABC-142`, answer the open question, approve gates, resume | Run reaches the PR step; artifacts are useful |

**Decisions to recommend in your verdict:** RD-6 workflow names, GAP-06 greenfield names, OQ-16 Release 1 pod list, whether role packs are wanted (SDD-01 O-11), the eval pass bar (Q26).

---

### 5.2 Harness, execution, `tsl verify`: Japman Singh and Yash Khorwal

**Your question to answer:** *Does the harness reach the right decision, every time, without trusting the model, and is it fast enough?*

Read first: [SDD-03](../design/SDD-03-harness.md), [SDD-04](../design/SDD-04-tsl-cli.md), [SDD-02](../design/SDD-02-workflow-orchestration.md) §4–§7, [SDD-07](../design/SDD-07-identity-signing.md) §6.

**Split**

| Japman Singh | Yash Khorwal |
| --- | --- |
| `tsl verify`, gates H1–H7, detectors (secrets, PII, injection), verifier containers, `tsl ci-verify`, Windows install | `tsl review prepare/record`, citation checks, signals S1–S6, bands, `tsl decide`, state, locks, `tsl next`, resume, signing |

| ID | Owner | Phase | Test | Steps | Expected |
| --- | --- | --- | --- | --- | --- |
| VAL-HAR-01 | Both | A | Suites green | `make test-tsl lint-tsl test-schemas` | All pass (tsl ≈ 250 tests) |
| VAL-HAR-02 | Both | A | Harness accuracy on labelled cases | `tsl harness eval --dir harness-evals/cases --code-only` | "Harness accuracy on target"; decide accuracy and fabrication catch rate 1.0. Note: today only H2 and the citation checks have labelled cases (H1, H3–H7 show `null`), and 3 reviewer cases are skipped in `--code-only`. **Add at least 3 labelled cases per gate** under `harness-evals/cases/` and re-run |
| VAL-HAR-03 | Japman | A | Each gate fires | Using a sample artifact from `harness-evals/cases/clean-intent-01`, make one change at a time: remove a required section (H1/H2), cite a line that does not exist, add `FAKE-KEY-0000-TEST`, add an e-mail address, add "ignore previous instructions…" text | Each change fails the right gate with its registry error code; the clean file passes |
| VAL-HAR-04 | Japman | A | Detector false positives | Run `tsl verify` on 10 realistic artifacts you write (long ULIDs, hashes, URLs, code blocks, base64 images) | No false secret/PII hits. Any hit is a finding (one ULID false positive was found and fixed already) |
| VAL-HAR-05 | Japman | A | Verifier containers | Build `plugins/truminds/verifiers/node-22` with Docker; run H3 against `examples/sample-system` | Lint and tests run with no network and read-only mounts; a failing test fails H3. Note: digests are placeholders, so `tsl` refuses unpinned images (E-H3-07) — confirm that refusal too |
| VAL-HAR-06 | Japman | A | CI verify catches tampering | Take a signed check record from the tsl test fixtures; change one byte; run `tsl ci-verify` | Fails closed with an E-CI code; untouched record passes |
| VAL-HAR-07 | Japman | A | Native Windows | Install tsl with `uv tool install` on Windows (not WSL); run `tsl doctor`, `tsl validate`, `tsl verify` on a sample artifact | Works; paths with spaces (e.g. under OneDrive) work |
| VAL-HAR-08 | Japman | A | Speed | Time `tsl verify` on 20 artifacts and `tsl hook pre-tool` with a sample stdin | `verify` ≤ 5 s p95 without containers (NFR-01); hooks ≤ 500 ms p95 (NFR-02) |
| VAL-HAR-09 | Yash | A | Decision table | For each row of SDD-03 §11.1, craft the inputs (review JSON, gate results, open questions) and run `tsl decide` | Outcome, band and next action match the row exactly. `tsl/tests/test_decide_table.py` shows how |
| VAL-HAR-10 | Yash | A | Reviewer cannot lie | Give `tsl review record` a review with a fabricated citation, a citation to a real file but wrong line, and invalid JSON | Fabricated findings are dropped (counted in S1/record), invalid JSON gives E-REV-02 |
| VAL-HAR-11 | Yash | A | Thresholds | Change band thresholds per skill (SDD-03 §9); re-run decide | Band moves as documented; out-of-range config rejected |
| VAL-HAR-12 | Yash | A | Locks and crash recovery | In a scratch companion repo (`tsl init` or copy `examples/sample-system/companion-example`), start the same ticket from two terminals; kill one mid-step; run `tsl state show` and resume | Second start refused with E-LOCK; crashed run is recoverable, no lost artifacts |
| VAL-HAR-13 | Yash | A | Signing | `make test-tsl` signing tests; then edit an `approvals.md` signature by hand and run `tsl ci-verify` | Tampering detected |
| VAL-HAR-14 | Both | C | Real run decisions | During the phase C brownfield run, open every check record | Each decision can be explained from the record alone, with no model judgement taken on trust |

**Decisions to recommend in your verdict:** harness thresholds and default limits (OQ-09, OQ-12), the High-band audit rate (OQ-11 / Q27), GAP-08 (should a blocker from secure-code review ESCALATE or go to NEEDS-INPUT?), container user id (SDD-03 says 1000, SEC-01 says 10001).

---

### 5.3 Skill execution and hook execution: Shubham Bansal

**Your question to answer:** *Does Claude Code actually behave the way SDD-05 assumes, and do the hooks enforce the rules on Windows and macOS?*

Read first: [SDD-05](../design/SDD-05-claude-code-integration.md), [spikes/README.md](../../spikes/README.md), [OPS-04](../operations/OPS-04-failure-runbook.md).

**Most important:** spikes S-01 to S-15 are the highest technical risk in the project (tracker Q37). Every design decision in SDD-05 §2.1 marked "unverified" waits on them.

| ID | Phase | Test | Steps | Expected |
| --- | --- | --- | --- | --- |
| VAL-EXE-01 | B | Spikes S-01 to S-15 | Follow each runbook in `spikes/README.md` on a company seat, local session. Fill each spike's results table | Each spike marked Confirmed / Different (say how) / Blocked. Update SDD-05 §2.1 U-01..U-06 by PR |
| VAL-EXE-02 | B | Plugin install (dev path) | `claude plugin marketplace add C:\dev\AI-Skill-Library` then `claude plugin install truminds@truminds-skill-library` | `/truminds:run`, `/truminds:status` etc. appear; SDLC skills do not auto-run |
| VAL-EXE-03 | B | Commands never start on their own | In a session, describe a ticket and ask for help without typing a command | Claude never starts a run (`disable-model-invocation: true`) |
| VAL-EXE-04 | B | Hook launcher, all failure paths | With `tsl` (a) missing, (b) wrong version, (c) crashing, (d) hanging: trigger a Write inside and outside an active run | Inside a run: denied with E-HOOK-01 (fail closed). Outside: allowed with a warning (fail open). Test `bin/tsl-hook.cmd` on Windows and `bin/tsl-hook` on macOS |
| VAL-EXE-05 | B | Write scope | During a run (S-09 stub or phase C), ask Claude to edit a file outside `artifacts/`, `runs/` and the product repos, and to edit `.github/workflows/` | Denied with E-POL-01/02 |
| VAL-EXE-06 | B | MCP writes need approval | With any MCP server connected **to a test space only**, ask Claude to create an item during a run | Denied with E-POL-03 unless `approvals.md` has a signed approval. Never use a real Jira/Confluence project |
| VAL-EXE-07 | B | Post-write verify | During a run, let Claude write an artifact with a missing section | Hook blocks with E-CHK-01 and Claude fixes it |
| VAL-EXE-08 | B | Managed settings | Apply `managed-settings/managed-settings.template.json` on a test machine via the file path (testing only), with placeholders filled with test values | Deny rules block `.env`, `curl`, force push; only the Truminds marketplace allowed (S-01, S-02, S-13) |
| VAL-EXE-09 | B | Session id handoff | Check `TSL_SESSION_ID` reaches `tsl` calls (S-08) | Present, or the documented fallback works |
| VAL-EXE-10 | B | Seat usage | Measure one stubbed full run and, in phase C, one real run (S-11) | Numbers recorded for Q38 |
| VAL-EXE-11 | C | Real run | `/truminds:run brownfield-change ABC-142` → answer `open-questions.md` → `/truminds:resume` → approve gates → `tsl pr` | Pause/resume works; `tsl pr` opens a PR in the **test** org and never merges |
| VAL-EXE-12 | A | Hook contracts | `make test-plugin`; read `tsl/tests` hook golden files | Golden files match what you observe in S-04/S-15 |

**Decisions to recommend in your verdict:** which managed-settings delivery to use (admin console vs MDM), anything in SDD-05 that the spikes disproved, whether C-16..C-18 hold.

---

### 5.4 Telemetry, logs, events and portal statistics: Gaurav Saini

**Your question to answer:** *Do the right events arrive, are the numbers on the portal correct and safe to show to each persona, and is nothing sensitive leaving the laptop?*

Read first: [SDD-08](../design/SDD-08-telemetry-insights.md), [SDD-09](../design/SDD-09-web-portal.md), [OPS-02](../operations/OPS-02-monitoring-alerting.md), `services/insights/README.md`, `portal/README.md`.

| ID | Phase | Test | Steps | Expected |
| --- | --- | --- | --- | --- |
| VAL-TEL-01 | A | Suites green | `make test-insights lint-insights test-portal lint-portal test-portal-e2e test-deploy-ops` | All pass |
| VAL-TEL-02 | A | Run the service locally | Follow `services/insights/README.md` "Run locally" (PostgreSQL 16 via `compose.dev.yml`), run migrations, then `uv run python seed/generate.py --catalogue ../..` | API healthy (`/healthz`, `/readyz`), seed data loaded |
| VAL-TEL-03 | A | Portal demo | `cd portal && npm ci && npm run demo` → http://localhost:4173. Switch persona; walk all 15 screens and the admin screens | Matches the prototype; Business view shows **no** run ids, ticket ids or names |
| VAL-TEL-04 | A | Event contract | Use tsl's outbox: create events in a scratch companion repo, then `tsl events flush` to the local service (point config at it) | Accepted; duplicates are ignored (idempotent on `event_id`); a malformed event is rejected with an E-ING code |
| VAL-TEL-05 | A | Offline outbox | Stop the service, generate events, restart, flush | Nothing lost; E-ING-02 rejections stay queued (SDD-08 §4.3) |
| VAL-TEL-06 | A | Numbers are right | Pick 5 portal numbers (e.g. first-try pass rate, PRs per month, runs waiting on me). Recompute each from the database with your own SQL (metric definitions M-xx in SDD-08/SDD-09) | Same values. Any difference is S2 |
| VAL-TEL-07 | A | Role filtering | Call the read API with tokens for business, engineer, eng lead, admin (test fixtures show how to mint local test tokens against a test JWKS) | Business: aggregates only. Engineer: own systems only (RD-2). Names only for eng lead/admin (RD-1) |
| VAL-TEL-08 | A | What leaves the laptop | Inspect outbox contents and every event schema in `schemas/events/` | Metadata only: no artifact text, no question text (RD-3), no code, no client names |
| VAL-TEL-09 | A | Monitoring | `make test-deploy-ops`; read `ops/monitoring` alert rules AL-01..AL-26 and dashboards | Each alert is actionable and links to an OPS-04 runbook section |
| VAL-TEL-10 | B | Claude Code OTel | With Shubham (spike S-10): point Claude Code OTel env at the local service `/otel` | Events arrive and join to `run_id` via `session_id` |
| VAL-TEL-11 | C | Live run on portal | Run a phase C brownfield run and watch it appear on Home (Engineer), Insights and Run detail | Appears within the ingest lag target (OPS-02); numbers update |
| VAL-TEL-12 | C | Test instance | Stand up the shared test instance with `deploy/docker-compose` on a VM | Healthy behind TLS; backups run; alerts fire on a forced failure |

**Decisions to recommend in your verdict:** RD-1..RD-5, telemetry retention (OQ-08, RD-4), which statistics matter most for the Business and Engineer dashboards, hosting option (OQ-02) from what you saw.

## 6. Cross-area scenario (all six together, phase C)

One shared run proves the pieces work together:

1. Gaurav stands up the test insights instance and the portal.
2. Shubham installs the plugin on two seats and confirms hooks.
3. Abhishek starts `/truminds:run brownfield-change ABC-142` on the sample system companion repo.
4. The run pauses on the 24-hour vs 30-day retention question; Ekjot answers it as product owner in `open-questions.md`.
5. Yash checks each check record and decision; Japman runs `tsl ci-verify` on the resulting PR.
6. Gaurav confirms the run, steps and outcomes on the portal for both personas.

Record the scenario as one GitHub issue with the label `validation:e2e` and link every finding to it.

## 7. Exit criteria for the validation

| # | Criterion |
| --- | --- |
| 1 | Every test in §5 is Pass, Fail-with-issue or Blocked-with-reason |
| 2 | No open S1 findings |
| 3 | All spikes S-01..S-15 have a result |
| 4 | Each area has a verdict file merged |
| 5 | Decisions recommended by each area are listed for Puneet |

## 8. Verdict file

Each area submits `docs/testing/validation/<area>-verdict.md` (areas: `skills`, `harness`, `execution`, `telemetry`) by pull request, using [the template](validation/verdict-template.md). Pairs submit one file together and say who tested what.

## 9. Ways of working

- Work in phases, not dates: finish phase A before B, and B before C where your tests depend on it.
- Post blockers as soon as you hit them (issue with `validation:blocked`).
- Do not fix code while validating unless it is a one-line fix; raise the issue first, then fix by PR linked to it, so the finding stays visible.
- Puneet reviews findings by severity and decides Go / Go with fixes / No-go per area.

## 10. What Puneet needs to arrange (blocks phase C)

| Item | From | Used for |
| --- | --- | --- |
| Entra ID **test** app registration (device code for `tsl`, auth code + PKCE for the portal) and test groups for the four app roles | IT / Entra admin | `tsl login`, portal sign-in |
| A test VM on the intranet for the insights service and portal | IT | Phase C, VAL-TEL-12 |
| A test GitHub org or repo for companion repos and test PRs | Puneet | `tsl pr`, `tsl ci-verify` |
| Claude seats for all six testers with the Claude Code desktop app | Claude admin | Phase B and C |
| Optional: a test Jira/Confluence space with no client data | Puneet | VAL-EXE-06 only |

## 11. Done criteria for this document

Every tester has read it, phase A has started, and each area has a named verdict file path.

## 12. Open items

| ID | Item | Owner |
| --- | --- | --- |
| TST-02-O1 | Entra test app, test VM, test GitHub org (§10) | Puneet |
| TST-02-O2 | Whether a client-facing person joins phase C as product owner | Puneet |
