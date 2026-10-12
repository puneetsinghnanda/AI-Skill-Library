> **Superseded (6 Oct 2026).** This single-file PRD is replaced by the six-document set: [1 PRD](../product/01-prd.md) · [2 Personas & Stories](../product/02-personas-and-stories.md) · [3 Architecture](../architecture/03-architecture.md) · [4 Design & UX](../ux/04-design-and-ux.md) · [5 API & Rules](../architecture/05-api-and-rules.md) · [6 Constraints & Out-of-Scope](../product/06-constraints.md). Kept for history only.

# Truminds AI Skill Library — Product Requirements Document

Oct 5, 2026 · @Puneet Singh Nanda

## 1. Document control

This PRD defines what the Truminds AI Skill Library must do and how success is judged; architecture detail lives in the companion plan, linked below.

| Field | Value |
| --- | --- |
| Product | Truminds AI Skill Library (AI capability platform) |
| Owner | @Puneet Singh Nanda |
| Approver | @Puneet Singh Nanda (sole approver) |
| Version | 1.0 draft |
| Status | Draft for review |
| Companion documents | [Architecture and implementation plan](architecture-plan-2026-09-28.md); earlier prototype handover (`HANDOVER_1.md`, superseded) |
| Delivery team | Abhishek, Shubham, Japman (backend); Ekjot, Gaurav (frontend) |

**How to read requirement IDs.** Functional requirements are `FR-<module>-<n>`, non-functional are `NFR-<n>`. Priority: **P0** must be in the first release, **P1** should be, **P2** later.

**Answers recorded from the owner (5 October 2026)**

- Approver: Puneet Singh Nanda only.
- First release supports all eight roles: Requirements Analyst, Solution Architect, Developer, Quality Engineer, DevOps, Security, UX, Delivery Manager (Mobile as a skill pack on Developer and QA).
- Skills run on Claude through company seats in the Claude Code desktop app; hosting cloud for the Truminds services (telemetry, portal) is **not decided**.
- Pilots run on both Truminds-owned code and client code once the client consents.
- First release includes both greenfield and brownfield workflows.
- Engineers use Claude Code and Cowork today.
- Numeric success targets are set after pilot baselines exist.
- The stack readout planned for 1 October has not been held; the stack is recorded as proposed.

## 2. Background and problem statement

Truminds' AI capability today is scattered across individual experiments, so it can neither be reused by engineers nor shown to clients as one credible capability.

**What happens today**

- Teams build their own prompts and agents for coding, testing or documents; each is tied to one project, one model or one person.
- Nothing is versioned, evaluated or owned, so no one can say whether an AI output is reliable.
- AI outputs are passed along as chat text, so a mistake early in the work is invisible until late.
- Brownfield work, most of what Truminds delivers, suffers most: the AI does not know the existing system, so it guesses.
- Sales cannot show breadth (SDLC roles, domains such as telecom, embedded, IoT, networking, digital) with evidence; they can only describe it.

**The problem to solve.** Give Truminds one governed library of small, reusable AI skills that any engineer can run on any brownfield or greenfield system, chained into workflows whose results are checked before anyone relies on them, and whose real usage becomes the evidence Sales shows clients.

**Why now.** Agent skills, tool protocols (MCP) and durable workflow engines are now open standards or mature products, so Truminds can build the parts that are its intellectual property instead of a whole platform.

## 3. Vision, goals and non-goals

**Vision.** A Truminds AI capability platform that turns engineering, technology and domain expertise into composable AI skills, roles, workflows and pods, used daily by engineers and shown to clients with evidence.

**Goals**

| # | Goal | How it is judged |
| --- | --- | --- |
| G1 | Engineers in every role reuse skills instead of building their own | Weekly active engineers; skill runs per week |
| G2 | AI output is trustworthy enough to act on | First-pass acceptance; calibration error; escaped defects |
| G3 | Any brownfield or greenfield system can be onboarded | Systems with a current context pack; time to onboard a system |
| G4 | Chains are reliable from the first step | Root-caused rework |
| G5 | Sales shows evidence-backed capability across roles and domains | Capability map cells backed by evals and real runs |
| G6 | Truminds can sell AI-augmented pods | Pods quoted from the pod builder; measured uplift per pod |
| G7 | The library improves from its own use, safely | Skill versions promoted through the improvement loop |

**Non-goals**

- Replacing engineers or selling AI agents as headcount; pods are people plus AI.
- Building our own LLM, agent runtime or coding assistant.
- Fully autonomous merges, deployments or client communication; these always need a human.
- Counting skills as a success measure.
- Tying the platform to one domain, stack or model provider.

## 4. Users and personas

Nine personas use the platform; the first release serves all of them, with engineers in eight roles as the primary users.

| Persona | Who | Needs from the platform | Main entry point |
| --- | --- | --- | --- |
| Requirements Analyst / BA | Turns client asks into ready requirements | Ambiguity found early, acceptance criteria drafted, open questions owned | Plugin in Claude Code or Cowork |
| Solution Architect | Designs changes and new systems | Impact analysis, ADRs, NFR review, context of the existing system | Plugin, portal |
| Developer (incl. mobile) | Builds and fixes | Code changes that compile and pass tests, grounded in the real codebase | Plugin, `tsl` CLI |
| Quality Engineer | Plans and automates tests | Test plans, automation scripts, failure analysis traced to requirements | Plugin, CLI |
| DevOps Engineer | Builds pipelines and operates systems | CI/CD, infrastructure review, deployment and incident analysis | Plugin, CLI |
| Security Engineer | Reviews risk | Threat models, secure-code and dependency review | Plugin |
| UX Designer | Designs flows and screens | User flows, accessibility and design review | Plugin, portal |
| Delivery Manager | Plans and reports | Estimation, dependency and risk views, status from real run data | Portal (run status and analytics) |
| Sales / Pre-sales | Wins work | Evidence-backed capability map, demo replays, pod sheets | Portal (read-only) |

**Platform-side personas**

| Persona | Responsibility |
| --- | --- |
| Skill owner | Owns a skill's quality, evals and every new version |
| Context-pack owner (tech lead of a system) | Keeps that system's pack accurate |
| Stage approver | Promotes skills to production in one lifecycle stage |
| Platform admin | Users, permissions, budgets, model allowlists, tenants |

## 5. Scope

The first release (end of Phase 2) covers all eight roles, both greenfield and brownfield, any stack with a verifier profile, and both Truminds-owned and consented client code.

| In scope for the first release | Out of scope for the first release |
| --- | --- |
| Skill library with spec, registry, versioning and evals | Fully autonomous merge, deploy or infrastructure change |
| 8 agents (roles) and their skill packs | Our own LLM, agent runtime or IDE |
| Brownfield workflows: feature, defect triage | Automatic promotion of skill versions |
| Greenfield workflows: requirement to architecture, project bootstrap, first feature | Tier C hardware-in-the-loop verifiers (Phase 3) |
| Context packs for any brownfield system | Second domain pack and second reference system (Phase 3) |
| Harness: hard gates, grounding, independent judge, bands, autonomy matrix | Pod builder plugin and client-facing pod sheets (Phase 3) |
| Human gates in the Claude Code session (open-questions and approval files) and on the pull request | Client-VPC deployment (Phase 3) |
| First domain pack, chosen by the first pilot's domain | Model routing across providers (Phase 3) |
| Entry points: Truminds plugin in the Claude Code desktop app, `tsl` CLI, portal for discovery and analytics | Skills served over MCP (Phase 3) |
| Capability map (read-only) for Sales | Billing or chargeback |
| Security: SSO, OPA tool policy, PII masking, injection guard, tenant isolation, audit |  |
| Pilots on Truminds-owned code and on client code with written consent | Client code without written consent |

## 6. Product concepts

The product is built from seven objects; every requirement in this PRD is about creating, running, checking or showing one of them.

&#91;embedded content: product object model · seven objects\]

| Object | Definition | Example |
| --- | --- | --- |
| Skill | A folder with `SKILL.md`, references, scripts and evals; does one job and produces one artifact | `requirement-review` |
| Agent | A role: persona, permitted tools, allowed skills, stop conditions | Quality Engineer |
| Workflow | A versioned chain of skills with gates, retries and branches | `brownfield-feature` |
| Package (pod) | Human roles plus agents, workflows and packs, pinned in one manifest | 1 architect + 1 developer + 1 QA pod |
| Knowledge pack | Context pack (one system) or domain pack (one industry) | Context pack of a client's order service |
| Artifact | A typed, versioned output with an envelope of traces and evidence | `story-set.v1` |
| Verifier profile | A container of stack tools that checks artifacts | `node-20-service` |

**Composition rule.** A capability is always Core skill + Technology + Domain (optional) + Project context. For example, *generate API tests* + Node.js + (no domain) + the client's context pack.

## 7. User journeys

Four journeys cover how people meet the product; each must work end to end in the first release.

&#91;embedded content: user journeys · engineer, sales, skill author, system onboarding\]

**Key user stories**

| ID | As a | I want to | So that |
| --- | --- | --- | --- |
| US-01 | Developer | run a workflow on my Jira ticket from Claude Code | I get a tested change grounded in our real codebase |
| US-02 | Reviewer | see the code, unit-test results, artifacts, evidence and confidence on the pull request | I can approve or fix it in minutes |
| US-03 | Product owner | get only the questions that block the build, each with a proposed default | requirements are ready without long review cycles |
| US-04 | Tech lead | onboard my existing system once and keep it fresh automatically | every skill knows our system without me re-explaining |
| US-05 | Architect | start a greenfield project from a requirement to an approved architecture and skeleton | new projects start on the same rails as brownfield ones |
| US-06 | Sales lead | filter the capability map by domain and role and show evidence | the client sees proof, not slides |
| US-07 | Pre-sales | turn "1 architect, 1 developer, 1 QA" into a pod sheet | I can quote an AI-augmented pod |
| US-08 | Skill author | publish a skill with evals and see its health | my skill is trusted and reused |
| US-09 | Delivery manager | see usage, uplift and cost per project | I can report value to the client |
| US-10 | Admin | set tool permissions, budgets and model allowlists per client | client rules are enforced, not hoped for |

## 8. Functional requirements

Requirements are grouped by module; P0 items define the first release, and each maps to an architecture plane in section 10.

### 8.1 Skill library and registry (REG)

| ID | Requirement | Priority |
| --- | --- | --- |
| FR-REG-01 | Every skill is a folder with `SKILL.md` (Agent Skills standard) plus Truminds fields under `metadata.truminds`: id, version, stage, maturity, owner, inputs, outputs, verification level, human gate, allowed tools, context needs | P0 |
| FR-REG-02 | CI rejects a skill with no named owner, no evals, a body over the size budget, or an input type no skill produces | P0 |
| FR-REG-03 | The registry indexes all skills, agents, workflows, packs and pods with maturity (draft, pilot, production, deprecated) and evidence | P0 |
| FR-REG-04 | Users search skills in plain language and filter by role, stage, stack, domain, mode (greenfield, brownfield) and maturity | P0 |
| FR-REG-05 | Skills are technology-neutral in method; stack-specific behaviour comes from verifier profiles and technology skill packs | P0 |
| FR-REG-06 | Usage, acceptance rate and eval scores are shown per skill | P1 |

### 8.2 Agents (AGT)

| ID | Requirement | Priority |
| --- | --- | --- |
| FR-AGT-01 | Eight agents ship in the first release: Requirements Analyst, Solution Architect, Developer, Quality Engineer, DevOps, Security, UX, Delivery Manager | P0 |
| FR-AGT-02 | Each agent declares persona, permitted tools, allowed skills (3 to 10) and stop conditions; the executor enforces the allowlist | P0 |
| FR-AGT-03 | Mobile, data and domain specialisms are skill packs on existing agents, not new agents | P0 |

### 8.3 Workflows and engine (WFL)

| ID | Requirement | Priority |
| --- | --- | --- |
| FR-WFL-01 | Workflows are versioned YAML with steps, dependencies, gates, loops, parallel branches and outcome handlers | P0 |
| FR-WFL-02 | The compiler type-checks every edge (output type satisfies the next input) and writes a lockfile of exact skill versions | P0 |
| FR-WFL-03 | Runs are resumable: run state is kept in the product repo; a paused run resumes from the last passed step without repeating finished steps | P0 |
| FR-WFL-04 | Templates in the first release: `brownfield-feature`, `defect-triage`, `greenfield-architecture` (requirement to approved architecture), `greenfield-bootstrap` (architecture to project skeleton and first feature) | P0 |
| FR-WFL-05 | When an upstream artifact is superseded, downstream artifacts become stale and only that branch re-runs | P0 |
| FR-WFL-06 | Additional templates: refactoring, API development, test automation, deployment failure analysis | P1 |

### 8.4 Planner (PLN)

| ID | Requirement | Priority |
| --- | --- | --- |
| FR-PLN-01 | The planner classifies a request (greenfield or brownfield, stack, domain, intent) and proposes a workflow template | P0 |
| FR-PLN-02 | A proposal that matches a template runs after pre-flight; any other proposal needs human approval | P0 |
| FR-PLN-03 | Pre-flight confirms context pack freshness, verifier availability and permissions before the first step | P0 |
| FR-PLN-04 | The planner composes new workflows from existing skills for unmatched requests, always human-approved | P2 |

### 8.5 Harness (HRN)

| ID | Requirement | Priority |
| --- | --- | --- |
| FR-HRN-01 | Every artifact passes the verification ladder to the level its type requires: L0 schema, L1 deterministic checks, L2 grounding, L3 independent judge, L4 human | P0 |
| FR-HRN-02 | Hard gates H1 to H7 (schema, sections, verifier checks, forbidden content, trace links, fresh inputs, permitted tools) block PASS | P0 |
| FR-HRN-03 | Signals S1 to S6 (evidence coverage, check pass rate, judge score, open blockers, context completeness, change risk) are computed per artifact | P0 |
| FR-HRN-04 | Confidence band (High, Medium, Low) is computed from rules, never reported by the generating model | P0 |
| FR-HRN-05 | Each step ends in one of six outcomes: PASS, PASS-WITH-FINDINGS, RETRY, NEEDS-INPUT, ESCALATE, ABORT | P0 |
| FR-HRN-06 | The autonomy matrix (band x action risk) decides auto-proceed or human gate; merge and deploy always need a human | P0 |
| FR-HRN-07 | Weekly calibration audits a sample of High outputs; thresholds tighten automatically when rejection exceeds the limit | P1 |

### 8.6 Human gates (GAT)

| ID | Requirement | Priority |
| --- | --- | --- |
| FR-GAT-01 | When input or approval is needed, the run pauses and writes a questions or approval file naming the owner role for each item | P0 |
| FR-GAT-02 | Final approval happens on the pull request, which carries the code, unit-test results, artifacts and verification records | P0 |
| FR-GAT-03 | Every gate decision and every human edit is recorded with who, when and why | P0 |
| FR-GAT-04 | No external write (Jira, Confluence, Git, client system) happens without a passed gate; writes are dry-run first and idempotent | P0 |

### 8.7 Context packs and Foundation (CTX)

| ID | Requirement | Priority |
| --- | --- | --- |
| FR-CTX-01 | `system-context-builder` onboards any brownfield system: scripts extract facts (services, schema, APIs, dependencies, build and deploy manifests) into `generated/` | P0 |
| FR-CTX-02 | The tech lead adds judgement (purpose, ownership, quirks, ADRs); every claim cites its source; history is queried live, never stored | P0 |
| FR-CTX-03 | Facts rebuild on every merge; drift fails CI; hand-written files carry `Owner:` and `Verified:` and are flagged when stale | P0 |
| FR-CTX-04 | The Foundation (System Baseline + Intent Baseline) must pass the Readiness Gate before downstream steps run | P0 |
| FR-CTX-05 | Downstream discoveries raise a root amendment, which creates a new baseline and marks affected work stale | P0 |
| FR-CTX-06 | Without a context pack, brownfield runs are allowed but capped at Medium confidence and labelled | P0 |
| FR-CTX-07 | Greenfield runs use an Engagement Profile (stack, NFRs, compliance) and grow an Architecture Baseline of approved ADRs | P0 |

### 8.8 Domain packs (DOM)

| ID | Requirement | Priority |
| --- | --- | --- |
| FR-DOM-01 | A domain pack holds glossary, heuristics, checklists, pitfalls, examples, domain verifiers and an eval set | P0 |
| FR-DOM-02 | Every heuristic ships with at least one eval case; lift is measured with and without the pack | P0 |
| FR-DOM-03 | Domain packs are optional; every workflow runs without one | P0 |
| FR-DOM-04 | The first pack is built for the first pilot team's domain | P0 |

### 8.9 Verifiers and execution (VER, EXE)

| ID | Requirement | Priority |
| --- | --- | --- |
| FR-VER-01 | A verifier profile is a versioned container image plus a check list; tiers A (generic), B (stack-specific), C (special) | P0 |
| FR-VER-02 | Profiles in the first release: Node, React, Java, Python | P0 |
| FR-VER-03 | A stack without a profile cannot reach pilot maturity or be shown as capability | P0 |
| FR-EXE-01 | Skills run in the Claude Code desktop app on the engineer's company Claude seat; no Claude API is used to run skills | P0 |
| FR-EXE-02 | Model access, usage limits and data settings are managed in the company Claude organisation; usage is reported through Claude Code's OpenTelemetry export | P0 |
| FR-EXE-03 | Tools are reached only through MCP servers allowed by policy (Jira, Confluence, GitHub, Slack first) | P0 |
| FR-EXE-04 | Verifier checks run in a container per verifier profile, on the engineer's machine and again in CI; skills never get production credentials | P0 |

### 8.10 Artifacts and traceability (ART)

| ID | Requirement | Priority |
| --- | --- | --- |
| FR-ART-01 | Every handoff is a typed artifact with an envelope: id, type, producer and version, run, baseline, inputs, traces, open items, verification, confidence, outcome, status | P0 |
| FR-ART-02 | Artifacts are stored as files in Git; metadata and the trace graph in a database | P0 |
| FR-ART-03 | Any artifact can be traced back to its requirements and forward to tests, code and results | P0 |

### 8.11 Improvement loop (IMP)

| ID | Requirement | Priority |
| --- | --- | --- |
| FR-IMP-01 | Gate decisions, human edit diffs, retries, hard-gate failures and downstream rework are captured per skill | P0 |
| FR-IMP-02 | A weekly job clusters failures; an improver agent opens a PR with a new eval case first, then the fix | P1 |
| FR-IMP-03 | A PR must pass the full eval suite and a hidden holdout set with no must-NOT-do regression; the owner approves; canary then promote | P1 |
| FR-IMP-04 | Rollback is a version-pin change | P0 |

### 8.12 Entry points (EXP)

| ID | Requirement | Priority |
| --- | --- | --- |
| FR-EXP-01 | Role packs install from a private Claude Code / Cowork plugin marketplace on stable or beta channels | P0 |
| FR-EXP-02 | `tsl` CLI: `init-context`, `run`, `verify`, `status`; same behaviour on a laptop and in CI | P0 |
| FR-EXP-03 | Workflows start with /truminds:run \<workflow> \<ticket> and continue with /truminds:resume \<run> | P0 |
| FR-EXP-04 | Backstage portal: catalogue, search, evidence, one-command install | P0 |
| FR-EXP-05 | Skills also work in other SKILL.md clients (Copilot, Cursor, Codex) for client sites that mandate them | P1 |
| FR-EXP-06 | Skills are served over MCP to any MCP client | P2 |

### 8.13 Capability map and pods (MAP, POD)

| ID | Requirement | Priority |
| --- | --- | --- |
| FR-MAP-01 | The capability map shows role x lifecycle stage and domain x stage, each cell with production skills, eval results, lift, real-run count and a replay link | P0 |
| FR-MAP-02 | Cells without evidence show as roadmap; only production items are shown as capability | P0 |
| FR-MAP-03 | Demo replays run on the reference system; no client code or data is ever shown | P0 |
| FR-POD-01 | The pod builder turns a client ask (roles, stack, domain, mode, constraints) into a pinned manifest, a pod sheet, an install command and an uplift baseline | P1 |
| FR-POD-02 | Non-production items go to a gaps list and are excluded from client claims | P1 |

### 8.14 Administration and governance (ADM)

| ID | Requirement | Priority |
| --- | --- | --- |
| FR-ADM-01 | Company SSO for all entry points; roles per project and client | P0 |
| FR-ADM-02 | Admins set per client: tool permissions, model allowlist, budgets, data residency and code-use consent | P0 |
| FR-ADM-03 | Client code is processed only when written consent is recorded for that client | P0 |
| FR-ADM-04 | Stage approvers promote skills to production through CODEOWNERS | P0 |

### 8.15 Local execution and telemetry (LOC, TEL)

| ID | Requirement | Priority |
| --- | --- | --- |
| FR-LOC-01 | `/truminds:run <workflow> <ticket>` starts a run in the Claude Code desktop app; run state is kept in `.truminds/runs/<run>/state.json` | P0 |
| FR-LOC-02 | A hook runs the harness after every artifact write; another hook blocks any skill whose inputs lack a valid PASS record or that is not the next step | P0 |
| FR-LOC-03 | The harness meaning check runs as a reviewer subagent with its own context and rubric; code verifies its citations and decides | P0 |
| FR-LOC-04 | On NEEDS-INPUT the run writes an open-questions file (ID, type, blocks, owner role, options, evidence, answer, answered by) and pauses | P0 |
| FR-LOC-05 | `/truminds:resume <run>` refuses to continue until every blocking question has an answer and a named decider | P0 |
| FR-LOC-06 | Design and release approvals are recorded with the approver's name before resume | P0 |
| FR-LOC-07 | `tsl pr` opens the pull request with code, unit-test results, artifacts, verification summary, answered questions and the run ID | P0 |
| FR-LOC-08 | Verification records are signed; CI re-runs the harness and rejects unsigned or altered records | P0 |
| FR-TEL-01 | `tsl` sends run events (started, skill finished, paused, answers recorded, artifact edited, PR created, completed) to the telemetry service with the run ID and user | P0 |
| FR-TEL-02 | Events are queued in `.truminds/outbox/` when offline and sent later | P0 |
| FR-TEL-03 | Claude Code's OpenTelemetry export is enabled through managed settings for usage, tokens and cost | P0 |
| FR-TEL-04 | A GitHub webhook sends reviews, CI results and merges, joined to the run by run ID | P0 |
| FR-TEL-05 | For client repos only metadata and counts are sent; content only for Truminds-owned repos or with written consent | P0 |
| FR-TEL-06 | Dashboards show run status, usage per user and repo, and skill performance per version | P0 |
| FR-TEL-07 | A weekly job turns telemetry into improvement PRs on the skills repo (section 11.4) | P1 |

## 9. Non-functional requirements

Non-functional requirements are as binding as functional ones; numeric limits marked *proposed* are confirmed in Phase 0.

| ID | Area | Requirement |
| --- | --- | --- |
| NFR-01 | Security | All ticket, repo and document content is treated as untrusted input; prompt-injection screening on inputs; tools limited by policy |
| NFR-02 | Security | No secrets in prompts, packs or repos; secrets come from a vault into sandboxes only |
| NFR-03 | Privacy | PII is detected and masked before any model call; no client code or data in evals, fixtures or demos |
| NFR-04 | Isolation | Each client has its own namespace, storage prefix and context packs; no cross-client retrieval |
| NFR-05 | Data protection | Encryption at rest and in transit; data residency per client setting |
| NFR-06 | Auditability | Every run records inputs, versions (skill, workflow, rules, verifier, model), tools used, outputs, checks and human decisions; records are retained per client contract |
| NFR-07 | Reproducibility | Any run can be replayed with the same pinned versions |
| NFR-08 | Reliability | A paused or failed run resumes from the last passed step; no step is executed twice for an external write |
| NFR-09 | Availability | Platform services target 99.5% availability in working hours (*proposed*) |
| NFR-10 | Performance | Harness result within 2 minutes of an artifact being written; events reach telemetry within 5 minutes when online (*proposed*) |
| NFR-11 | Cost | Cost per run and per user reported from Claude Code usage data; seat and usage limits managed in the Claude organisation |
| NFR-12 | Portability | Truminds cloud services are cloud-neutral (containers, open standards); skills are in the open SKILL.md format and work in other SKILL.md clients |
| NFR-13 | Scalability | Discovery stays fast at 500 or more skills because only names and descriptions load until a skill is used |
| NFR-14 | Accessibility | Portal and dashboards meet WCAG 2.1 AA |
| NFR-15 | Maintainability | Every skill, pack and profile has a named owner; unowned items are blocked by CI |

## 10. System architecture

The system has five planes plus an improvement loop; Truminds builds the content (skills, packs, evals) and the decisions (rules, gates, confidence), and reuses existing products to run, store and display them.

&#91;embedded content: system architecture · five planes, improvement loop, cross-cutting governance\]

Each plane calls the one below it. The highlighted control plane decides what runs and whether it passed.

| Plane | Built by Truminds | Reused (proposed, confirmed at G0) |
| --- | --- | --- |
| Experience | Capability map and pod builder plugins, `tsl` CLI, gate and run views | Backstage, Claude Code / Cowork plugin marketplace, Jira, GitHub, Slack |
| Capability | All skills, agents, workflow templates, pod manifests, artifact schemas | SKILL.md format, JSON Schema |
| Control | Planner, harness rules, confidence calculator, workflow compiler, gate and autonomy policies | Claude Code hooks and local run state; OPA for policy |
| Execution | Plugin packaging, hook scripts (tsl), verifier profile images | Claude Code desktop app on company Claude seats, MCP servers, containers |
| Knowledge and data | Context-pack spec and builder, domain packs, eval sets, reference systems, trace schema | Git, PostgreSQL with pgvector, Langfuse on OpenTelemetry |

**Model and hosting.** Skills and the reviewer run on Claude through company seats in the Claude Code desktop app (section 11). Hosting for the Truminds cloud services (telemetry service, portal) is not decided; they are container-based and cloud-neutral. See decision D-04 in section 18.

## 11. End-to-end flow and call flows

Every request moves through eight stages; the platform works between five human gates and stops early if its own checks fail. The example is a feature on an existing system: "Show 30 days of order history."

&#91;embedded content: end-to-end flow · 8 stages, 5 human gates\]

Read each row left to right: who acts, what the platform does, what it produces. Two-way arrows are gates.

| Stage | What happens | Gate and approver | If it fails |
| --- | --- | --- | --- |
| 0 Onboard (once per system) | Facts extracted by script; system description drafted with citations | Tech lead signs the context pack | Pack stays draft; brownfield runs capped at Medium |
| 1 Trigger | Planner picks a template; pre-flight checks pack, verifier, permissions | None (template already approved) | Unmatched request goes to a human for plan approval |
| 2 Foundation | Requirements split into numbered items; cross-check against the system finds conflicts (order history kept only 24 hours) | Product owner answers blockers and signs the intent | NEEDS-INPUT to the named owner; run pauses |
| 3 Design | Impact analysis; ADR for significant decisions | Tech lead approves design | Rework design or ESCALATE |
| 4 Build | Stories, tests and code in a sandbox; verifier fix loop up to 3 times | None (nothing reaches the codebase yet) | ESCALATE to tech lead after 3 failed fixes |
| 5 Judge | Hard gates, grounding, independent judge; band and outcome | Code reviewer approves the PR | Reject with reason; returns to build |
| 6 Release | Rollback, migrations, change risk, test coverage checked | Release owner approves | Release held |
| 7 Learn | Edits, rejections and retries feed the improvement loop | None (changes later go through owner approval) | — |

**Greenfield variant.** Stage 0 is replaced by an Engagement Profile (stack, NFRs, compliance); stage 3 produces the Architecture Baseline and a project skeleton through `greenfield-architecture` and `greenfield-bootstrap`; stages 4 to 7 are the same.

### 11.1 Local execution model

Engineers run every skill on their own machine in the Claude Code desktop app, through a Truminds plugin, on their company Claude seat; no Claude API is used to run skills. Hooks in the plugin run the harness after every skill and send the facts of each run to a Truminds telemetry service.

&#91;embedded content: local execution model · laptop, Claude, telemetry service, GitHub\]

| Pipe | From → To | Carries |
| --- | --- | --- |
| A | Claude Code → Anthropic | Prompts and responses for skills and the reviewer subagent, on the engineer's company Claude seat |
| B | `tsl` scripts (run by hooks) → Truminds telemetry | Run events: run started, skill finished, outcome, findings, questions, answers, edits, PR created |
| C | Claude Code built-in OpenTelemetry export → Truminds telemetry | Sessions, tokens, cost, tool use per user; switched on once by an administrator |
| D | `tsl pr` → GitHub | Branch push and pull request with code, test results, artifacts and verification records |
| E | GitHub webhook → Truminds telemetry | Reviews, changes requested, CI result, merge |

**What runs where**

| Part | Where | Uses the Claude API? |
| --- | --- | --- |
| Skills, workflow commands, chaining | Claude Code desktop app | No; company Claude seat |
| Harness fact checks, evidence checks, decision | `tsl` scripts run by hooks | No LLM |
| Harness meaning check | Reviewer subagent in the same session (own context and instructions, optionally a different model) | No; company Claude seat |
| Verifier checks (build, tests, lint, scans) | Verifier container on the engineer's machine, and again in CI | No LLM |
| Run records, analytics, improvement feed | Truminds telemetry service | No LLM |

**One-time setup**

1. The engineer has a company Claude seat and the Claude Code desktop app; personal accounts are not used for any client code.
2. An administrator sets managed settings for all engineers: the private Truminds plugin marketplace is required, the plugin's hooks are enforced, and the OpenTelemetry export points at the Truminds telemetry endpoint.
3. The engineer installs the role pack (for example `truminds-developer`) from the marketplace on the stable channel; updates arrive automatically.
4. The engineer runs `tsl login` once (company SSO); the token ties every event to a real user.
5. The product repo is onboarded once: `tsl init-context` builds the context pack, the tech lead signs it, and `.truminds/tsl.yaml` records the stack, verifier profile, owners and pinned workflow versions.

**Plugin contents**

```
truminds-plugin/
  .claude-plugin/plugin.json
  skills/       requirement-review/  intent-cross-check/  story-writer/  impact-analysis/
                test-plan-generator/ code-change/  unit-test-gen/  defect-triage/ ...
  commands/     run.md  resume.md  status.md      -> /truminds:run, /truminds:resume, /truminds:status
  agents/       reviewer.md                       -> harness meaning check (subagent)
  workflows/    brownfield-feature.yaml  greenfield-architecture.yaml  defect-triage.yaml ...
  hooks/        hooks.json                        -> after artifact write, before each skill, session end
  bin/          tsl                               -> verify, decide, state, events, pr, resume
```

**Product repo layout**

```
<product-repo>/
  .truminds/
    tsl.yaml                project config: stack, verifier profile, owners, pinned workflows
    context/                context pack (signed by the tech lead; facts rebuilt by CI)
    artifacts/SW-123/       one folder per ticket: every skill output and its verification record
    runs/RUN-2031/          run state (state.json), open questions, answers
    outbox/                 events not yet sent (offline)
```

### 11.2 Complete local flow: worked example

Ticket **SW-123**, "Show 30 days of order history", on a client's existing order service, run by a developer from requirement to pull request.

&#91;embedded content: local call flow · one skill step from write to recorded outcome\]

In the diagram, messages 4 to 13 repeat for every skill in the workflow; message 15 happens once, at the end. Solid arrows are calls; dashed arrows are replies.

**Step 1. Start the run.** In the Claude Code desktop app, in the product repo, the developer types:

```
/truminds:run brownfield-feature SW-123
```

`tsl` creates `RUN-2031`, reads the pinned workflow from `tsl.yaml`, writes the run state, and sends `run_started` to the telemetry service.

```json
// .truminds/runs/RUN-2031/state.json
{"run_id": "RUN-2031", "ticket": "SW-123", "workflow": "brownfield-feature@2.1.0",
 "lockfile": "brownfield-feature.lock", "baseline": "FND-orders@v3",
 "steps": ["requirement-review", "intent-cross-check", "impact-analysis", "story-writer",
           "test-plan-generator", "code-change", "unit-test-gen", "open-pr"],
 "current": "requirement-review", "status": "RUNNING"}
```

**Step 2. First skill runs.** `requirement-review` reads the Jira ticket through MCP and the context pack from `.truminds/context/`, and writes `.truminds/artifacts/SW-123/review-report.md` with numbered requirements and typed findings.

**Step 3. Harness runs automatically (hooks).**

1. The write fires a hook. `tsl verify` runs the code checks: schema, sections, trace links, and lookups in `context/generated/` (services, tables, endpoints). A failure is sent back to Claude to fix (RETRY, at most 2 times); the reviewer is not called.
2. Facts pass, so Claude calls the **reviewer subagent** with the artifact, the relevant context-pack sections and the rubric. It writes `review.json`: findings, each citing evidence.
3. Writing `review.json` fires the second hook. `tsl decide` checks every citation exists and says what is claimed, drops unproven findings, applies the rules, and writes a signed `review-report.verification.json` with the band and outcome.
4. `tsl` sends `skill_finished` to telemetry: skill and version, outcome, band, retries, findings by severity, duration.

**Step 4. Open questions: the run pauses.** The cross-check finds that order history is kept only 24 hours. The outcome is NEEDS-INPUT. The skill writes the questions file, the state becomes PAUSED, `run_paused` is sent, and Claude tells the developer what is needed and from whom. The session can be closed.

```markdown
# Open questions · RUN-2031 · SW-123

## Q-1 (blocking REQ-001)
Type: decision · Owner role: product owner
Question: Order history is kept for 24 hours. Extend retention to 30 days?
Evidence: context/orders/data-model.md#retention
Options:
  A. Extend to 30 days (storage and cost impact)
  B. Reduce the feature to 24 hours
Answer: 
Answered by: 

## Q-2 (non-blocking)
Type: gap-default · Owner role: product owner
Question: Which time zone defines a day boundary?
Proposed default: UTC, start-inclusive
Answer: 
Answered by: 
```

**Step 5. Answer.** The developer answers, or sends the file to the product owner and records the reply. `Answered by` must name the person who decided.

**Step 6. Resume.**

```
/truminds:resume RUN-2031
```

`tsl` checks every blocking question has an answer and a named decider, sends `answers_recorded` (who answered; defaults accepted or rejected), and resumes from the paused step. `requirement-review` re-runs with the answers, the harness passes, and the Intent Baseline is signed.

**Step 7. Chaining.** Before each skill a hook checks that its input artifacts have a valid PASS record and that it is the next step in `state.json`. Otherwise the skill is blocked and Claude says which step to fix. Each skill then runs as in steps 2 and 3: `intent-cross-check`, `impact-analysis`, `story-writer`, `test-plan-generator`.

**Step 8. Code and unit tests.** `code-change` and `unit-test-gen` change the code on branch `tsl/SW-123`. The hook runs the verifier container: build, unit tests, lint, security and secrets scans. Failures go back to Claude to fix, at most 3 times, then ESCALATE.

**Step 9. Pull request.** The last step, `tsl pr`, pushes the branch and opens the pull request. The description is generated:

```markdown
## SW-123 · Show 30 days of order history · RUN-2031
Workflow: brownfield-feature@2.1.0 · Baseline: FND-orders@v4

### Changes
- OrderService: GET /orders/history (paginated, 100 per page)
- Retention extended to 30 days (decision Q-1, answered by: product owner)

### Unit tests
42 passed, 0 failed · coverage 81% (no drop) · mutation score 74%

### Verification
| Artifact | Outcome | Band |
| review-report | PASS | High |
| impact-report | PASS-WITH-FINDINGS | Medium |
| code-change | PASS | High |

Artifacts: .truminds/artifacts/SW-123/
```

`pr_created` is sent to telemetry.

**Step 10. Review and merge.** The reviewer approves or requests changes on GitHub. CI re-runs the harness and checks every verification record's signature. The GitHub webhook sends reviews, CI result and merge to telemetry.

**Rules that make the local flow trustworthy**

- Hooks are enforced by managed settings; engineers cannot switch them off.
- Verification records are signed; a hand-edited record fails in CI.
- A skill cannot start unless its inputs have valid PASS records and it is the next step.
- Merge always needs a human reviewer on the pull request.

Approvals at the design and release gates use the same pause and resume: the run writes an approval file, and the approver's name and decision are recorded before `/truminds:resume` continues.

### 11.3 What is recorded in the cloud

The LLM never sends anything to Truminds. Claude Code runs the plugin's hook scripts at fixed moments; those scripts read the run's local facts and send them to the Truminds telemetry service over HTTPS, using the engineer's `tsl login` token.

**How one event is produced.** When a skill writes an artifact, Claude Code runs the hook and passes it a description of what happened:

```json
{"hook_event_name": "PostToolUse", "session_id": "a1b2c3",
 "cwd": "/Users/dev/orders-service", "tool_name": "Write",
 "tool_input": {"file_path": ".truminds/artifacts/SW-123/review-report.md"}}
```

`tsl` runs the harness, reads `state.json`, the verification record and git, and posts:

```json
POST /v1/events
{"event": "skill_finished", "run_id": "RUN-2031", "user": "dev@truminds.com",
 "repo": "orders-service", "ticket": "SW-123", "skill": "requirement-review@1.2.0",
 "outcome": "NEEDS-INPUT", "band": null, "retries": 0,
 "findings": {"blocker": 1, "major": 1, "minor": 2}, "open_questions": 2,
 "duration_sec": 94, "timestamp": "2026-10-06T10:20:11Z"}
```

**Events**

| Event | Sent when | Key fields |
| --- | --- | --- |
| `run_started` | `/truminds:run` | run, user, repo, ticket, workflow and version |
| `skill_finished` | Every artifact verified | skill and version, outcome, band, retries, findings by severity, duration |
| `run_paused` | Open-questions file written | number of blocking and non-blocking questions |
| `answers_recorded` | `/truminds:resume` | who answered each question, defaults accepted or rejected |
| `artifact_edited` | Artifact committed | how much the engineer changed the AI output, by section |
| `pr_created` | `tsl pr` | PR link, unit-test results, verification summary |
| `pr_reviewed`, `ci_result`, `pr_merged` | GitHub webhook | review comments, changes requested, CI outcome, time to merge |
| `run_completed` / `run_aborted` | End of run | total duration, number of pauses and retries |

**Usage metrics without extra code.** Claude Code's built-in OpenTelemetry export, switched on by an administrator, sends sessions, tokens, cost, tool use and lines changed per user to the same service.

**Joining it up.** Every event carries `run_id`; `tsl pr` writes the run ID into the PR description, so GitHub webhook events join the same run. Offline events wait in `.truminds/outbox/` and are sent on the next run.

**Privacy.** For client repos only metadata and counts leave the machine; no code and no artifact text. Artifact content is sent only for Truminds-owned repos or where the client has consented in writing.

**What the service shows**

| View | Answers |
| --- | --- |
| Run status | Every run, its current step, paused or completed, waiting on whom |
| Usage | Who uses which repo and skill, how often, at what cost |
| Skill performance | First-pass acceptance, retries, outcomes, edit size, review rejections per skill and version |
| Capability map | Evidence per role and domain from real runs |

### 11.4 How runs feed improvement

A weekly job reads the same events and clusters problems per skill, then opens an improvement PR on the skills repo: first the failing case as a new eval case, then the fix. The skill owner approves; the new version reaches engineers through the plugin's stable channel.

| Signal | Source | Tells the team |
| --- | --- | --- |
| Hard-gate failures and retries | `skill_finished` | Where the skill's procedure is weak |
| Reviewer findings by rubric item | `skill_finished` | Which quality checks fail most |
| Edit size and sections edited | `artifact_edited` | What engineers keep correcting |
| Proposed defaults rejected | `answers_recorded` | Which house defaults are wrong |
| Changes requested and review comments | GitHub webhook | Quality gaps the harness missed |
| CI failures after a local PASS | GitHub webhook | Gaps between local checks and CI |
| Defects later linked to the ticket | Jira | Escapes to add as eval cases |

For client repos the improvement job works from metadata; turning a client failure into an eval case needs a sanitised example submitted by the engineer or the client's consent.

## 12. Harness and confidence rules

The harness turns evidence into a confidence band and one of six outcomes; this is what makes a chain of AI steps trustworthy.

&#91;embedded content: harness decision flow · ladder, hard gates, signals, band, autonomy, calibration\]

Hard gates are checked first and cannot be outweighed by good scores.

**Hard gates (any failure blocks PASS)**

| Rule | Check | On failure |
| --- | --- | --- |
| H1 | Artifact validates against its schema | RETRY |
| H2 | Required sections present, including Known / Assumed / Unknown | RETRY |
| H3 | Verifier profile checks pass (build, tests, lint, security scan) | RETRY in the fix loop, then ESCALATE |
| H4 | No forbidden content: invented values in acceptance criteria, secrets, PII, client names in shared outputs | ABORT for secrets or PII; RETRY for invented values |
| H5 | Trace links to Foundation items present and resolving | RETRY |
| H6 | All inputs are current, not stale | Re-run upstream branch |
| H7 | Only permitted tools were called | ABORT |

**Scored signals**

| Signal | Measure | Starting threshold for High (*proposed*) |
| --- | --- | --- |
| S1 Evidence coverage | Share of claims with a resolving citation | 90% |
| S2 Check pass rate | Share of verifier checks passed | 100% |
| S3 Judge score | Independent rubric score | 4.0 of 5 |
| S4 Open blockers | Open `decision` items | 0 |
| S5 Context completeness | Declared context present and fresh | All |
| S6 Change risk | Diff size, files, sensitive paths | Below the skill's limit |

**Autonomy matrix**

| Action | High | Medium | Low |
| --- | --- | --- | --- |
| Draft artifact, read-only | Auto-proceed | Proceed, findings flagged | Human review |
| Write to Jira or Confluence | Review before write | Review before write | Human rewrite |
| Open a pull request | Open for review | Open as draft | Human decides |
| Merge, deploy, change infrastructure | Always human | Always human | Always human |

Thresholds are proposals until pilot data and calibration audits set them per skill.

### 12.1 Who checks what: code versus LLM

Every artifact is checked in the same four steps: code checks facts, an LLM reviewer checks meaning against the context pack, code verifies the reviewer's evidence, and code makes the decision.

&#91;embedded content: who checks what · 4 steps, 3 in code, 1 by an LLM reviewer\]

The LLM is essential for understanding whether an artifact fits the system, its conditions and its code flows; code is essential for certainty, for catching invented facts on both sides, and for a repeatable decision. The harness rules engine is written by engineers in ordinary code (engineers may use AI to help write it, but it is reviewed, tested and versioned like any code).

**Why code can check relationships at all.** The context pack's `generated/` folder (`services.json`, `schema.json`, `endpoints.json`, `dependencies.json`) is machine-readable and rebuilt from the real code on every merge. Questions such as "does this service exist?" or "does this column exist?" become lookups.

**Worked example: a design artifact**

Request: "Show 30 days of order history." The design skill produces:

```yaml
type: impact-report.v1
traces: [REQ-001, REQ-002]
change:
  service: OrderService
  endpoint: GET /orders/history
  reads: orders.created_at, orders.status
  filter: created_at within last 30 days, customer_id = caller
  pagination: 100 per page
cites:
  - context/orders/generated/services.json#OrderService
  - context/orders/generated/schema.json#orders
```

| Step | Check | Done by | Result in the example |
| --- | --- | --- | --- |
| 1 | `OrderService` exists in `services.json` | Code | Pass |
| 1 | `orders.created_at` and `orders.status` exist in `schema.json` | Code | Pass |
| 1 | `GET /orders/history` does not clash with `endpoints.json` | Code | Pass |
| 1 | Every cited file and anchor exists; every REQ is traced | Code | Pass |
| 2 | Does the design respect data retention in `data-model.md`? | LLM | **Finding:** order history is kept 24 hours; 30 days cannot be served (blocker) |
| 2 | `known-quirks.md`: archived orders live in a separate store. Does the design read both? | LLM | **Finding:** archive store not read (major) |
| 2 | Are acceptance conditions covered (empty result, time zones, more than 100 orders)? | LLM | **Finding:** time-zone boundary not specified (minor, proposed default: UTC start-inclusive) |
| 2 | Does it follow the existing request flow (gateway, auth check)? | LLM | Pass, cites `architecture.md#request-flow` |
| 3 | Each finding's citation exists and says what the finding claims | Code | 3 findings verified; none dropped |
| 4 | Hard gates pass; S4 open blockers = 1 | Code | Outcome **NEEDS-INPUT** to the product owner; band not assigned until resolved |

The LLM reviewer must return structured findings, each with a citation:

```json
{"finding": "Design ignores 24-hour retention of order history",
 "severity": "blocker", "type": "decision",
 "evidence": "context/orders/data-model.md#retention",
 "rubric_item": "R3 respects data constraints"}
```

### 12.2 Does this split fit every artifact?

Yes: every artifact goes through the same four steps. What changes is how much each step can carry. Early artifacts (requirements, design) are mostly prose, so the LLM does most of the checking; code and test artifacts can be executed, so code does most of it.

| Artifact | Step 1 and 3: code checks | Step 2: LLM checks | Who carries most of the weight |
| --- | --- | --- | --- |
| Requirement review (`intent.v1`) | Schema; every item numbered; Known/Assumed/Unknown present; no invented values in acceptance criteria; terms exist in glossary; trace links | Ambiguity, conflicts, missing conditions, intent versus system conflicts, decision versus default classification | LLM |
| Design / impact report | Named services, tables, columns, endpoints exist; no clashes; citations exist; traces | Fit to architecture and request flow, constraints (retention, limits), quirks, NFRs, missing cases | LLM, backed by code lookups |
| Stories and acceptance criteria | Each story traces to a REQ; each AC testable in format; no proposed default inside an AC | AC really covers the requirement; stories are independent and sized | LLM |
| Test plan | Every AC has at least one test; coverage matrix complete | Tests would actually detect a failure; edge and negative cases present | Shared |
| Code change | Compiles; lint; static analysis; security scan; secrets scan; no forbidden paths; diff size within limit | Change does what the story asks; follows existing patterns and flows; no hidden side effects | **Code**, LLM for intent |
| Unit tests | Tests run and pass; coverage does not drop; mutation testing shows tests fail when code is broken | Tests assert behaviour, not implementation; meaningful names and cases | **Code** |
| Test execution result | Pass and fail counts; flaky-test detection; results linked to ACs | Explains failures and likely root cause | **Code** |
| Release checklist | Every REQ has a passing test; migrations have rollback; version and changelog present | Risk summary is accurate | **Code** |

**Rules that apply to every artifact type**

- Code always runs first; the LLM reviewer is not called if a fact check fails, which saves cost.
- The LLM reviewer is a different call from the generator, with its own context and rubric, ideally a different model.
- Every LLM finding must cite evidence; code drops any finding it cannot verify.
- The final outcome is always decided by code.
- Each rubric has its own eval set, so the reviewer is tested like a skill.

**Ownership.** Japman owns the rules engine, fact checks and evidence verification (code) and the reviewer rubrics, prompts and their eval sets (LLM).

## 13. Data, artifacts and integrations

All work products are typed artifacts stored as files with a traceable envelope; external systems are reached only through MCP under policy.

**Onboarding call flow**

&#91;embedded content: call flow · onboarding a brownfield system\]

Facts come only from scripts (steps 5 to 7); the tech lead adds judgement and signs (step 9). After that, every merge refreshes the facts and fails CI if the pack drifts from the code.

**Core artifact types (first release)**

| Type | Produced by | Consumed by |
| --- | --- | --- |
| `system-card.v1` | `system-context-builder` | Every brownfield skill |
| `engagement-profile.v1` | Architect (greenfield) | Greenfield skills |
| `plan.v1` | Planner | Workflow engine |
| `intent.v1`, `review-report.v1` | `requirement-review`, `intent-cross-check` | Design and story skills |
| `impact-report.v1`, `adr.v1` | `impact-analysis`, `adr-writer` | Build skills, reviewers |
| `story-set.v1`, `test-plan.v1` | `story-writer`, `test-plan-generator` | Build and QA skills |
| `code-change.v1`, `test-result.v1` | `code-change`, verifiers | Harness, reviewers |
| `verification-record.v1` | Harness | Gates, audit, improvement loop |
| `release-checklist.v1`, `defect-triage.v1` | `release-readiness`, `defect-triage` | Release owner, Developer |

**Stores**

| Data | Store | Retention |
| --- | --- | --- |
| Skills, workflows, packs, artifacts | Git repositories | Per client contract |
| Artifact metadata, trace graph, registry index | PostgreSQL (with pgvector for search) | Per client contract |
| Run traces | Langfuse on OpenTelemetry | Per client contract |
| Run state (local) and run events (cloud) | Workflow engine | Per client contract |

**Integrations**

| System | Purpose | Direction |
| --- | --- | --- |
| Jira | Read tickets; write stories after approval | Read and write (gated) |
| Confluence | Read history; publish ADRs and docs after a gate | Read and write (gated) |
| GitHub (or client Git) | Read code; open PRs; send review, CI and merge webhooks | Read and write (gated) |
| Slack | Optional: share open-questions files and run status | Write |
| Company SSO | Sign-in for every entry point | Read |
| Claude (company seats) | All skill and reviewer calls, from the Claude Code desktop app | Outbound |

## 14. Success metrics

The PRD commits to these metrics now; numeric targets are set after pilot teams record their baselines, as the owner decided.

| Goal | Metric | Definition | Target |
| --- | --- | --- | --- |
| G1 Adoption | Weekly active engineers | Distinct engineers with at least one run in the week | Set after baseline |
| G1 Adoption | Skill runs per week | Runs across all entry points | Set after baseline |
| G2 Trust | First-pass acceptance | Share of gated artifacts accepted without edit | Set after baseline |
| G2 Trust | Calibration error | Share of High outputs rejected in audits | Set after baseline |
| G2 Trust | Escaped defects | Defects found after release, versus baseline | Set after baseline |
| G3 Coverage | Systems onboarded | Systems with a current, signed context pack | Set after baseline |
| G4 Root strength | Root-caused rework | Share of downstream rework traced to a Foundation gap | Set after baseline |
| G5 Evidence | Evidence-backed cells | Capability map cells with production skills, evals and real runs | Set after baseline |
| G6 Uplift | Cycle time | Raw requirement to merged change, versus baseline | Set after baseline |
| G7 Improvement | Promoted versions | Skill versions promoted through the improvement loop | Set after baseline |
| Cost | Cost per workflow run | Model plus compute cost | Set after baseline |

**Rules for measurement**

- Each pilot team records time to ready story, rework rate, estimate stability, escaped defects and cycle time before first use.
- No uplift is claimed to anyone until it is measured against that baseline.
- The number of skills is never reported as a success metric.

## 15. Release plan

The product ships in four phases defined by scope, not dates; the first release is the end of Phase 2, when all eight roles and both greenfield and brownfield workflows are live for pilot teams.

&#91;embedded content: release roadmap · 4 phases, 4 gates, no dates\]

A phase starts only when the gate before it passes. G1 is the decisive gate: one brownfield chain running end to end on the reference system with every gate enforced.

| Phase | Scope | Exit gate |
| --- | --- | --- |
| 0 Foundations | Skill spec and first schemas; plugin, hooks and reviewer-subagent spike in the Claude Code desktop app; telemetry event schema; context-pack spec; reference-system scope; catalog model and wireframes; repo, CI, SSO, vault, private marketplace | **G0:** plugin, hooks and subagent proven in the desktop app; spec reviewed; owners named; hosting for cloud services decided |
| 1 Core chain | Workflow runner (run, resume, run state) with type-check and lockfile; harness L0 to L2 with hard gates; six outcomes; open-questions pause and resume; first 8 skills; 3 agents; Node and React verifier containers; Jira and GitHub MCP; `system-context-builder`; reference system; artifact store; tsl CLI and tsl pr; telemetry service with core events; OPA; audit | **G1:** `brownfield-feature` and `defect-triage` run end to end; every hard gate blocks a seeded bad output |
| 2 First release | All 8 agents; `greenfield-architecture` and `greenfield-bootstrap`; L3 judge, signals, bands, autonomy matrix, calibration; Java and Python verifiers; first domain pack; portal, capability map, run-status and skill-performance dashboards, GitHub webhooks, OpenTelemetry usage; PII, injection guard, tenant isolation; pilots on Truminds and consented client code | **G2:** 3 teams using it weekly for 4 consecutive weeks; acceptance and calibration reported per skill; no open security finding |
| 3 Scale | 25 to 40 skills; improvement loop automated to PR; canary and rollback; Tier C verifier; second domain and reference system; pod builder; skills over MCP; client-VPC option | **G3:** measured uplift against baseline on at least 2 metrics; capability map fully evidence-backed |

**Team ownership (current five)**

| Person | Area |
| --- | --- |
| Abhishek | Workflow runner and run state, type-check and lockfile, artifact store, telemetry service and database |
| Shubham | Plugin packaging and hooks, tsl pr, MCP connections, verifier containers, OpenTelemetry and GitHub webhook setup |
| Japman | Harness and knowledge: hard gates, confidence, OPA, evals, context-pack extractors |
| Ekjot | Portal, catalog model, capability map, marketplace install |
| Gaurav | Run-status, usage and skill-performance dashboards; open-questions and PR templates; pod builder UI |

## 16. Assumptions, constraints and dependencies

Each assumption below is unconfirmed until its owner signs it off; anything that turns out false is logged as a change to this PRD.

**Assumptions (to confirm)**

| # | Assumption | How it is confirmed |
| --- | --- | --- |
| A1 | The Claude Code desktop app runs the plugin's skills, hooks and reviewer subagent as designed, and managed settings can enforce them for every engineer | Team spike and readout, then G0 |
| A2 | Engineers will run skills from Claude Code and Cowork, the tools they use today | Pilot usage |
| A3 | Pilot teams can spare time to record a baseline before first use | Agreement with each pilot team |
| A4 | Tech leads will own and sign context packs for their systems | Named owner per pilot system |
| A5 | Clients will give written consent for AI processing of their code | Consent recorded per client |
| A6 | A subject-matter expert is available for the first domain pack | Named person at G1 |

**Constraints**

- Hosting for the Truminds cloud services is not decided; they must stay cloud-neutral until it is. Engineers need company Claude seats.
- Delivery team is five people (2 frontend, 3 backend) today.
- Company SSO for authentication; no custom auth.
- No secrets in code or configuration; encryption at rest; no client data in fixtures.
- Merge, deploy and infrastructure changes always need a human.

**Dependencies**

| Dependency | Needed for | Owner |
| --- | --- | --- |
| Hosting decision for telemetry service and portal | Phase 1 build | Puneet |
| Jira, Confluence, GitHub and Slack access via MCP | Phase 1 | Platform admin |
| Legal review of client consent and AI-use clauses | Pilots on client code (Phase 2) | Legal, via Puneet |
| Three pilot teams with brownfield systems from different domains and stacks | Phase 2 | Puneet |
| Reference system codebase (domain-neutral) | Phase 1 | Delivery team |

## 17. Risks and mitigations

The largest risk is scope: eight roles, two modes and both audiences in the first release with a five-person team.

| Risk | Early signal | Mitigation |
| --- | --- | --- |
| Scope too large for five people | Phase 1 gate keeps slipping | Reuse every product possible; Sales gets a read-only view only; widen roles by skill packs, not new agents |
| Hosting decision delays the telemetry service | No decision at G0 | Service is containerised; events wait in the local outbox until it is live, so skills are not blocked |
| Weak root in real projects | High root-caused rework | Readiness Gate enforced; context pack required for brownfield |
| Context packs go stale | Stale `Verified:` dates | Facts rebuilt in CI; drift fails the build |
| Confidence bands mean nothing | Calibration error rising | Weekly audits; automatic threshold tightening |
| Low adoption | Weekly active engineers flat | Meet engineers in Claude Code and Jira; pilot teams by consent |
| Client code risk | Missing consent record | Platform refuses client code without recorded consent |
| Prompt injection or data leak | Classifier or PII detector hits | Untrusted-input handling, sandboxes, OPA on every tool call |
| Over-claiming to clients | Pilot items in a pod sheet | Only production items shown; gaps list automatic |
| Dependency ownership changes (promptfoo, Langfuse) | Licence or roadmap change | Own formats for evals and traces behind interfaces |
| Model cost overrun | Cost per run rising | Budgets with hard caps per team and run |

## 18. Decisions log and open questions

Every decision below was made or confirmed by the owner; open items have no default and block the gate named.

**Decisions**

| ID | Decision | Status |
| --- | --- | --- |
| D-01 | Reset and re-architect; the September prototype is kept as lessons, not code | Decided |
| D-02 | Truminds builds its own control plane on top of existing products; no re-implementation of what exists | Decided |
| D-03 | Engineers and Sales are served equally; Sales sees a read-only view of engineering evidence | Decided |
| D-04 | Hosting cloud for the Truminds services (telemetry, portal) | **Open** (blocks G0) |
| D-05 | Skills and the reviewer run on Claude through company seats in the Claude Code desktop app; no Claude API is used to run skills | Decided |
| D-06 | Six outcomes: PASS, PASS-WITH-FINDINGS, RETRY, NEEDS-INPUT, ESCALATE, ABORT | Decided |
| D-07 | Confidence is computed by harness rules, never self-reported | Decided |
| D-08 | Sell AI-augmented pods (people plus AI), not AI headcount | Decided |
| D-09 | Domain-agnostic: any brownfield system via its context pack; domain packs optional | Decided |
| D-10 | No calendar timelines; phases are defined by scope and gates | Decided |
| D-11 | First release supports all eight roles | Decided |
| D-12 | First release includes greenfield and brownfield workflows | Decided |
| D-13 | Pilots on Truminds-owned code and on client code with written consent | Decided |
| D-14 | Engineers run workflows locally through the Truminds plugin; hooks run the harness after every skill and send run events to the telemetry service; open questions are answered in a file and fed back with resume | Decided |
| D-15 | Numeric success targets set after pilot baselines | Decided |
| D-16 | Puneet Singh Nanda is the sole approver of this PRD | Decided |
| D-17 | Proposed cloud stack (Backstage, OpenTelemetry collector, PostgreSQL, OPA, promptfoo) | **Pending** team readout |

**Open questions**

| # | Question | Blocks |
| --- | --- | --- |
| Q-01 | Which cloud hosts the Truminds telemetry service and portal? | G0 |
| Q-02 | When is the stack readout held, and does it confirm or change D-17? | G0 |
| Q-03 | Which three pilot teams, systems and domains? | Phase 2 |
| Q-04 | Who is the subject-matter expert for the first domain pack? | Phase 2 |
| Q-05 | What consent wording and AI-use clauses will Legal accept for client code? | Pilots on client code |
| Q-06 | Who are the stage approvers (CODEOWNERS) per lifecycle stage? | First production promotion |
| Q-07 | Who owns the context pack for each pilot system? | Pilot onboarding |
| Q-08 | Run-record retention period, where contracts do not set one | NFR-06 |
| Q-09 | Confirm the proposed NFR limits (availability, gate notice time, run time) | G0 |

## 19. Glossary

| Term | Meaning |
| --- | --- |
| Skill | A folder with `SKILL.md` that does one job and produces one reviewable artifact |
| Agent | A role with a persona, permitted tools, allowed skills and stop conditions |
| Workflow | A versioned chain of skills with gates, retries and branches |
| Pod | An AI-augmented team package: human roles plus agents, workflows and packs |
| Artifact | A typed, versioned output with an envelope of traces and evidence |
| Context pack | A versioned description of one existing system: facts, judgement, links to history |
| Domain pack | Optional industry knowledge: heuristics, checklists, pitfalls, evals |
| Foundation | System Baseline plus Intent Baseline; the root every chain builds on |
| Readiness Gate | The checklist the Foundation must pass before downstream steps run |
| Verifier profile | A container of stack tools that checks artifacts |
| Harness | The rules engine that verifies artifacts and computes confidence and outcome |
| Hard gate | A check that blocks PASS whatever the scores |
| Band | High, Medium or Low confidence, computed from evidence |
| Autonomy matrix | Band x action risk; decides auto-proceed or human gate |
| Human gate | A point where the run pauses for a named person |
| Greenfield / brownfield | New system / change to an existing system |
| MCP | Model Context Protocol; the standard way the AI reaches tools such as Jira and GitHub |
| Eval | A test case with must-do and must-NOT-do checks |
| Maturity | draft, pilot, production, deprecated |
| Reference system | A Truminds-owned, domain-neutral codebase for demos and tests |
