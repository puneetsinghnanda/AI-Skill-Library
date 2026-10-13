# Truminds AI Skill Library — Implementation Readiness Tracker

Oct 12, 2026 · @Puneet Singh Nanda

## 1. Verdict

**We are not ready to start full implementation. We are ready to start the foundation work.**

The architecture, the flow, the quality-check (harness) logic and the data model are designed well enough that nobody has to guess *what* the system does. What is missing is the layer Claude Code needs to build each piece *without assuming*: detailed feature specs, the actual schema files, the skill template, the portal API, a backlog, a sample system to test against, and about a dozen decisions only you can make.

**Safe to start now** (no open decisions block them): data formats as real JSON Schema files, `tsl state` and `tsl decide` with their tests, the skill template, a Truminds-owned sample system, and a hooks spike that proves the Claude Code features we rely on.

**Must wait for you**: pilot choice, Release-1 scope and priority, hosting, portal technology (Backstage or custom), consent and legal wording, security reviewer, admin and IT setup.

### How to read the status

| Status | Meaning | Count |
| --- | --- | --- |
| Ready | Specified enough to build without assumptions | 0 |
| Mostly ready | Designed; small gaps that do not block starting | 3 |
| Partial | Direction is clear, but key details are missing; building now means guessing | 21 |
| Missing | Not written yet | 10 |
| Needs decision | Blocked on a choice by Puneet or another person | 6 |

Sources checked: the six documents (PRD, Personas and Stories, Architecture, Design and UX, API and Rules, Constraints), the Web UI prototype and the architecture deck.

### Team and areas of responsibility

Set by Puneet. Puneet monitors and assesses the work. Where the right owner is unclear, the owner is **TBD by Puneet**.

| Area | Owner(s) |
| --- | --- |
| Skills, workflows, roles (developer, tester, DevOps and others) | Abhishek Verma, Ekjot Singh |
| Harness, execution, `tsl verify` | Japman Singh, Yash Khorwal |
| Skill execution, hook execution | Shubham Bansal |
| Telemetry, types of logs, events, statistics published on the web portal | Gaurav Saini |

This replaces the earlier module ownership in Doc 3 §12.2.

Claude supports every owner. It drafts specs, schemas and code for the owner to review and accept. The owner stays accountable.

## 2. Tracker

**Owner** is the accountable person for each question. **Claude can draft** marks the items where I can do most of the work for the owner to review.

| # | Question | Status | Main gap | Owner | Claude can draft |
| --- | --- | --- | --- | --- | --- |
| 1 | Can Claude Code build without assumptions? | Partial | No per-module feature specs, schema files or backlog | TBD by Puneet | Yes |
| 2 | Is skill creation defined? | Partial | No SKILL.md template, rubric or eval-case format | Abhishek Verma, Ekjot Singh | Yes |
| 3 | Is skill chaining defined? | Partial | Output-to-input mapping, orchestrator behaviour, parallel steps | Abhishek Verma, Ekjot Singh (runtime side: Shubham Bansal) | Yes |
| 4 | Is the harness split (code vs AI) defined? | Mostly ready | Per-artifact check list and reviewer prompt not written | Japman Singh, Yash Khorwal | Yes |
| 5 | Is analytics transfer to the cloud defined? | Partial | Per-event schemas, tsl login token flow, improvement report spec | Gaurav Saini | Yes |
| 6 | Is the cloud DB schema defined? | Partial | Dashboard indexes and summary views, retention, seed data | Gaurav Saini | Yes |
| 7 | Where are the Claude Code hooks defined? | Partial | hooks.json not written; behaviour not verified against current docs | Shubham Bansal | Yes |
| 8 | Is the PRD complete, with features per phase? | Partial | No feature-to-phase table; exit criteria thin | TBD by Puneet | Yes |
| 9 | Which features need feature documents? | Missing | List below; none written yet | Per spec, see Q9 table | Yes |
| 10 | Web UI data, features and API | Missing | No portal read API (endpoints and responses) | Gaurav Saini | Yes |
| 11 | UX design of the Web UI | Partial | Not signed off; placeholder brand; Figma half-built | TBD by Puneet | Yes |
| 12 | Guardrails | Mostly ready | No single guardrail spec with test cases; prompt-injection handling thin | Shubham Bansal (hooks); Japman Singh, Yash Khorwal (harness gates) | Yes |
| 13 | Restrictions and constraints document | Partial | Exists (Doc 6); legal, consent and residency items open | TBD by Puneet | Partly |
| 14 | Tech stack | Mostly ready | Hosting and portal technology open; versions not pinned | TBD by Puneet | Recommend only |
| 15 | Works with other AI models or tools? | Partial | Skills portable; plugin, hooks, subagent are Claude-specific; no adapter design | TBD by Puneet | Yes |
| 16 | What is "done" for Release 1? | Needs decision | No pilot, no success targets | TBD by Puneet | Proposal only |
| 17 | First-build scope and priority | Needs decision | 17 skills listed, none ranked | TBD by Puneet | Proposal only |
| 18 | Which open questions block building? | Partial | OQ list not classified | TBD by Puneet | Yes (done in §6) |
| 19 | Backlog of tickets | Missing | No tickets | TBD by Puneet | Yes, with approval |
| 20 | Contracts between team members | Partial | Formats described, not as files | Each area owner for their formats; coordination TBD by Puneet | Yes |
| 21 | Build order and dependencies | Missing | Not written | TBD by Puneet | Yes |
| 22 | Repositories and branching | Partial | Only marketplace and companion repo described | TBD by Puneet | Yes |
| 23 | Developer setup | Partial | No setup guide | TBD by Puneet | Yes |
| 24 | Sample brownfield system | Missing | Does not exist | TBD by Puneet | Yes |
| 25 | Test strategy and test cases | Partial | Strategy exists; no cases | Each area owner for their module | Yes |
| 26 | How AI parts are tested | Partial | Eval approach exists; case format and thresholds unconfirmed | Abhishek Verma, Ekjot Singh (skill evals); Japman Singh, Yash Khorwal (reviewer evals) | Yes |
| 27 | How we measure harness accuracy | Needs decision | Audit rate open (OQ-11) | Japman Singh, Yash Khorwal; rate TBD by Puneet | Proposal only |
| 28 | Independent security review | Missing | Nobody assigned | TBD by Puneet | Review pack only |
| 29 | Consent wording and legal review | Needs decision | Not drafted, not reviewed | TBD by Puneet | Draft only |
| 30 | Admin roles and access | Needs decision | Roles defined; people not named | TBD by Puneet | No |
| 31 | Hosting, deploy, backup, cost | Needs decision | Cloud not chosen (OQ-02) | TBD by Puneet | After choice |
| 32 | Support and rollout of updates | Missing | Not written | TBD by Puneet | Yes |
| 33 | Monitoring of the cloud service | Missing | Not written | Gaurav Saini | Yes |
| 34 | Onboarding and training | Missing | Not written | TBD by Puneet | Yes |
| 35 | Adoption and value measures | Partial | Metrics named; baseline and targets not set | Gaurav Saini (measures); targets TBD by Puneet | Yes |
| 36 | Failure modes in practice | Partial | Covered in specs, no runbook | TBD by Puneet | Yes |
| 37 | Claude Code features behave as assumed? | Partial | Not verified against current Claude Code docs | Shubham Bansal | Yes |
| 38 | Seat usage limits | Missing | Unknown for long workflows | TBD by Puneet | No |
| 39 | Source of truth and change approval | Partial | Co-approver open (OQ-01) | TBD by Puneet | No |
| 40 | Decision log process | Partial | Decisions listed; no process | TBD by Puneet | Yes |

## 3. Answers: core design (Q1–Q5)

### Q1 · Does Claude Code have everything to build without assumptions? — Partial

**What exists:** the *what* is clear. That covers the components, the run states, the companion-repo layout, the harness algorithm, the database tables, the command list, the error codes, the event types and the screens.

**What is missing, and where Claude Code would have to guess:**

- **Per-artifact body schemas.** We have the envelope for `design.v1`, `intent.v1` and so on, but not the required sections and fields inside each one.
- **The skill content.** Not one SKILL.md, scoring checklist (rubric) or eval case has been written.
- **The context extractors.** Nothing defines how `tsl init-context` (now `tsl context build`) builds `module-map.json` or `api-inventory.json` for Java, Node, Python or C.
- **The portal read API** (see Q10).
- **The orchestrator** (see Q3).
- **Exact tsl behaviour** for each flag and edge case: Doc 5 is a summary, not a spec.
- **No backlog, no done criteria per ticket, no sample system** to test against.

**Honest view:** if we pointed Claude Code at the docs today, it would build working code, but it would invent field names, prompt wording and extractor logic. Those inventions are exactly the assumptions you want to avoid.

**Closes when:** the feature specs in Q9, the schema files in Q20, the backlog in Q19 and the sample system in Q24 exist.

### Q2 · Is it defined how skills are created? — Partial

**What exists:**

- The `skill-metadata.v1` example (Doc 5 §3.2).
- `tsl validate`, `/truminds:eval` and the publish story US-15.
- Status values (now `draft`, `pilot`, `production`, `deprecated`, SDD-01 §7).
- Version rules.
- The rule that an improvement must start with a failing eval case.

**What is missing:**

- **A SKILL.md template.** It should cover required sections, how the skill reads the context pack, how it writes the artifact envelope and claims, and how it hands over to the harness.
- **The rubric format** the reviewer scores against.
- **The eval-case format.** That means the input fixture, expected checks and pass rule.
- **The folder layout of a skill** in the marketplace repo.
- **A worked example skill.**

Without these, five skill authors will write five different styles.

**Closes when:** I write the template plus one reference skill end to end (recommended: `requirement-review`), with its rubric and 10 eval cases.

### Q3 · Is skill chaining in place? — Partial

**What exists:**

- `workflow.v1` with steps, `after:` dependencies and human gates (Doc 5 §3.3).
- The run state machine, locks, pause and resume.
- Retry limits.
- The rule that inputs must not be stale (H6).

**What is missing:**

- **How outputs bind to inputs.** For example, how `design` finds `impact.md` from step 3: by path, by step id or by schema name.
- **What the orchestrator actually is.** It could be a slash command prompt, a Claude subagent, or `tsl` deciding the next step and Claude only executing it. *My recommendation: `tsl` decides the next step, so the chain is code and not AI.*
- **Steps that could run in parallel** (`secure-code-review` and `test-plan`). Claude Code runs them one after another in one session; the docs should say so.
- **Multi-PR runs** across several repos.
- **What happens to downstream steps** when an upstream step is re-run after resume.

**Closes when:** a short "Orchestrator and chaining" feature spec exists.

### Q4 · Is the harness split (code vs AI) defined? — Mostly ready

**What exists:** this is the best-specified part of the design.

- The four-step order (code, AI reviewer, code verifies the citations, code decides).
- Hard gates H1–H7 and signals S1–S6.
- The band formula and the `decide()` pseudocode.
- The outcome rules and the autonomy table.
- The PRD §12 table of which checks code does and which the reviewer does, per artifact type.

**What is missing:**

- **The exact code check list per artifact type, as a catalogue.** For example, for `design.v1`: check named endpoints against `api-inventory.json`.
- **The reviewer subagent's own prompt and findings JSON schema.**
- **The citation matcher rules** (string match or code-structure match, per language).
- **Confirmed thresholds.** They are proposals until pilot data exists (OQ-12).

**Closes when:** a "Harness checks catalogue" spec and the reviewer prompt exist. The thresholds stay proposals until the pilot.

### Q5 · How does analytics data reach the cloud and drive improvement? — Partial

**What exists:**

- Three sources joined by `run_id`: tsl events, Claude Code OpenTelemetry, and the GitHub webhook.
- Endpoints, batching and idempotency by `event_id`.
- The offline outbox and the metadata-only rule.
- The event type list (Doc 5 §5).
- Improvement through a plain-code weekly report plus `/truminds:improve`, with an eval case first.

**What is missing:**

- **The full JSON schema for each event body.** Today it is a field list.
- **How `tsl login` gets and refreshes the token** to call the API. This depends on which SSO provider (identity provider) the company uses.
- **Which Claude Code OpenTelemetry metrics we keep**, and how we tie a Claude session to a run.
- **The weekly improvement report**: its queries, layout and where it is delivered.

**Closes when:** an "Events and telemetry" spec exists, and I know the SSO provider (needs you).

## 4. Answers: data, hooks, scope, specs, UI data (Q6–Q10)

### Q6 · What is the cloud database schema? — Partial

**What exists:** PostgreSQL 16 tables in Doc 3 §9.1:

- `client`, `project`, `system`;
- `app_user`, `role_grant`, `signing_key`;
- `skill`, `skill_version`;
- `run`, `step`, `verification`, `pull_request`, `event`.

There are also rules for changing the schema over time (Alembic, forward-only).

**What is missing:**

- **Indexes and summary views** behind each dashboard number, for example first-try pass per skill per period. Without them the dashboards will be slow or each built differently.
- **A `pod` and `pod_version` table.** Pods appear in the UI but not in the schema.
- **How raw events are turned into `run` and `step` rows.** It isn't written whether the API writes both at once or a background job does it.
- **Retention and deletion rules** (OQ-08).
- **Where the pseudonym-to-person mapping is stored and who can read it.**
- **Seed data** for development.

**Closes when:** I add these to Doc 3 §9 as a schema v1.1 with migrations. Retention needs your decision.

### Q7 · Where are the Claude Code hooks defined? — Partial

**What exists:** Doc 5 §4. It lists four hooks:

- PreToolUse policy check;
- PreToolUse on the `Skill` tool, to check inputs;
- PostToolUse after a write, to run `tsl verify`;
- SessionEnd, to save state and flush events.

It also covers their input and output, the fail-closed and fail-open rules, and the `policy.v1` file. The hooks ship inside the plugin as `hooks/hooks.json`.

**What is missing, honestly:**

- **The `hooks.json` file itself is not written.**
- **Several Claude Code behaviours are assumptions that have not been checked against the current Claude Code documentation:**
  - that a PreToolUse hook can match the `Skill` tool;
  - the exact JSON fields Claude Code passes in;
  - that hooks shipped in a plugin are enforced when admins require the plugin;
  - the SessionEnd timing.

This is the highest technical risk in the design.

**Closes when:** I check each assumption against the current Claude Code docs and build a small spike plugin that proves each hook fires as designed.

### Q8 · Is the PRD complete, and what is in which phase? — Partial

**What exists:**

- PRD §6 has Phases 0–3 with gates G0–G3 (no dates, per your rule).
- Requirements FR-\* are linked to user stories.
- There is a do-not-build list (Doc 6 §5) with Phase 2 and 3 items: mobile verifiers, the pod builder, GitLab.

**What is missing:**

- **A single table assigning every feature, skill, workflow and pod to a phase.**
- **Measurable exit criteria for each gate.** For example: "G1 = 3 skills at ≥ 80% first-try on the sample system, CI verify live on one repo".
- **Release-1 scope** depends on your answers to Q16 and Q17.

**Closes when:** you confirm scope and priority; I then write the phase table and gate criteria into PRD §6.

### Q9 · Which features need their own feature document? — Missing

None are written yet. These are the ones I recommend. Each is short (3–6 pages) and written to the standard of "Claude Code can build it without guessing":

| # | Feature spec | Owner | Why it is needed |
| --- | --- | --- | --- |
| F1 | Skill authoring standard: template, rubric, eval format, reference skill | Abhishek Verma, Ekjot Singh | Q2 |
| F2 | Orchestrator and chaining | Abhishek Verma, Ekjot Singh (workflow definition); Shubham Bansal (runtime) | Q3 |
| F3 | Harness checks catalogue and reviewer prompt | Japman Singh, Yash Khorwal | Q4 |
| F4 | Context pack and extractors (per language), drift and refresh | TBD by Puneet | Q1 |
| F5 | `tsl` CLI full behaviour spec | Japman Singh, Yash Khorwal | Q1 |
| F6 | Hooks and policy (verified against Claude Code) | Shubham Bansal | Q7, Q12 |
| F7 | Signing, login and key management | TBD by Puneet | Q5, Q28 |
| F8 | Events, telemetry API and ingestion | Gaurav Saini | Q5, Q6 |
| F9 | CI verify action | Japman Singh, Yash Khorwal | Q1 |
| F10 | Portal read API and screen data contracts | Gaurav Saini | Q10 |
| F11 | Pod definition format (`pod.v1`) and pod pages | Abhishek Verma, Ekjot Singh | Q6, Q8 |
| F12 | Improvement loop (weekly report, `/truminds:improve`) | Abhishek Verma, Ekjot Singh; report data from Gaurav Saini | Q5 |
| F13 | Onboarding and admin (seats, managed settings, consent) | TBD by Puneet | Q29, Q30 |
| F14 | Companion repo lifecycle (create, multi-repo, migrate) | TBD by Puneet | Q22 |

### Q10 · What data the Web UI shows, and which APIs it calls — Missing

**What exists:** Doc 4 §2.0.4 maps each screen and number to its source tables and events. The prototype shows every field.

**What is missing:** the API the portal calls.

- Doc 5 only defines the *write* side: `POST /v1/events`, keys and the webhook.
- No read endpoints exist. The portal needs, for example:
  - `GET /v1/catalogue/skills`
  - `GET /v1/pods/{id}`
  - `GET /v1/insights/business`
  - `GET /v1/insights/engineering/runs`
  - `GET /v1/runs/{id}`
- Each needs its filters, paging, response format, and the permission check (Business vs Engineer, own projects only, pseudonyms).
- The catalogue's source is also undecided: read the marketplace repo directly, or sync it into the database.

**Closes when:** I write spec F10 with an OpenAPI file. It depends on Q14: Backstage or custom web app (OQ-15).

## 5. Answers: UX, guardrails, constraints, stack, other models (Q11–Q15)

### Q11 · Is the Web UI UX design done? — Partial

**What exists:**

- An interactive prototype with 13 screens, a working Business / Engineer switch and a persona map.
- Screen-by-screen specs, components, states and accessibility rules (Doc 4 §2.0).
- A Figma file with brand variables and 3 screens.

**What is missing:**

- **Your sign-off** that this is the version to build.
- **Real Truminds brand colours and logo** (OQ-13).
- **Empty, loading and error states** are described but not drawn.
- **Phone layouts** were not visually checked.
- **Figma is half built**, because your View seat hit its limit.
- **Admin screens** (users, roles, consent) are not designed.

**Closes when:** you review the prototype and send brand assets. I then draw the missing states and admin screens. Figma needs a Dev or Full seat if you want it there.

### Q12 · Guardrails — Mostly ready

**What exists:**

- **Policy file** (`policy.v1`): write and read allow/deny lists, blocked shell commands, MCP writes need approval, never merge or deploy.
- **Hard gates:** H4 (no secrets, personal data or client names in outputs) and H7 (only permitted tools).
- **Rules** R-14 to R-17.
- **Approval roles**, including the rule that you cannot approve your own work.
- **A STRIDE threat model** with 14 threats (Doc 3 §8).
- **Company seats only** and consent before use.

**What is missing:**

- **One consolidated guardrail spec** that lists each guardrail, where it is enforced (hook, harness, CI or process) and the test proving it works.
- **Concrete prompt-injection handling**, for example when a repo file or ticket says "ignore previous instructions".
- **The secrets and personal-data detectors** are not chosen (which scanner, which patterns).

**Closes when:** I write the guardrail spec with a test case for each guardrail (part of F6).

### Q13 · Restrictions and constraints document — Partial

**What exists:** Doc 6, with:

- constraints C-01 to C-15;
- assumptions A-01 to A-07;
- DPDP and GDPR notes;
- limitations L-01 to L-11;
- the do-not-build list X-01 to X-17.

**What is missing:**

- **Legal review** of consent and data-processing wording (OQ-06).
- **Data residency** (OQ-03).
- **Confirmation of the assumptions**, for example that admins can enforce managed settings (A-02) and that client repos are on GitHub (A-03).
- **Your sign-off.**

**Closes when:** you and legal or IT confirm the open items. I update Doc 6.

### Q14 · Tech stack — Mostly ready

**Decided:**

- Claude Code desktop with a plugin from the marketplace.
- Agent Skills (SKILL.md).
- MCP for Jira, Confluence, GitHub and Figma.
- Python 3.12 for `tsl` and the hooks, with Typer, Pydantic and jsonschema.
- Ed25519 signing.
- Docker verifiers.
- FastAPI with PostgreSQL 16.
- The OpenTelemetry Collector.
- GitHub and GitHub Actions.
- Company SSO.

**Open:**

- **Hosting cloud** (OQ-02).
- **Portal technology:** Backstage or a custom web app (OQ-15). This changes Ekjot's and Gaurav's work significantly.
- **The secrets scanner and static-analysis tools** inside the verifier containers.
- **Exact library versions** are not pinned.

**My recommendation for the portal:** a custom React web app on the FastAPI service. The prototype is already a custom design, and Backstage would add a large framework for a few screens. It is your call.

### Q15 · Can it work with other AI models or tools? — Partial

**Portable today:**

- **Skills** use the open Agent Skills standard, which Copilot, Cursor, Codex and Gemini CLI also read.
- **`tsl`** (checks, decide, signing, state, PR) is plain Python with no model inside, so any tool that can run a shell command can use it.
- **CI verify, the database and the portal** do not depend on the model at all.

**Tied to Claude Code:**

- the plugin and marketplace format;
- the `/truminds:*` commands;
- the hook events and their input format;
- the reviewer as a Claude subagent;
- Claude Code OpenTelemetry.

**What another tool would need:** an adapter per tool that maps its hook or extension system to the same `tsl` calls, plus a way to run the reviewer. Not every tool has equivalent hooks, so enforcement would be weaker there and CI would carry more of it.

**Honest view:** the design keeps the door open, but multi-model support is not designed and is out of scope for Release 1 (company Claude seats only, C-03). If you want it later, I can write a short "portability adapter" design so the Release-1 code doesn't close that door.

## 6. Answers: scope, plan, setup, testing (Q16–Q27)

### Q16 · What is "done" for Release 1? — Needs decision

The PRD says targets are set after a baseline, and the pilot systems are open (OQ-04).

**I need from you:**

- which pilot (a Truminds internal system and/or one consented client system);
- what result counts as success.

**My proposal to react to:** on the pilot system, `brownfield-change` runs end to end on 10 real tickets, with:

- at least 70% of steps passing first time;
- zero merged PRs that bypassed records;
- tech leads agreeing that every High-confidence result they audited deserved High.

### Q17 · First-build scope and priority — Needs decision

Doc 3 §7 lists 17 skills and 5 workflows, but none are ranked.

**My proposal:** build the thinnest path first, the `brownfield-change` chain. In order:

- requirement-review;
- impact-analysis;
- design;
- implement;
- unit-test.

The rest come after the chain works end to end. You decide.

### Q18 · Which open questions block building? — Partial

**Block building now:**

- OQ-15: portal technology;
- OQ-10: which GitHub org hosts companion repos;
- OQ-04: pilot systems;
- OQ-16: Release-1 pods.

**Block going live, not coding:**

- OQ-02: hosting;
- OQ-03: data residency;
- OQ-06: legal consent;
- OQ-08: telemetry retention.

**Can wait:**

- OQ-01: co-approver;
- OQ-05: SME;
- OQ-07: stage approvers;
- OQ-09 and OQ-12: limits, which have defaults;
- OQ-11: audit rate;
- OQ-13: brand;
- OQ-14: client people answering questions.

### Q19 · Backlog of tickets — Missing

No backlog exists. The Atlassian connector is available in this session, so once the feature specs exist I can create the Jira epics and tickets. Each ticket would carry:

- a link to its spec and user story;
- acceptance criteria;
- done criteria;
- an owner.

I will only do this with your go-ahead, per the "no writes to Jira without approval" rule.

### Q20 · Contracts between team members — Partial

The formats are described in Doc 5 as examples:

- `tsl.yaml`;
- the skill metadata file;
- `workflow.v1`;
- state and lock files;
- the artifact envelope;
- the records;
- events;
- the CLI JSON output.

They are not yet real JSON Schema files in a repo. Until they are, the five people will interpret them differently. **I can write all schema files plus sample files that pass validation**; this is the single most useful thing to unblock parallel work.

### Q21 · Build order and dependencies — Missing

Not written. The natural order is:

1. **Schemas.**
2. **In parallel:**
   - `tsl state` and the events API skeleton (Abhishek);
   - `tsl verify` and `decide` (Japman);
   - the hooks spike (Shubham);
   - portal shells on mock data (Ekjot, Gaurav).
3. **The first skill and the sample system.**
4. **End-to-end on the sample system.**
5. **CI verify and the dashboards on real events.**

I'll draw this as a dependency diagram when you approve.

### Q22 · Repositories and branching — Partial

Only the marketplace repo and the companion-repo layout are described.

**Proposed repos:**

- `truminds-skill-library`: plugin, skills, workflows, `tsl`, schemas;
- `truminds-companion-template`;
- `truminds-insights-service`: FastAPI and database;
- `truminds-portal`;
- `tsl-ci-verify`: the GitHub Action.

Still to decide:

- the branch model, release tagging and code owners;
- **which GitHub org** they live in (needs you).

### Q23 · Developer setup — Partial

Tools are named, but there is no setup guide. I can write the guide and a dev container / `make dev` setup:

- Python 3.12;
- Docker;
- the Claude Code version;
- local PostgreSQL;
- the sample system.

### Q24 · Sample brownfield system — Missing

The test plan needs a Truminds-owned system with no client code. It doesn't exist. **I can build one**: a small order service with a real database, API, retention rule and a few known quirks, so the ABC-142 example can be run for real. I can also make a second one in another language, to test that the skills are domain- and language-agnostic.

### Q25 · Test strategy and test cases — Partial

Doc 3 §12 defines the test layers and the done criteria per module. No test cases are written. I can write them as part of each feature spec, plus the golden-file tests for `decide()`: known inputs with an expected outcome, checked on every change.

### Q26 · How the AI parts are tested — Partial

**The approach is set:**

- signed eval runs on the seat;
- a minimum of 10 cases and a 90% pass rate (proposed);
- every improvement must first add a failing case.

**Missing:**

- the eval-case file format (part of F1);
- the real cases;
- **your confirmation of the 90% threshold.**

Also, the reviewer subagent needs its own eval set: does it find planted defects, and does it avoid inventing ones that aren't there?

### Q27 · How we measure harness accuracy — Needs decision

The design is set: tech leads audit a sample of High-confidence results, and any miss tightens the thresholds and adds an eval case.

**Missing:**

- the audit rate (OQ-11);
- who audits;
- how often a miss must happen before action is taken.

**My proposal:** audit 1 in 10 High results during the pilot, then 1 in 25.

## 7. Answers: security, operations, adoption, platform, governance (Q28–Q40)

### Q28 · Independent security review — Missing

The threat model and signing design were written by me and have not been reviewed by anyone else. **A security person at Truminds should review:**

- Doc 3 §8;
- the policy file;
- key handling.

They should do this before any client code is touched. I can prepare a review pack and checklist for them.

### Q29 · Consent wording and legal review — Needs decision

Not drafted. **I can draft a consent template** covering:

- what is processed;
- by which model provider, on company seats;
- what leaves the laptop: metadata only;
- retention;
- withdrawal.

Legal must review it. I am not a lawyer, and this needs a qualified one.

### Q30 · Admin roles and access — Needs decision

The seven roles and the permission matrix are defined (Doc 2 §2). **Not named:** who the admins, tech leads and skill owners are for Release 1.

### Q31 · Hosting, deploy, backup, cost — Needs decision

The cloud is not chosen (OQ-02). The service is small (one API, one PostgreSQL, one portal), so any major cloud or the company's internal hosting works. **Once you choose,** I can write:

- the deployment setup (container, database, secrets from the cloud's secret store);
- backup and restore;
- a cost estimate.

### Q32 · Support and update rollout — Missing

Not written. It needs:

- who answers engineers' questions;
- how a new plugin version is released (tag, marketplace update, changelog);
- how to roll back a bad skill version: pin the previous version in managed settings;
- how running workflows are protected. Runs already pin their versions (R-08).

I can write this runbook.

### Q33 · Monitoring of the cloud service — Missing

Not written. It needs:

- service health checks;
- error-rate and ingest-lag alerts;
- database storage alerts;
- a "devices with old outbox events" alert.

I can add it to F8.

### Q34 · Onboarding and training — Missing

US-18 covers the admin steps only. Still missing:

- an engineer guide;
- a skill-author guide;
- a tech-lead guide for context packs and approvals;
- a 30-minute hands-on session on the sample system.

I can write all four once the first skill works.

### Q35 · Adoption and value measures — Partial

PRD §5 names the metrics and the portal shows them. **Missing:**

- the baseline (how long tickets take today, without the library);
- targets.

You need to decide whether to measure a baseline on the pilot team before starting.

### Q36 · Failure modes in practice — Partial

The specs cover these:

- stale pack;
- stale lock;
- retries exhausted;
- abort;
- offline;
- missing records in CI.

No operational runbook says **who** acts on each and **what** they do. I can write it.

### Q37 · Do Claude Code features behave as we assume? — Partial (highest technical risk)

The design relies on the following, all taken from earlier research and not re-checked against today's documentation:

- plugin marketplaces and admin-required plugins;
- hooks and their input fields (including matching the `Skill` tool);
- subagents;
- slash commands;
- Claude Code OpenTelemetry export;
- skills.

**I can verify each against the current Claude Code docs** and build a tiny spike plugin. Running the spike on a real company seat needs an engineer (Shubham) because I can't run the desktop app.

### Q38 · Seat usage limits — Missing

Unknown: how much a long workflow uses against company seat limits, and what happens when a limit is reached mid-run. The resume design means a run can continue later, but we need real numbers. **Needs:**

- your Claude admin, for the plan's limits;
- one measured end-to-end run on the sample system.

### Q39 · Source of truth and change approval — Partial

The six-document set is the source of truth, and the project pointer doc lists it. Puneet approves. **Open:**

- the co-approver (OQ-01);
- the rule for who may change which document.

### Q40 · Decision log — Partial

Decisions D-01 to D-16 are recorded in PRD §7, but there is no process for new ones. **Proposal:** one short decision record per decision, in the skill-library repo, linked from PRD §7; each one is approved by you before code depends on it. I can set up the template.

## 8. What I need from you

**Decisions that unblock building (please answer first):**

| # | Decision | Question |
| --- | --- | --- |
| 1 | Portal technology: Backstage or custom web app (OQ-15) | Q10, Q14 |
| 2 | Pilot system(s) and what success looks like (OQ-04) | Q16 |
| 3 | Release-1 skills and pods, in priority order (OQ-16) | Q17 |
| 4 | GitHub org for the Truminds repos and companion repos (OQ-10) | Q22 |
| 5 | Company SSO provider, so `tsl login` and the portal can be specified | Q5 |
| 6 | Confirm or change the proposed thresholds: 90% eval pass, 1-in-10 audits, default limits (OQ-11, OQ-12) | Q26, Q27 |

**Decisions needed before going live:**

- hosting cloud (OQ-02);
- data residency (OQ-03);
- telemetry retention (OQ-08);
- named admins, tech leads and skill owners (Q30);
- whether to measure a baseline (Q35).

**People or functions to bring in:**

- **Security reviewer** for the threat model and signing (Q28).
- **Legal** for consent and data processing (Q29).
- **Claude admin / IT** for managed settings, seat limits and plugin enforcement (Q37, Q38).
- **Brand** colours and logo (Q11).
- **Sign-off** on the UX prototype (Q11) and the constraints doc (Q13).

## 9. What I can take care of, and how

Everything below I can do in this workspace. Code arrives as files or a zip, or is pushed to GitHub if you connect a repo. Docs go into the six-document set. I won't write to Jira, Confluence or any client system without your explicit go-ahead.

| Order | Work | Closes | How I deliver it |
| --- | --- | --- | --- |
| 1 | **Verify Claude Code assumptions** against current docs; build a spike plugin (hooks, Skill matcher, subagent, managed settings, OTel) | Q7, Q37 | Findings note + spike plugin; Shubham runs it on a company seat |
| 2 | **All schema files** (JSON Schema) with valid and invalid samples | Q20 | `schemas/` folder + tests |
| 3 | **Feature specs F1–F14** to the "no guessing" standard, starting with F1, F2, F3, F5, F6 | Q1–Q4, Q9, Q12 | New docs linked from the PRD |
| 4 | **Skill template + reference skill** `requirement-review` with rubric and 10 eval cases | Q2, Q26 | SKILL.md, rubric, evals |
| 5 | **Sample brownfield system** (order service, plus a second language) | Q24 | Repo with README |
| 6 | **Code foundations:** `tsl` skeleton (state, verify, decide, sign), `decide()` golden tests, FastAPI events service with database migrations | Q4–Q6, Q25 | Python repos with tests passing |
| 7 | **Portal read API** (OpenAPI) and database v1.1 (pods, views, indexes) | Q6, Q10 | Spec + migration |
| 8 | **Phase table and gate criteria** in PRD §6; open-question triage; build-order diagram | Q8, Q18, Q21 | PRD update |
| 9 | **Backlog:** epics and tickets with acceptance criteria and owners | Q19 | Jira, only after your approval |
| 10 | **Runbooks and guides:** dev setup, support and rollout, monitoring, failure modes, onboarding, decision-record template | Q23, Q32–Q34, Q36, Q40 | Docs + repo files |
| 11 | **Drafts for others to review:** consent template, security review pack, hosting design once the cloud is chosen | Q28, Q29, Q31 | Drafts marked "for review" |
| 12 | **UX completion:** empty, error and admin screens; brand swap | Q11 | Prototype update |

**What I cannot do alone:**

- run Claude Code desktop on a company seat;
- make your scope and hosting decisions;
- give legal or security sign-off;
- see your seat limits;
- edit Figma beyond the View-seat limit.

**Suggested next step:** say go on items 1–5. They need none of the open decisions, and they remove most of the "Partial" ratings.

## 10. Proposed design document set

**Decisions taken by Puneet, 12 Oct 2026:**

| Topic | Decision | Effect |
| --- | --- | --- |
| Where documents live | Design documents (SDDs, SEC-01, TST-01, PLN-01) in Claude Docs, next to the six existing docs. ADRs, the developer guide and runbooks (DEV-01, OPS-01–04, GOV-01) as markdown in the skill-library repo | Section 10 tables apply as written |
| Portal technology (OQ-15) | **Custom web app**: React front end on the FastAPI insights service. Backstage is dropped | Closes OQ-15; updates D-15 and Doc 3 §11; SDD-09 designed for React |
| Identity provider | **Microsoft Entra ID** (OIDC): device-code flow for `tsl login`, authorization-code flow with PKCE for the portal | Unblocks SDD-07 and the token part of SDD-08 |
| Sample brownfield system | **Most probably React front end + Node.js back end.** Database not yet stated; PostgreSQL proposed | First context extractor targets JavaScript/TypeScript; the order-history example is built on it |

The six existing documents stay as the top level: PRD, Personas, Architecture (high-level design), UX, API and Constraints. The detailed design is split into separate documents, one per component plus a few cross-cutting ones, the way most engineering teams organise it. Each detailed design document has the same sections:

- scope;
- context and dependencies;
- design, with diagrams;
- data formats and interfaces;
- error handling;
- security;
- test plan;
- done criteria;
- open items;
- validator sign-off.

Each must stay consistent with Doc 3 (architecture and tech stack) and Doc 5 (APIs and rules); any deviation is raised as an architecture decision record (ADR) first.

**Detailed designs (software design documents, SDD), one per component:**

| ID | Document | Covers | Validator |
| --- | --- | --- | --- |
| SDD-01 | Skill authoring standard and catalogue | F1 · Q2, Q26 | Abhishek Verma, Ekjot Singh |
| SDD-02 | Workflow orchestration and chaining | F2 · Q3 | Abhishek Verma, Ekjot Singh; Shubham Bansal |
| SDD-03 | Harness: checks catalogue, reviewer, decide, CI verify | F3, F9 · Q4, Q27 | Japman Singh, Yash Khorwal |
| SDD-04 | `tsl` command-line tool | F5 · Q1 | Japman Singh, Yash Khorwal |
| SDD-05 | Claude Code integration: plugin, commands, hooks, policy | F6 · Q7, Q12, Q37 | Shubham Bansal |
| SDD-06 | Context pack and extractors | F4 · Q1 | TBD by Puneet |
| SDD-07 | Identity, signing and keys | F7 · Q5 | TBD by Puneet |
| SDD-08 | Telemetry and insights service, database | F8 · Q5, Q6, Q33 | Gaurav Saini |
| SDD-09 | Web portal and read API | F10 · Q10, Q11, Q35 | Gaurav Saini; UI owner TBD by Puneet |
| SDD-10 | Pods | F11 · Q8 | Abhishek Verma, Ekjot Singh |
| SDD-11 | Improvement loop | F12 · Q5 | Abhishek Verma, Ekjot Singh; Gaurav Saini |
| SDD-12 | Companion repo lifecycle | F14 · Q22 | TBD by Puneet |
| SDD-13 | Onboarding and administration | F13 · Q30, Q34 | TBD by Puneet |

**Cross-cutting documents:**

| ID | Document | Covers | Validator |
| --- | --- | --- | --- |
| SEC-01 | Security design and threat model (guardrails, prompt injection, secret and PII detection) | Q12, Q28 | Security reviewer TBD by Puneet |
| TST-01 | Master test plan (test layers, AI evals, harness accuracy, sample systems) | Q24–Q27 | Each area owner |
| DEV-01 | Developer guide: repos, branching, setup, coding standards, contribution | Q22, Q23 | TBD by Puneet |
| OPS-01 | Deployment and hosting | Q31 | TBD by Puneet (after hosting choice) |
| OPS-02 | Monitoring and alerting | Q33 | Gaurav Saini |
| OPS-03 | Release, rollout and support | Q32 | TBD by Puneet |
| OPS-04 | Failure-mode runbook | Q36 | TBD by Puneet |
| PLN-01 | Delivery plan: phase table, gate criteria, build order, backlog map | Q8, Q16–Q19, Q21 | Puneet |
| GOV-01 | ADR log and document change process | Q39, Q40 | Puneet |
| LEG-01 | Client consent and data-processing template (draft for legal) | Q29 | Legal, TBD by Puneet |

**Code deliverables:**

- schema files (Q20);
- the reference skill (Q2);
- the sample system (Q24);
- the `tsl` and service skeletons (Q4–Q6);
- the Claude Code integration spike (Q37).

They go into the repos in DEV-01 once you confirm where they live.

## 11. Build plan per question

**What I can build** tells you what I take on:

- **Full** = I build it end to end and the owner validates it.
- **Draft** = I prepare it, someone else decides or approves.
- **No** = only a person can do it.

| Q | What I will produce | What I can build | Lives in | Validator | Blocked by |
| --- | --- | --- | --- | --- | --- |
| 1 | Closed by the SDD set, schemas, backlog and sample system; re-assessed at the end | Full | This tracker | TBD by Puneet | All SDDs |
| 2 | SKILL.md template, rubric format, eval format, reference skill `requirement-review` with 10 evals | Full | SDD-01 + skill-library repo | Abhishek Verma, Ekjot Singh | Nothing |
| 3 | Chaining rules, orchestrator design (`tsl` picks the next step), parallel and resume behaviour | Full | SDD-02 | Abhishek Verma, Ekjot Singh; Shubham Bansal | Nothing |
| 4 | Checks catalogue per artifact type, reviewer prompt and findings schema, citation matcher, `decide()` with golden tests | Full | SDD-03 + code | Japman Singh, Yash Khorwal | Nothing |
| 5 | Event schemas, ingestion design, OTel handling, weekly report spec | Full | SDD-08, SDD-11 | Gaurav Saini | SSO provider (token flow) |
| 6 | Schema v1.1: pods, indexes, summary views, retention job, seed data, migrations | Full | SDD-08 + code | Gaurav Saini | Retention (OQ-08) for final value |
| 7 | `hooks.json`, policy file, behaviour verified against current Claude Code docs, spike plugin | Full (running it needs a seat) | SDD-05 + spike | Shubham Bansal | Nothing |
| 8 | Phase table and gate criteria | Draft | PLN-01, PRD §6 | Puneet | Scope (Q16, Q17) |
| 9 | All 13 SDDs | Full | Section 10 | Per SDD | See each |
| 10 | Read API (OpenAPI), permission rules, data contract per screen | Full | SDD-09 | Gaurav Saini | Portal technology (OQ-15) |
| 11 | Empty, error and admin screens; brand swap | Full | Doc 4 + prototype | TBD by Puneet | Brand assets, sign-off |
| 12 | Guardrail catalogue with enforcement point and test case each; injection handling; detector choice | Full | SEC-01 | Shubham Bansal; Japman Singh, Yash Khorwal | Nothing |
| 13 | Doc 6 updates once items are confirmed | Draft | Doc 6 | Puneet | Legal, residency |
| 14 | Recommendation and pinned versions | Draft | Doc 3 §11 + ADR | Puneet | Hosting, portal choice |
| 15 | Portability adapter design (not built in Release 1) | Full (design only) | ADR | Puneet | Nothing |
| 16 | Release-1 success proposal | Draft | PLN-01 | Puneet | Your decision |
| 17 | Priority proposal | Draft | PLN-01 | Puneet | Your decision |
| 18 | Open-question triage (done) | Full | Tracker §6 | Puneet | Nothing |
| 19 | Epics and tickets with acceptance criteria | Full (Jira only with approval) | Jira | Puneet | SDDs |
| 20 | JSON Schema files with valid and invalid samples | Full | skill-library repo `schemas/` | Each area owner | Nothing |
| 21 | Build-order dependency diagram | Full | PLN-01 | Puneet | Nothing |
| 22 | Repo layout, branching, release tags, code owners | Draft | DEV-01 | TBD by Puneet | GitHub org (OQ-10) |
| 23 | Setup guide and dev container | Full | DEV-01 | TBD by Puneet | Repos |
| 24 | Sample brownfield systems | Full | Own repo | TBD by Puneet | Language choice |
| 25 | Test cases per module | Full | TST-01 + each SDD | Each area owner | SDDs |
| 26 | Eval-case format, skill and reviewer eval sets | Full | TST-01, SDD-01, SDD-03 | Abhishek Verma, Ekjot Singh; Japman Singh, Yash Khorwal | Threshold confirmation |
| 27 | Audit procedure | Draft | SDD-03 | Japman Singh, Yash Khorwal | Audit rate (OQ-11) |
| 28 | Security review pack and checklist | Draft | SEC-01 | Security reviewer | A named reviewer |
| 29 | Consent template | Draft | LEG-01 | Legal | A named legal contact |
| 30 | — | No | Doc 2 §2 | Puneet | Names |
| 31 | Hosting and deployment design, cost estimate | Draft | OPS-01 | Puneet | Hosting choice (OQ-02) |
| 32 | Release and support runbook | Full | OPS-03 | TBD by Puneet | Nothing |
| 33 | Monitoring and alert design | Full | OPS-02 | Gaurav Saini | Hosting for tooling |
| 34 | Engineer, author and tech-lead guides; hands-on session | Full | SDD-13 | TBD by Puneet | First skill working |
| 35 | Metric definitions and queries | Full (targets: no) | SDD-08 | Gaurav Saini | Your targets |
| 36 | Failure-mode runbook | Full | OPS-04 | TBD by Puneet | Nothing |
| 37 | Verification findings and spike | Full (running it needs a seat) | SDD-05 | Shubham Bansal | Nothing |
| 38 | — | No | — | Claude admin | Admin data |
| 39 | — | No | GOV-01 | Puneet | Co-approver |
| 40 | ADR template and change process | Full | GOV-01 | Puneet | Nothing |

**Totals:** I can build 27 fully (2 of them need a seat to run), draft 10 for someone else to decide, and 3 need a person only (Q30, Q38, Q39).
