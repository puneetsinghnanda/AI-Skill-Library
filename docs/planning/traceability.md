# Traceability: readiness tracker and requirements to the repository

| Field | Value |
| --- | --- |
| Status | Draft for owner review |
| Owner | Puneet Singh Nanda |
| Approver | Puneet Singh Nanda |
| Related docs | [Readiness tracker](readiness-tracker.md) · [PLN-01](PLN-01-delivery-plan.md) · [PRD](../product/01-prd.md) · [Personas and Stories](../product/02-personas-and-stories.md) · [docs index](../README.md) · [Release 1 gate checklist](release-1-gate-checklist.md) |

## 1. Scope and method

This document answers one question: **is everything promised in the readiness tracker in this repository?** It walks the tracker in full (§2 table with the §3–§7 answers, §8, §9, §10 and §11) and then maps every PRD requirement and every user story to a design section and to code or a test.

**Statuses**

| Status | Meaning |
| --- | --- |
| Delivered | In the repo; code items have passing tests (`make test-all`) |
| Delivered (draft for owner review) | In the repo as a document or file at status "Draft for owner review"; the named validator still has to review it |
| Needs Puneet / external | What the repo can hold is there; the item stays open until a named person decides or acts. The row says exactly what is needed and from whom |
| Missing | Not in the repo |

For the §2 questions the status says whether the **question is closed**. For §9 and §11 rows it says whether **the promised work product** is in the repo. A question can therefore be "Needs Puneet / external" while its §11 work product is "Delivered".

**Counts**

| Section | Items | Delivered | Delivered (draft for owner review) | Needs Puneet / external | Missing |
| --- | --- | --- | --- | --- | --- |
| §2 Questions Q1–Q40 | 40 | 10 | 13 | 17 | 0 |
| §4 Q9 feature specs F1–F14 | 14 | 0 | 14 | 0 | 0 |
| §8 What I need from you | 16 | 2 | 0 | 14 | 0 |
| §9 What I can take care of (12 rows + 5 "cannot do alone") | 17 | 5 | 6 | 6 | 0 |
| §10 Document set (4 decisions, 6 top-level docs, 13 SDDs, 10 cross-cutting, 5 code deliverables) | 38 | 8 | 30 | 0 | 0 |
| §11 Build plan rows Q1–Q40 | 40 | 14 | 20 | 6 | 0 |
| **Total** | **165** | **39** | **83** | **43** | **0** |

Nothing in the tracker is Missing. Items built during this audit are marked **(built in this audit)**. Gaps that the tracker does not list but the designs promise are in §9.

## 2. Tracker §2 and the answers in §3–§7 (Q1–Q40)

| Q | Question | Delivered by (repo paths) | Status | What is still needed, from whom |
| --- | --- | --- | --- | --- |
| 1 | Can Claude Code build without assumptions? | All SDDs in `docs/design/`; `schemas/`; `docs/planning/backlog.csv` (built in this audit); `examples/sample-system/` | Delivered (draft for owner review) | Each SDD validator reviews their SDD (G0-3) |
| 2 | Is skill creation defined? | SDD-01; `plugins/truminds/skills/requirement-review/` (SKILL.md, `skill.yaml`, `rubric.md`, `checks.yaml`, 10 eval cases); `schemas/skill-metadata.v1.json`, `rubric.v1.json`, `eval-case.v1.json`; `plugins/truminds/tests/test_structure.py` | Delivered | — |
| 3 | Is skill chaining defined? | SDD-02; `plugins/truminds/workflows/*.workflow.yaml`; `tsl/src/tsl/orchestrator/`; `tsl/tests/test_e2e.py`, `test_e2e_paths.py`, `test_state_lock.py` | Delivered | — |
| 4 | Is the harness split (code vs AI) defined? | SDD-03; `tsl/src/tsl/harness/`; `plugins/truminds/agents/reviewer.md`; `schemas/review.v1.json`; `tsl/tests/test_decide_table.py`, `test_citations.py` | Delivered | Thresholds stay proposals until pilot data (OQ-09, OQ-12): Puneet |
| 5 | Is analytics transfer to the cloud defined? | SDD-08 §4–§7; SDD-11; ADR 0002; `schemas/events/`; `tsl/src/tsl/telemetry/`; `services/insights/app/{ingest,otel,projector}/`; `services/insights/tests/test_events.py`, `test_otel.py`, `test_projection.py`; `tsl/tests/test_outbox.py` | Delivered | OTel allowlist confirmed by spike S-10 on a seat: Shubham Bansal |
| 6 | Is the cloud DB schema defined? | SDD-08 §10–§11; `services/insights/alembic/versions/0001`–`0005`; `services/insights/seed/generate.py`; `services/insights/app/jobs/retention.py`; `test_jobs.py`, `test_seed.py` | Delivered | Final retention value (OQ-08; default RD-4 is config): Puneet |
| 7 | Where are the Claude Code hooks defined? | SDD-05 §5–§6; `plugins/truminds/hooks/hooks.json`; `plugins/truminds/bin/tsl-hook`; `plugins/truminds/policy/policy.yaml`; `tsl/src/tsl/hooks/`; `tsl/tests/hooks/test_hook_contract.py`; `plugins/truminds/tests/test_tsl_hook.py`; `spikes/` | Needs Puneet / external | Spikes S-01 to S-09 run on a company test seat and recorded in SDD-05 §8.1: Shubham Bansal, with a test seat from the Claude org admin (TBD by Puneet) |
| 8 | Is the PRD complete, with features per phase? | PLN-01 §2 (phase table, feature-to-phase), §3 (gate criteria) | Needs Puneet / external | Puneet confirms scope (Q16, Q17) and the gate criteria (PLN-OI-06); then PRD §6 is updated from PLN-01 |
| 9 | Which features need feature documents? | SDD-01 to SDD-13 (F1–F14, see §2.1) | Delivered (draft for owner review) | Validators named in §10 review each SDD |
| 10 | Web UI data, features and API | SDD-09 §5; `services/insights/openapi/openapi.json`; `services/insights/app/api/v1/read/`; `portal/src/api/`; `services/insights/tests/test_read_api.py`; `portal/src/api/contract.test.ts` | Delivered | — |
| 11 | UX design of the Web UI | Doc 4; `docs/ux/prototype/`; SDD-09 §3.6, §8, §9; empty, loading and error states in `portal/src/components/States.tsx`, `portal/src/app/StatusBanner.tsx`; brand tokens checked by `portal/scripts/check-tokens.mjs` | Needs Puneet / external | Puneet signs off the prototype; brand colours and logo (OQ-13) from Brand; Figma Dev or Full seat if Figma is wanted; admin screens are not drawn because SDD-09 and SDD-13 each point to the other (OI-13-04): Puneet names the owner (UI owner TBD by Puneet) |
| 12 | Guardrails | SEC-01 §6, §7, §11 (guardrail catalogue with enforcement point and test); `plugins/truminds/policy/policy.yaml`; `managed-settings/managed-settings.template.json`; `tsl/src/tsl/harness/gates.py` (H4, H7), `detectors.py`, `rules/`; `plugins/truminds/tests/test_denylist.py` | Delivered (draft for owner review) | Security reviewer reviews SEC-01 (Q28). Code gap: SC-INJ-01 (§9) |
| 13 | Restrictions and constraints document | Doc 6 (`docs/product/06-constraints.md`) | Needs Puneet / external | Legal reviews consent and data-processing wording (OQ-06); Claude admin and Puneet answer data residency (OQ-03); IT confirms A-02 (managed settings enforceable) and A-03 (client repos on GitHub); Puneet signs off Doc 6 |
| 14 | Tech stack | Doc 3 §11; ADR 0001; versions pinned in `tsl/uv.lock`, `services/insights/uv.lock`, `portal/package-lock.json`, `examples/sample-system/package-lock.json`; images pinned by digest (`deploy/tests/test_deploy.py`); scanner choice SEC-01 §7.1 | Delivered (draft for owner review) | Hosting stays open; tracked under Q31 |
| 15 | Works with other AI models or tools? | ADR 0005 (built in this audit) | Delivered (draft for owner review) | Puneet accepts or rejects ADR 0005 |
| 16 | What is "done" for Release 1? | PLN-01 §3.3 (R1-1 to R1-11 proposal); `docs/planning/release-1-gate-checklist.md` (built in this audit) | Needs Puneet / external | Puneet picks the pilot system(s) (OQ-04) and accepts the success criteria (PLN-OI-06) |
| 17 | First-build scope and priority | PLN-01 §2.3 (priority 1–17, Phase 1 = 10 skills) | Needs Puneet / external | Puneet confirms the priority order and Release-1 pods (PLN-OI-07, OQ-16) and the 10-vs-8 count (PLN-OI-03) |
| 18 | Which open questions block building? | Tracker §6 Q18; PLN-01 §2.4; GOV-01 §6 | Delivered | — |
| 19 | Backlog of tickets | PLN-01 §7 (17 epics, 88 stories); `docs/planning/backlog.csv` and `scripts/build_backlog.py` (built in this audit; `make docs-check` keeps them in sync) | Delivered (draft for owner review) | Jira epics and tickets are created only after Puneet's go-ahead (PLN-OI-09); nothing was written to Jira |
| 20 | Contracts between team members | `schemas/` (every contract with valid and invalid fixtures); `schemas/tests/test_schemas.py`; PLN-01 §5 | Delivered | — |
| 21 | Build order and dependencies | PLN-01 §4 (dependency graph, lanes), §7 epic graph | Delivered (draft for owner review) | — |
| 22 | Repositories and branching | DEV-01 §2; GOV-01 §5; `.github/CODEOWNERS`; `.github/pull_request_template.md`; `.github/workflows/` | Needs Puneet / external | Puneet names the GitHub org (OQ-10) and the CODEOWNERS team handles; decides where the `tsl-ci-verify` action lives and trunk vs tagged `main` (DEV-01 §9) |
| 23 | Developer setup | DEV-01 §3; `Makefile`; `.devcontainer/` and `services/insights/compose.dev.yml` (built in this audit) | Delivered (draft for owner review) | Development Entra app registrations: Entra admin (TBD by Puneet); dev container not yet built on a team laptop |
| 24 | Sample brownfield system | ADR 0004; TST-01 §4; `examples/sample-system/` (React, Node.js, PostgreSQL, seeded tickets and defects, tests, canary) | Delivered | Second system in another language (TST-01 §11): Puneet picks the language |
| 25 | Test strategy and test cases | TST-01 §2, §5 (test case catalogue); component suites under `tsl/tests/`, `schemas/tests/`, `plugins/truminds/tests/`, `services/insights/tests/`, `portal/src/**/*.test.ts(x)`, `portal/e2e/`, `examples/sample-system/**/test/`, `deploy/tests/`, `ops/monitoring/tests/` | Delivered | — |
| 26 | How AI parts are tested | SDD-01 §10; TST-01 §3.1–§3.2; eval sets in every SDLC skill's `evals/`; reviewer labelled set `harness-evals/` (built in this audit) | Needs Puneet / external | Puneet confirms the 90% eval pass threshold and reviewer targets (PLN-OI-11) |
| 27 | How we measure harness accuracy | SDD-03 §16; TST-01 §3.3 (audit procedure); `tsl harness eval` (`tsl/src/tsl/harness/accuracy.py`); `harness-evals/` | Needs Puneet / external | Puneet sets the audit rate (OQ-11), who audits, and the miss trigger; Japman Singh and Yash Khorwal own the procedure |
| 28 | Independent security review | SEC-01 §12 (review plan, scope, checklist) | Needs Puneet / external | Puneet names a security reviewer; the reviewer reviews SEC-01, the policy file and key handling before any client code is touched |
| 29 | Consent wording and legal review | LEG-01 (template, consent record, engagement checklist, questions for legal); `schemas/consent-record.v1.json` | Needs Puneet / external | Puneet names a legal contact; Legal reviews and approves LEG-01 (OQ-06) |
| 30 | Admin roles and access | Doc 2 §2; SDD-13 §5; SDD-07 §3 | Needs Puneet / external | Puneet names admins, tech leads and skill owners for Release 1 (OI-13-01) |
| 31 | Hosting, deploy, backup, cost | OPS-01 (options, single-VM baseline H1, backup and restore, cost drivers); `deploy/` with `deploy/tests/test_deploy.py` | Needs Puneet / external | Puneet chooses the hosting (OQ-02); then a cost estimate with numbers |
| 32 | Support and rollout of updates | OPS-03; `.github/workflows/release.yml`; `.github/ISSUE_TEMPLATE/support.yml`, `bug.yml` | Delivered (draft for owner review) | — |
| 33 | Monitoring of the cloud service | OPS-02; `ops/monitoring/` (alerts, recording rules, dashboards DSH-1 to DSH-6, synthetic probe); `ops/monitoring/tests/test_monitoring.py`; `services/insights/app/obs/` | Delivered (draft for owner review) | Monitoring tooling host follows the hosting choice (Q31) |
| 34 | Onboarding and training | SDD-13 §3–§4; `docs/training/` (built in this audit: checklist, five persona outlines, facilitator guide) | Delivered (draft for owner review) | First hands-on session to be run once the first skill works on a seat (SDD-13 §12) |
| 35 | Adoption and value measures | PRD §5; SDD-09 §7; SDD-08 §10.4 (metric catalogue); `services/insights/alembic/versions/0002_views.py`; `services/insights/app/api/v1/read/insights.py` | Needs Puneet / external | Puneet decides whether pilot teams record a baseline (R1-10) and sets targets after it (D-09) |
| 36 | Failure modes in practice | OPS-04 (who acts, what they do, alert runbook AL-01 to AL-26) | Delivered (draft for owner review) | — |
| 37 | Claude Code features behave as assumed? | SDD-05 §2 (verified facts, unverified list); `spikes/` (plugin and runbooks S-01 to S-15) | Needs Puneet / external | Shubham Bansal runs the spikes on a company test seat; Claude org admin applies managed settings for S-01, S-06, S-11, S-12 |
| 38 | Seat usage limits | SDD-13 §8 (what is known, behaviour at a limit, spike S-11 plan); `spikes/README.md` S-11 | Needs Puneet / external | Claude org admin gives the plan's limits; one measured end-to-end run on the sample system (PLN-OI-10) |
| 39 | Source of truth and change approval | ADR 0003; GOV-01 §2–§5; `.github/workflows/ci-docs.yml` | Needs Puneet / external | Puneet names the co-approver (OQ-01) |
| 40 | Decision log process | GOV-01 §7 (ADR process), §8 (decision log); `docs/adr/0000-template.md`; `.github/ISSUE_TEMPLATE/decision.yml` | Delivered (draft for owner review) | — |

### 2.1 Q9 feature specs F1–F14

| F | Feature spec | Delivered by | Status |
| --- | --- | --- | --- |
| F1 | Skill authoring standard | [SDD-01](../design/SDD-01-skill-authoring.md) | Delivered (draft for owner review) |
| F2 | Orchestrator and chaining | [SDD-02](../design/SDD-02-workflow-orchestration.md) | Delivered (draft for owner review) |
| F3 | Harness checks catalogue and reviewer prompt | [SDD-03](../design/SDD-03-harness.md) §5, §7 | Delivered (draft for owner review) |
| F4 | Context pack and extractors | [SDD-06](../design/SDD-06-context-pack.md) | Delivered (draft for owner review) |
| F5 | `tsl` CLI full behaviour | [SDD-04](../design/SDD-04-tsl-cli.md) | Delivered (draft for owner review) |
| F6 | Hooks and policy | [SDD-05](../design/SDD-05-claude-code-integration.md) §5–§6 | Delivered (draft for owner review) |
| F7 | Signing, login and key management | [SDD-07](../design/SDD-07-identity-signing.md) | Delivered (draft for owner review) |
| F8 | Events, telemetry API and ingestion | [SDD-08](../design/SDD-08-telemetry-insights.md) | Delivered (draft for owner review) |
| F9 | CI verify action | [SDD-03](../design/SDD-03-harness.md) §13 | Delivered (draft for owner review) |
| F10 | Portal read API and screen data contracts | [SDD-09](../design/SDD-09-web-portal.md) | Delivered (draft for owner review) |
| F11 | Pod definition format and pod pages | [SDD-10](../design/SDD-10-pods.md) | Delivered (draft for owner review) |
| F12 | Improvement loop | [SDD-11](../design/SDD-11-improvement-loop.md) | Delivered (draft for owner review) |
| F13 | Onboarding and admin | [SDD-13](../design/SDD-13-onboarding-admin.md) | Delivered (draft for owner review) |
| F14 | Companion repo lifecycle | [SDD-12](../design/SDD-12-companion-repo.md) | Delivered (draft for owner review) |

## 3. Tracker §8 "What I need from you"

| # | Item | Repo record | Status | What is needed, from whom |
| --- | --- | --- | --- | --- |
| 8.1 | Portal technology (OQ-15) | ADR 0001; PRD §8 lists OQ-15 as resolved by ADR 0001 | Delivered | — |
| 8.2 | Pilot system(s) and success (OQ-04) | PLN-01 §3.3 proposal; `release-1-gate-checklist.md` | Needs Puneet / external | Puneet: pilot teams, systems and domains |
| 8.3 | Release-1 skills and pods in priority order (OQ-16) | PLN-01 §2.3; SDD-10 §4; `pods/` | Needs Puneet / external | Puneet: confirm order and pod list (PLN-OI-07) |
| 8.4 | GitHub org (OQ-10) | Placeholders `<companion-org>` in SDD-12 §5.1 and `tsl/src/tsl/_org.toml` | Needs Puneet / external | Puneet: the org for Truminds and companion repos |
| 8.5 | Company SSO provider | ADR 0002 (Microsoft Entra ID); SDD-07 | Delivered | Entra app registrations still need the Entra admin (see 8.13) |
| 8.6 | Thresholds: 90% eval pass, 1-in-10 audits, default limits (OQ-11, OQ-12) | SDD-01 §10, SDD-03 §10.2, §16; Doc 3 §6; config defaults in `tsl.yaml` | Needs Puneet / external | Puneet: confirm or change (PLN-OI-11) |
| 8.7 | Hosting cloud (OQ-02) | OPS-01 §4 options | Needs Puneet / external | Puneet: choose (PLN-OI-05 proposes moving it to G1) |
| 8.8 | Data residency (OQ-03) | Doc 6 C-07; LEG-01 §15 | Needs Puneet / external | Claude org admin and Legal: plan terms; Puneet decides |
| 8.9 | Telemetry retention (OQ-08) | SDD-08 §8.2; default RD-4 as config (`services/insights/app/config.py`) | Needs Puneet / external | Puneet: retention period |
| 8.10 | Named admins, tech leads, skill owners (Q30) | SDD-13 §5.1 (roles with TBD names) | Needs Puneet / external | Puneet: names and backups |
| 8.11 | Measure a baseline (Q35) | PRD §5 baseline rule; R1-10 | Needs Puneet / external | Puneet: yes or no, before pilots start |
| 8.12 | Security reviewer (Q28) | SEC-01 §12 | Needs Puneet / external | Puneet: name the reviewer |
| 8.13 | Legal for consent and data processing (Q29) | LEG-01 | Needs Puneet / external | Puneet: name the legal contact; Legal reviews |
| 8.14 | Claude admin / IT for managed settings, seat limits, plugin enforcement (Q37, Q38) | `managed-settings/managed-settings.template.json`; SDD-13 §6, §8 | Needs Puneet / external | Claude org admin and IT; also the Entra admin for app registrations (SDD-07 §3.1) |
| 8.15 | Brand colours and logo (Q11) | SDD-09 §9 swap procedure; placeholder `portal/public/brand/` | Needs Puneet / external | Brand owner: official assets (OQ-13) |
| 8.16 | Sign-off on the UX prototype (Q11) and Doc 6 (Q13) | `docs/ux/prototype/`; Doc 6 | Needs Puneet / external | Puneet: sign-off |

## 4. Tracker §9 "What I can take care of"

| Order | Work | Delivered by | Status | Note |
| --- | --- | --- | --- | --- |
| 1 | Verify Claude Code assumptions; spike plugin | SDD-05 §2 (findings); `spikes/` (plugin, settings, OTel collector, runbooks with result tables) | Delivered (draft for owner review) | Running it needs a seat (Q37) |
| 2 | All schema files with valid and invalid samples | `schemas/`, `schemas/fixtures/`, `schemas/tests/` | Delivered | — |
| 3 | Feature specs F1–F14 | SDD-01 to SDD-13 | Delivered (draft for owner review) | — |
| 4 | Skill template and reference skill with rubric and 10 evals | SDD-01 §3, §13; `plugins/truminds/skills/requirement-review/` | Delivered | — |
| 5 | Sample brownfield system | `examples/sample-system/` | Delivered | Second language waits for a language choice (Q24) |
| 6 | Code foundations: `tsl`, `decide()` golden tests, events service with migrations | `tsl/`; `tsl/tests/test_decide_table.py`; `services/insights/` | Delivered | — |
| 7 | Portal read API (OpenAPI) and database v1.1 | `services/insights/openapi/openapi.json`; `alembic/versions/0002`–`0005`; `portal/` | Delivered | — |
| 8 | Phase table, gate criteria, OQ triage, build-order diagram | PLN-01 §2–§4 | Delivered (draft for owner review) | PRD §6 is updated after Puneet's scope decision (Q8) |
| 9 | Backlog with acceptance criteria and owners | PLN-01 §7; `docs/planning/backlog.csv` (built in this audit) | Delivered (draft for owner review) | Jira only after Puneet's go-ahead |
| 10 | Runbooks and guides: dev setup, support and rollout, monitoring, failure modes, onboarding, decision-record template | DEV-01, `.devcontainer/`; OPS-03; OPS-02; OPS-04; `docs/training/`; `docs/adr/0000-template.md` | Delivered (draft for owner review) | `.devcontainer/` and `docs/training/` built in this audit |
| 11 | Drafts for others: consent template, security review pack, hosting design | LEG-01; SEC-01 §12; OPS-01 | Needs Puneet / external | Legal, a security reviewer and the hosting choice (Q28, Q29, Q31) |
| 12 | UX completion: empty, error and admin screens; brand swap | Empty and error states in `portal/src/components/States.tsx`; brand swap procedure SDD-09 §9 | Needs Puneet / external | Brand assets (OQ-13); prototype sign-off; admin-screen owner (OI-13-04) |
| C1 | Cannot: run Claude Code desktop on a company seat | `spikes/README.md` | Needs Puneet / external | Shubham Bansal on a test seat |
| C2 | Cannot: make scope and hosting decisions | PLN-01 §9 | Needs Puneet / external | Puneet |
| C3 | Cannot: give legal or security sign-off | LEG-01, SEC-01 §12 | Needs Puneet / external | Legal; security reviewer |
| C4 | Cannot: see seat limits | SDD-13 §8 | Needs Puneet / external | Claude org admin |
| C5 | Cannot: edit Figma beyond the View seat | Doc 4 Figma link | Delivered (draft for owner review) | Not blocking delivery: the prototype in `docs/ux/prototype/` and the portal code hold the design; a Figma Dev or Full seat is needed only if Puneet wants Figma completed |

## 5. Tracker §10 "Proposed design document set"

| Item | Path | Status |
| --- | --- | --- |
| Decision: where documents live | Superseded by [ADR 0003](../adr/0003-repo-is-source-of-truth.md) (repo is the source of truth) | Delivered |
| Decision: portal technology | [ADR 0001](../adr/0001-portal-custom-react-on-fastapi.md) | Delivered |
| Decision: identity provider | [ADR 0002](../adr/0002-identity-microsoft-entra-id.md) | Delivered |
| Decision: sample system | [ADR 0004](../adr/0004-sample-system-react-node.md) (Proposed, tentative) | Delivered (draft for owner review) |
| Doc 1 PRD | [product/01-prd.md](../product/01-prd.md) | Delivered (draft for owner review) |
| Doc 2 Personas and Stories | [product/02-personas-and-stories.md](../product/02-personas-and-stories.md) | Delivered (draft for owner review) |
| Doc 3 Architecture | [architecture/03-architecture.md](../architecture/03-architecture.md) | Delivered (draft for owner review) |
| Doc 4 Design and UX | [ux/04-design-and-ux.md](../ux/04-design-and-ux.md) | Delivered (draft for owner review) |
| Doc 5 API and Rules | [architecture/05-api-and-rules.md](../architecture/05-api-and-rules.md) | Delivered (draft for owner review) |
| Doc 6 Constraints | [product/06-constraints.md](../product/06-constraints.md) | Delivered (draft for owner review) |
| SDD-01 to SDD-13 (13 documents) | `docs/design/SDD-01` … `SDD-13` (see §2.1) | Delivered (draft for owner review), each of the 13 |
| SEC-01 | [security/SEC-01-threat-model.md](../security/SEC-01-threat-model.md) | Delivered (draft for owner review) |
| TST-01 | [testing/TST-01-master-test-plan.md](../testing/TST-01-master-test-plan.md) | Delivered (draft for owner review) |
| DEV-01 | [development/DEV-01-developer-guide.md](../development/DEV-01-developer-guide.md) | Delivered (draft for owner review) |
| OPS-01 | [operations/OPS-01-deployment-hosting.md](../operations/OPS-01-deployment-hosting.md) | Delivered (draft for owner review) |
| OPS-02 | [operations/OPS-02-monitoring-alerting.md](../operations/OPS-02-monitoring-alerting.md) | Delivered (draft for owner review) |
| OPS-03 | [operations/OPS-03-release-rollout-support.md](../operations/OPS-03-release-rollout-support.md) | Delivered (draft for owner review) |
| OPS-04 | [operations/OPS-04-failure-runbook.md](../operations/OPS-04-failure-runbook.md) | Delivered (draft for owner review) |
| PLN-01 | [planning/PLN-01-delivery-plan.md](PLN-01-delivery-plan.md) | Delivered (draft for owner review) |
| GOV-01 | [governance/GOV-01-adr-and-change-process.md](../governance/GOV-01-adr-and-change-process.md) | Delivered (draft for owner review) |
| LEG-01 | [legal/LEG-01-client-consent-template.md](../legal/LEG-01-client-consent-template.md) | Delivered (draft for owner review); legal review is Q29 |
| Code: schema files (Q20) | `schemas/` | Delivered |
| Code: reference skill (Q2) | `plugins/truminds/skills/requirement-review/` | Delivered |
| Code: sample system (Q24) | `examples/sample-system/` | Delivered |
| Code: `tsl` and service (Q4–Q6) | `tsl/`, `services/insights/` (full implementations, not skeletons) | Delivered |
| Code: Claude Code integration spike (Q37) | `spikes/` | Delivered |

The SDD row counts as 13 items and the four decisions, six top-level documents, ten cross-cutting documents and five code deliverables as one each (38 in total).

## 6. Tracker §11 "Build plan per question"

| Q | Promised output | Lives in (repo) | Status | Note |
| --- | --- | --- | --- | --- |
| 1 | Re-assessment at the end | This document | Delivered (draft for owner review) | — |
| 2 | SKILL.md template, rubric format, eval format, `requirement-review` with 10 evals | SDD-01; `plugins/truminds/skills/requirement-review/` | Delivered | — |
| 3 | Chaining rules, orchestrator, parallel and resume behaviour | SDD-02; `tsl/src/tsl/orchestrator/` | Delivered | — |
| 4 | Checks catalogue, reviewer prompt and findings schema, citation matcher, `decide()` with golden tests | SDD-03; `tsl/src/tsl/harness/`; `plugins/truminds/agents/reviewer.md`; `schemas/review.v1.json`; `tsl/tests/test_decide_table.py` | Delivered | — |
| 5 | Event schemas, ingestion, OTel handling, weekly report spec | SDD-08, SDD-11; `schemas/events/`; `services/insights/` | Delivered | — |
| 6 | Schema v1.1: pods, indexes, views, retention job, seed, migrations | SDD-08 §10–§11; `services/insights/alembic/`, `seed/`, `app/jobs/retention.py` | Delivered | Retention value is config until OQ-08 |
| 7 | `hooks.json`, policy file, verified behaviour, spike plugin | SDD-05; `plugins/truminds/hooks/hooks.json`; `plugins/truminds/policy/policy.yaml`; `spikes/` | Delivered | Running on a seat: Q37 |
| 8 | Phase table and gate criteria | PLN-01 §2–§3 | Delivered (draft for owner review) | PRD §6 edit follows the scope decision |
| 9 | All 13 SDDs | `docs/design/` | Delivered (draft for owner review) | — |
| 10 | Read API, permission rules, data contract per screen | SDD-09 §4–§5; `services/insights/openapi/openapi.json`; `services/insights/app/read/access.py` | Delivered | — |
| 11 | Empty, error and admin screens; brand swap | `portal/src/components/States.tsx`; SDD-09 §9 | Needs Puneet / external | Brand assets and sign-off (Puneet, Brand); admin-screen owner (OI-13-04) |
| 12 | Guardrail catalogue with enforcement point and test each; injection handling; detector choice | SEC-01 §6, §7, §11 | Delivered (draft for owner review) | SC-INJ-01 code gap in §9 |
| 13 | Doc 6 updates once items are confirmed | Doc 6 | Needs Puneet / external | Legal (OQ-06) and residency (OQ-03) first |
| 14 | Recommendation and pinned versions | Doc 3 §11; ADR 0001; lockfiles | Delivered (draft for owner review) | — |
| 15 | Portability adapter design | ADR 0005 (built in this audit) | Delivered (draft for owner review) | — |
| 16 | Release-1 success proposal | PLN-01 §3.3; `release-1-gate-checklist.md` (built in this audit) | Delivered (draft for owner review) | Decision: Q16 |
| 17 | Priority proposal | PLN-01 §2.3 | Delivered (draft for owner review) | Decision: Q17 |
| 18 | Open-question triage | Tracker §6; PLN-01 §2.4 | Delivered | — |
| 19 | Epics and tickets with acceptance criteria | PLN-01 §7; `backlog.csv` (built in this audit) | Delivered (draft for owner review) | Jira after go-ahead |
| 20 | JSON Schema files with valid and invalid samples | `schemas/` | Delivered | — |
| 21 | Build-order dependency diagram | PLN-01 §4.1 | Delivered (draft for owner review) | — |
| 22 | Repo layout, branching, release tags, code owners | DEV-01 §2; `.github/CODEOWNERS`; OPS-03 §2 | Delivered (draft for owner review) | Final org and team handles: Q22 |
| 23 | Setup guide and dev container | DEV-01 §3; `.devcontainer/` (built in this audit) | Delivered (draft for owner review) | — |
| 24 | Sample brownfield systems | `examples/sample-system/` | Delivered | Second system: language choice by Puneet |
| 25 | Test cases per module | TST-01 §5; each SDD test plan; component suites | Delivered | — |
| 26 | Eval-case format, skill and reviewer eval sets | SDD-01 §10; TST-01 §3; `plugins/truminds/skills/*/evals/`; `harness-evals/` (built in this audit) | Delivered (draft for owner review) | Threshold confirmation: Q26 |
| 27 | Audit procedure | SDD-03 §16.3; TST-01 §3.3 | Delivered (draft for owner review) | Rate: Q27 |
| 28 | Security review pack and checklist | SEC-01 §12 | Delivered (draft for owner review) | Reviewer: Q28 |
| 29 | Consent template | LEG-01 | Delivered (draft for owner review) | Legal: Q29 |
| 30 | — (names only) | Doc 2 §2; SDD-13 §5 | Needs Puneet / external | Puneet names people |
| 31 | Hosting and deployment design, cost estimate | OPS-01; `deploy/` | Needs Puneet / external | Hosting choice (OQ-02) before a costed estimate |
| 32 | Release and support runbook | OPS-03; `.github/workflows/release.yml` | Delivered (draft for owner review) | — |
| 33 | Monitoring and alert design | OPS-02; `ops/monitoring/` | Delivered | Tests in `ops/monitoring/tests/` |
| 34 | Engineer, author and tech-lead guides; hands-on session | SDD-13 §3–§4; `docs/training/` (built in this audit) | Delivered (draft for owner review) | — |
| 35 | Metric definitions and queries | SDD-08 §10.4; SDD-09 §7; `alembic/versions/0002_views.py` | Delivered | Targets: Puneet (Q35) |
| 36 | Failure-mode runbook | OPS-04 | Delivered (draft for owner review) | — |
| 37 | Verification findings and spike | SDD-05 §2, §8; `spikes/` | Delivered | Running on a seat: Q37 |
| 38 | — (admin data) | SDD-13 §8 | Needs Puneet / external | Claude org admin |
| 39 | — (co-approver) | GOV-01 | Needs Puneet / external | Puneet (OQ-01) |
| 40 | ADR template and change process | GOV-01; `docs/adr/0000-template.md` | Delivered (draft for owner review) | — |

## 7. PRD requirements to design and code

Test names are `file::test`. Paths are relative to the repo root.

| Req | Design (SDD section) | Code | Tests |
| --- | --- | --- | --- |
| FR-REG-01 | SDD-01 §2–§4 | `plugins/truminds/skills/*/skill.yaml`; `schemas/skill-metadata.v1.json` | `plugins/truminds/tests/test_structure.py::test_skill_folder_files`; `tsl/tests/test_commands.py::test_validate` |
| FR-REG-02 | SDD-01 §4, §10; SDD-04 §6.5 | `tsl/src/tsl/services/validate.py`; `.github/workflows/ci-plugin.yml` | `tsl/tests/test_commands.py::test_validate`; `test_structure.py::test_every_artifact_input_schema_is_produced_by_some_skill` |
| FR-REG-03 | SDD-01 §7; SDD-09 §6 | `services/insights/app/api/v1/read/catalogue.py` | `services/insights/tests/test_read_api.py::test_capability_map_shared_hides_pilot` |
| FR-AGT-01 | SDD-01 §11.1 | `agent` field in each `skill.yaml` | `test_structure.py::test_release1_catalogue_is_complete` |
| FR-AGT-02 | SDD-01 §11.1; PLN-01 ST-05.5 | Allowed skills per agent via `skill.yaml`; role packs not yet designed (§9) | `test_structure.py::test_release1_catalogue_is_complete` |
| FR-WFL-01 | SDD-02 §3 | `plugins/truminds/workflows/*.workflow.yaml`; `schemas/workflow.v1.json` | `test_structure.py::test_workflow_skill_refs_resolve`, `test_brownfield_change_matches_sdd02_exactly` |
| FR-WFL-02 | SDD-02 §3.5 | `tsl/src/tsl/services/validate.py` | `tsl/tests/test_commands.py::test_validate_lock_writes_workflow_lock` |
| FR-WFL-03 | SDD-02 §4; PLN-01 §2.3 (Doc 3 names, PLN-OI-02, RD-6) | `plugins/truminds/workflows/` (`brownfield-change`, `defect-fix`, `greenfield-feature`, `ux-review`, `estimate`) | `test_structure.py::test_doc3_release1_workflows_exist`; `services/insights/tests/test_jobs.py::test_rd6_workflow_name_choice` |
| FR-WFL-04 | SDD-01 §12 | `plugins/truminds/skills/` (17 SDLC skills) | `test_structure.py::test_release1_catalogue_is_complete` |
| FR-RUN-01 | SDD-02 §5; SDD-04 §6.7 | `tsl/src/tsl/state/`; `plugins/truminds/skills/run/SKILL.md` | `tsl/tests/test_state_lock.py::test_start_takes_and_pushes_the_lock` |
| FR-RUN-02 | SDD-01 §3.3; SDD-03 §4.8; SDD-05 §5.3 | `tsl/src/tsl/hooks/pre_tool.py`; `tsl/src/tsl/harness/verify.py` | `tsl/tests/test_commands.py::test_verify_inputs_and_artifact`; `tsl/tests/hooks/test_hook_contract.py::test_hook_golden` |
| FR-RUN-03 | SDD-02 §9 | `tsl/src/tsl/approvals/` | `tsl/tests/test_e2e_paths.py::test_needs_input_then_resume`; `tsl/tests/test_e2e.py::test_full_run_gate_story_and_completion` |
| FR-RUN-04 | SDD-02 §9.1; SDD-04 §6.7 | `tsl/src/tsl/state/service.py` | `tsl/tests/test_state_lock.py::test_resume_rules` |
| FR-RUN-05 | SDD-02 §11.1 | `tsl/src/tsl/state/lock.py` | `tsl/tests/test_state_lock.py::test_second_start_is_locked` |
| FR-RUN-06 | SDD-04 §6.12; SDD-12 §4.2 | `tsl/src/tsl/services/pr.py` | `tsl/tests/test_e2e_code.py::test_code_step_pr_and_ci_verify` |
| FR-HRN-01 | SDD-03 §4–§6 | `tsl/src/tsl/harness/gates.py`, `verify.py` | `tsl/tests/test_e2e_paths.py::test_retry_from_post_write_block_and_feedback`; `harness-evals/` |
| FR-HRN-02 | SDD-03 §7; SDD-05 §4.3–§4.4 | `tsl/src/tsl/review/service.py`; `plugins/truminds/agents/reviewer.md`; `plugins/truminds/skills/review/` | `tsl/tests/test_commands.py::test_review_errors`; `test_structure.py::test_reviewer_agent_is_read_only_and_review_skill_forks` |
| FR-HRN-03 | SDD-03 §8–§12 | `tsl/src/tsl/harness/citations.py`, `decide.py`, `decide_service.py` | `tsl/tests/test_citations.py`; `tsl/tests/test_decide_table.py` |
| FR-HRN-04 | SDD-03 §4.5, §5.5 | `tsl/src/tsl/harness/verifier.py` | `tsl/tests/test_docker.py`; `tsl/tests/test_e2e_code.py::test_h3_failure_retries_in_fix_loop` |
| FR-HRN-05 | SDD-03 §13 | `tsl/src/tsl/ci/verify.py`; `.github/workflows/tsl-ci-verify.yml` | `tsl/tests/test_e2e_code.py::test_code_step_pr_and_ci_verify`, `test_ci_verify_no_marker` |
| FR-CTX-01 | SDD-06 §5–§6 | `tsl/src/tsl/context/build.py`, `extractors.py` | `tsl/tests/test_commands.py::test_context_commands` |
| FR-CTX-02 | SDD-06 §7 | `tsl/src/tsl/context/freshness.py` | `tsl/tests/test_commands.py::test_context_freshness_and_tamper` |
| FR-CTX-03 | SDD-03 §10.3 | `tsl/src/tsl/harness/decide.py` | `tsl/tests/test_decide_table.py::test_cap_pack_stale_limits_medium` |
| FR-DOM-01 | SDD-01 §1.3 (domain packs optional); PLN-01 ST-05.7 | Not built: blocked by OQ-04 and OQ-05 (§9) | — |
| FR-TEL-01 | SDD-04 §8; SDD-08 §4 | `tsl/src/tsl/telemetry/outbox.py`, `emit.py`; `services/insights/app/api/v1/events.py` | `tsl/tests/test_outbox.py`; `services/insights/tests/test_events.py` |
| FR-TEL-02 | SDD-08 §5, §6.1 | `services/insights/app/otel/`; `services/insights/app/api/v1/webhooks_github.py` | `services/insights/tests/test_otel.py`; `test_webhook.py` |
| FR-TEL-03 | SDD-08 §4.4; SEC-01 §4.3 | `services/insights/app/ingest/denylist.py`, `schemas.py` | `services/insights/tests/test_events.py::test_client_name_denylist`, `test_no_user_column_from_body` |
| FR-POR-01 | SDD-09 §3–§5 | `portal/src/screens/`; `services/insights/app/api/v1/read/` | `portal/src/screens/screens.test.tsx`; `portal/e2e/navigation.spec.ts`; `services/insights/tests/test_read_api.py` |
| FR-POR-02 | SDD-09 §6 | `portal/src/screens/CapabilityMapShare.tsx`; `portal/src/components/CapabilityMapTable.tsx` | `services/insights/tests/test_read_api.py::test_capability_map_shared_hides_pilot` |
| FR-IMP-01 | SDD-11 §4 | `services/insights/app/jobs/improvement_report.py` | `services/insights/tests/test_improvement.py::test_report_job_opens_flag` |
| FR-IMP-02 | SDD-11 §5–§6; SDD-04 §6.16–§6.17 | `tsl/src/tsl/improve/`, `tsl/src/tsl/evals/`; `plugins/truminds/skills/{improve,eval}/` | `tsl/tests/test_improve.py`; `tsl/tests/test_commands.py::test_eval_plan_run_check` |
| FR-ADM-01 | SDD-05 §6.2; SDD-13 §6 | `managed-settings/managed-settings.template.json` | Spike S-01 runbook in `spikes/README.md` (needs a seat) |
| FR-ADM-02 | SDD-07 §4–§5 | `tsl/src/tsl/identity/entra.py`, `keys.py`; `services/insights/app/api/v1/keys.py` | `tsl/tests/test_identity.py::test_login_registers_key_and_writes_device_code_to_stderr`; `services/insights/tests/test_keys.py` |
| FR-ADM-03 | SDD-12 §7; LEG-01 §13 | `tsl/src/tsl/services/init.py`; `services/insights/app/api/v1/admin.py` | `tsl/tests/test_commands.py::test_init_needs_consent_and_registration`; `services/insights/tests/test_admin.py::test_consent_and_system_record` |
| FR-ADM-04 | SDD-07 §3; SDD-09 §5.2–§5.4 | `services/insights/app/auth/scope.py`; `services/insights/app/read/access.py` | `services/insights/tests/test_read_api.py::test_read_role_privileges`; `test_admin.py::test_ceiling_and_scope_checks` |

## 8. User stories to design and code

| Story | Design (SDD section) | Code | Tests |
| --- | --- | --- | --- |
| US-01 Run a brownfield change to a PR | SDD-02 §4–§7; SDD-04 §6.7, §6.12 | `tsl/src/tsl/state/`, `orchestrator/`, `services/pr.py` | `tsl/tests/test_state_lock.py::test_start_takes_and_pushes_the_lock`, `test_start_without_engineer_grant`; `tsl/tests/test_e2e_code.py::test_code_step_pr_and_ci_verify` |
| US-02 Harness result after every skill | SDD-03 §3–§12 | `tsl/src/tsl/harness/` | `tsl/tests/test_e2e_paths.py`; `tsl/tests/test_decide_table.py` |
| US-03 Pause for open questions and resume | SDD-02 §9.1 | `tsl/src/tsl/approvals/questions_md.py`; `tsl/src/tsl/state/service.py` | `tsl/tests/test_e2e_paths.py::test_needs_input_then_resume` |
| US-04 Record who decided | SDD-02 §9.1; Doc 4 §3 | `tsl/src/tsl/approvals/questions_md.py` | `tsl/tests/test_e2e_paths.py::test_needs_input_then_resume`; `schemas/fixtures/open-questions.v1/` |
| US-05 Review a PR with its evidence | SDD-03 §13; SDD-04 §6.12; SDD-08 §6.1 | `tsl/src/tsl/services/pr.py`, `ci/verify.py`; `services/insights/app/api/v1/webhooks_github.py` | `tsl/tests/test_e2e_code.py`; `services/insights/tests/test_webhook.py` |
| US-06 Onboard an existing system | SDD-06 §6–§7; SDD-12 §5 | `tsl/src/tsl/context/`; `tsl/src/tsl/services/init.py` | `tsl/tests/test_commands.py::test_context_commands`, `test_context_lint_and_sign_rules`, `test_context_freshness_and_tamper` |
| US-07 Approve a design gate | SDD-02 §9.2; SDD-07 §6.4 | `tsl/src/tsl/approvals/approvals_md.py`, `service.py` | `tsl/tests/test_e2e.py::test_full_run_gate_story_and_completion`; `tsl/tests/test_commands.py::test_self_approval_refused` |
| US-08 Start a greenfield project | SDD-02 §3 (workflow files); PLN-01 §2.3 (`greenfield-feature`, PLN-OI-02) | `plugins/truminds/workflows/greenfield-feature.workflow.yaml`; `plugins/truminds/skills/design/` | `test_structure.py::test_doc3_release1_workflows_exist`; `plugins/truminds/skills/design/evals/` |
| US-09 Plan and automate tests | SDD-03 §5.4 | `plugins/truminds/skills/test-plan/`, `test-automation/` (`checks.yaml`) | Their `evals/cases/`; `test_structure.py::test_eval_cases_and_every_referenced_file_exist` |
| US-10 Pipelines and deployment failures | SDD-03 §5.4 | `plugins/truminds/skills/pipeline-review/`, `deployment-failure-analysis/`; workflows `pipeline-check`, `deploy-failure` | Their `evals/cases/`; `test_structure.py::test_workflow_skill_refs_resolve` |
| US-11 Threat model and secure review | SDD-03 §5.4, §11.1 (row 6; see GAP-08) | `plugins/truminds/skills/threat-model/`, `secure-code-review/`; workflow `security-review` | Their `evals/cases/`; `tsl/tests/test_decide_table.py::test_row6_needs_input_from_blocker_and_question` |
| US-12 UX flow and accessibility review | SDD-03 §5.4; SDD-05 §6.4 (MCP writes need approval) | `plugins/truminds/skills/ux-flow-review/`, `accessibility-review/`; workflow `ux-review` | Their `evals/cases/`; `plugins/truminds/tests/test_structure.py` |
| US-13 Estimate review and status report | SDD-03 §5.4; SDD-09 §4.13–§4.14 | `plugins/truminds/skills/estimate-review/`, `status-report/`; `portal/src/screens/InsightsEngineering.tsx`, `RunDetail.tsx` | Their `evals/cases/`; `services/insights/tests/test_read_api.py::test_run_detail` |
| US-14 Triage a defect | SDD-02 §3; SDD-03 §5.4 | `plugins/truminds/skills/defect-triage/`; workflow `defect-fix` | `plugins/truminds/skills/defect-triage/evals/`; `test_structure.py::test_doc3_release1_workflows_exist` |
| US-15 Publish a skill | SDD-01 §6–§7, §10; SDD-04 §6.5, §6.16 | `tsl/src/tsl/services/validate.py`, `tsl/src/tsl/evals/service.py`; `.github/workflows/ci-plugin.yml` | `tsl/tests/test_commands.py::test_validate`, `test_eval_plan_run_check` |
| US-16 Improve a skill from evidence | SDD-11 §4–§6 | `services/insights/app/jobs/improvement_report.py`; `tsl/src/tsl/improve/` | `services/insights/tests/test_improvement.py`; `tsl/tests/test_improve.py::test_new_case_must_fail_before`, `test_regression_is_refused` |
| US-17 Sales shows the capability map | SDD-09 §6; SDD-10 §6 | `portal/src/screens/CapabilityMapShare.tsx`; `services/insights/app/read/names.py` | `services/insights/tests/test_read_api.py::test_capability_map_shared_hides_pilot`, `test_name_rule` |
| US-18 Admin onboards an engineer and a client | SDD-13 §3, §7; SDD-07 §4–§5; SDD-12 §7 | `tsl/src/tsl/identity/`; `services/insights/app/api/v1/admin.py`; `docs/training/onboarding-checklist.md` | `tsl/tests/test_identity.py::test_login_registers_key_and_writes_device_code_to_stderr`; `tsl/tests/test_commands.py::test_init_needs_consent_and_registration`; `services/insights/tests/test_admin.py` |
| US-19 Engineering lead sees usage and performance | SDD-08 §7, §10.3–§10.4; SDD-09 §4.13, §5.3 | `services/insights/app/projector/`; `services/insights/app/api/v1/read/insights.py`; `portal/src/screens/InsightsEngineering.tsx` | `services/insights/tests/test_read_api.py::test_engineering_tabs`, `test_name_rule`; `test_projection.py::test_full_run_projection` |
| US-20 Work offline | SDD-04 §8; SDD-08 §4.2 | `tsl/src/tsl/telemetry/outbox.py`; `services/insights/app/ingest/service.py` | `tsl/tests/test_outbox.py::test_offline_keeps_events`; `services/insights/tests/test_events.py::test_idempotent_batch` |
| US-21 Two runs on the same ticket are prevented | SDD-02 §11 | `tsl/src/tsl/state/lock.py` | `tsl/tests/test_state_lock.py::test_second_start_is_locked`, `test_unlock_rules` |
| US-22 Pod builder (Phase 3) | SDD-10 §10 (preview only; X-04) | `portal/src/screens/PodBuilder.tsx` (Phase 3 preview screen) | `portal/src/screens/screens.test.tsx` |

## 9. Gaps found that the tracker does not list

These are promised by the SDDs or PLN-01, not by the tracker. None blocks the tracker items above. They are listed so nothing is lost.

| # | Gap | Promised in | Needed from |
| --- | --- | --- | --- |
| GAP-01 | `SC-INJ-01` soft check is not in `tsl`, and `plugins/truminds/policy/injection-markers.yaml` does not exist (the schema `injection-markers.v1` and its fixtures do) | SEC-01 §6.5 | Japman Singh, Yash Khorwal (harness); Shubham Bansal (policy file) |
| GAP-02 | Verifier container profiles and Dockerfiles under `plugins/truminds/verifiers/` do not exist, so H3 has no profile to run on a real seat and `verifier-images.yml` has nothing to build | SDD-03 §5.5; PLN-01 ST-06.2 | Japman Singh, Yash Khorwal; digests need the GitHub org and registry (OQ-10) |
| GAP-03 | 16 of 17 SDLC skills have 3 eval cases each; SDD-01 §10.3 asks for at least 10 and G1-5 for ≥ 90% pass, signed | SDD-01 §10.3; PLN-01 G1-5 | Abhishek Verma, Ekjot Singh (skill owners) |
| GAP-04 | Role packs per agent (FR-AGT-02) are not designed in any SDD | PRD FR-AGT-02; PLN-01 ST-05.5 | Abhishek Verma, Ekjot Singh; Puneet to confirm it is still wanted |
| GAP-05 | First domain pack (FR-DOM-01) | PRD FR-DOM-01; PLN-01 ST-05.7 | Puneet: pilot domain (OQ-04) and SME (OQ-05) |
| GAP-06 | PRD FR-WFL-03 and US-08 still name `greenfield-architecture` and `greenfield-bootstrap`; the repo follows Doc 3 (`greenfield-feature`). A skeleton-creating bootstrap step is not designed | PLN-OI-02 | Puneet: update the PRD or ask for the bootstrap workflow |
| GAP-07 | Portal admin screens (clients, consent, role grants) are not designed or built; the admin API exists (`services/insights/app/api/v1/admin.py`) | SDD-13 §7.2; SDD-09 §1.2 | Puneet names the owner (OI-13-04) |
| GAP-08 | Conflict: US-11 AC2 says a critical secure-code finding gives ESCALATE; SDD-03 §11.1 row 6 sends a `blocker` finding to NEEDS-INPUT, and the code follows SDD-03 | Doc 2 US-11; SDD-03 §11.1 | Puneet: pick one; then update Doc 2 or SDD-03 and the decide table |

## 10. How to keep this current

- Update a row in the same pull request that delivers or changes the item (GOV-01 §4).
- `make docs-check` checks links, registry ids, doc control rows and that `backlog.csv` matches PLN-01 §7.
- Re-count §1 when a status changes.

## 11. Done criteria

- Every tracker item in §2–§6 has a repo path and a status, and no item is Missing.
- Every PRD requirement and user story in §7–§8 maps to at least one SDD section and at least one code path or test.
- Puneet has reviewed this document.

## 12. Open items

| Id | Item | Owner |
| --- | --- | --- |
| TR-OI-01 | Close each "Needs Puneet / external" row; the rows name who acts | Puneet Singh Nanda |
| TR-OI-02 | Decide on GAP-01 to GAP-08 (build, defer or drop) | Puneet Singh Nanda with the area owners |
