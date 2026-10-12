# Truminds AI Skill Library — Architecture & Implementation Plan

Sep 28, 2026 · @Puneet Singh Nanda

## Executive summary

Truminds will build an AI capability platform: a governed library of skills, agents, workflows and packages that engineers use daily and Sales shows with evidence. Success means three pilot teams using it weekly on real work, and a capability map where every claim is backed by eval results and real runs.

**What we build versus reuse.** We build the thin layer that carries Truminds IP: contracts, harness rules, verifiers, context and domain packs, workflow templates, the improvement loop and two portal plugins. We reuse proven open standards and products for everything else: the agent runtime, workflow engine, tools protocol, gateway, tracing, evals and portal.

**Decisions locked in this plan**

| # | Decision |
| --- | --- |
| D1 | Reset and re-architect; the September prototype is kept as evidence and lessons, not as code |
| D2 | Seven-object model: Skill, Agent, Workflow, Package, Knowledge Pack, Artifact, Verifier |
| D3 | Build the control plane; reuse executors, MCP and the SKILL.md standard |
| D4 | The workflow engine executes, the planner only proposes, the harness decides the outcome |
| D5 | Confidence is computed from evidence (hard gates, signals, bands) and calibrated by human audit, never self-reported |
| D6 | Six outcomes: PASS, PASS-WITH-FINDINGS, RETRY, NEEDS-INPUT, ESCALATE, ABORT |
| D7 | The Foundation (System Baseline + Intent Baseline) must pass a Readiness Gate before any downstream step |
| D8 | A context pack is required for brownfield work; without it, confidence is capped at Medium |
| D9 | Verifier profiles are defined when a stack is onboarded; no verifier means no capability claim |
| D10 | Self-improvement proposes changes as PRs; promotion is never automatic |
| D11 | One distribution backbone, six entry points; multi-step workflows run on the platform |
| D12 | Sell AI-augmented pods (people plus AI), built by a registry resolver into a pinned manifest |
| D13 | Domain-agnostic: any brownfield system is onboarded through its context pack; domain packs are optional add-ons chosen per engagement |
| D14 | Only production-maturity items are shown to clients as capability |

## Design principles and object model

Ten principles govern every design choice below; any component that breaks one is redesigned, not excused.

1. **Skill first.** One skill produces one artifact a human would review as a unit.
2. **Artifacts, not conversation.** Skills hand off typed, versioned files, never chat history.
3. **Evidence over confidence.** The harness computes confidence; a model never grades itself.
4. **Deterministic process, probabilistic steps.** Code runs the workflow; LLMs do the steps inside it.
5. **Strong root.** Nothing runs downstream of an unready Foundation.
6. **Humans at the cost jumps.** Gates sit where an error becomes expensive, not after every step.
7. **No verifier, no claim.** A stack or domain is advertised only where outputs can be checked.
8. **Reuse standards.** SKILL.md, MCP and existing products before anything we write.
9. **Improve by PR.** Every change to a skill is proposed, evaluated and approved.
10. **Usage, not count.** Report skills used per week and measured uplift, never the number of skills.

&#91;embedded content: object model · seven objects and how they relate\]

The skill is the unit of reuse. Agents decide who may run it, workflows decide when, knowledge packs ground it, and verifiers check what it produces.

## Reference architecture

The platform is five planes plus an improvement loop that runs across them; Truminds builds something in every plane: most of the Capability and Knowledge planes (the IP), the rules and logic of the Control plane, and thin layers on Experience and Execution, which mostly reuse existing products.

&#91;embedded content: reference architecture · five planes, one improvement loop, cross-cutting governance\]

Each plane calls the one below it. The improvement loop reads signals from the control and execution planes and proposes changes to capability and knowledge.

| Plane | Responsibility | Built by Truminds | Reused |
| --- | --- | --- | --- |
| Experience | Discover, run, sell | Capability map and pod builder plugins, `tsl` CLI | Backstage, IDE agents, plugin marketplaces, Jira/GitHub/Slack |
| Capability | What the AI can do | Skills, agents, workflow templates, pod manifests, artifact schemas | SKILL.md format, JSON Schema |
| Control | Decide what runs and whether it passed | Planner prompt, harness rules, confidence calculator, gate policies | Temporal, OPA |
| Execution | Do the work | Executor interface, verifier images | Claude Agent SDK, LiteLLM, MCP servers, containers |
| Knowledge and data | Ground the work, store results | Context and domain packs, eval sets, reference systems, trace schema | Git, Postgres with pgvector, Langfuse |

## End-to-end flow

A brownfield feature passes through eight stages; humans act at five gates and the platform does the rest. The worked example is a feature request on an existing system: "Show 30 days of order history." The same flow applies to any stack or domain.

&#91;embedded content: end-to-end flow · 8 stages, 5 human gates\]

At stage 2 the cross-check finds that the data model keeps order history for only 24 hours. The run stops with NEEDS-INPUT, the product owner decides, and only then does design start. That conflict is caught before any code exists, which is the point of the Foundation.

**What happens on each outcome at any stage**

| Outcome | Engine action |
| --- | --- |
| PASS | Next step starts; auto-proceed only where the autonomy matrix allows |
| PASS-WITH-FINDINGS | Next step starts; findings travel in the artifact's open items |
| RETRY | Same step re-runs with the failure as input, at most 2 retries (3 for the build fix loop) |
| NEEDS-INPUT | Run pauses; the named owner of each open item is notified in Jira or Slack |
| ESCALATE | Run pauses; the tech lead decides to resume, change scope or stop |
| ABORT | Run stops; the requester and tech lead are notified with the reason |

## The Foundation: making the root strong

The root of every chain is the **Foundation**: a System Baseline (what exists) plus an Intent Baseline (what is wanted), both human-signed and frozen before any downstream skill runs. Errors multiply along a chain (five steps at 90% each give about 59% end to end), so this is where human attention pays most.

&#91;embedded content: Foundation construction · two tracks, one gate, one amendment loop\]

The two tracks run in parallel and join at the Readiness Gate. A failed gate sends named questions to owners; a downstream discovery re-baselines the root instead of being worked around.

**Nine rules for the root**

| # | Rule | Failure it prevents |
| --- | --- | --- |
| R1 | Separate by provenance: facts extracted by scripts, judgement written by humans, history queried live | Stale or invented facts |
| R2 | Every claim cites a source (file and line, schema, ADR, ticket); uncited claims become assumptions | Invented facts |
| R3 | Known, Assumed and Unknown are explicit sections; every unknown has an owner | Silent gaps |
| R4 | Atomic numbered items (REQ-001, AC-001.2), each confirmed, proposed default or open | Ambiguity, scope drift |
| R5 | Findings typed as decision, verify, gap-default or question; only a decision may block; defaults never enter an AC unconfirmed | Hidden decisions |
| R6 | Challenge before sign-off: two independent extractions compared, intent cross-checked against the system | Ambiguity, conflicts |
| R7 | Just-enough context: system card always, touched components next, deep files on demand | Noise, token cost |
| R8 | Freeze and version: baseline ID and hash; changes create a new baseline and mark affected work stale | Scope drift |
| R9 | Downstream discoveries raise a root amendment | Recurring gaps |

**Readiness Gate criteria (all must hold)**

- System card verified within 90 days; generated facts rebuilt at the current commit
- Every component the intent touches is present in the context pack
- Zero open `decision` blockers on in-scope items
- Every REQ has at least one testable AC or a named open question
- NFRs stated, or marked "house default proposed"
- The intent-versus-system cross-check has no unresolved conflict
- Signed by named roles: product owner for intent, tech lead for system

**Greenfield variant.** There is no system to extract, so the root is Intent plus Constraints, the Domain Pack and an Engagement Profile (stack, NFRs, compliance). It grows in stages: Intent Baseline, then an Architecture Baseline of approved ADRs, then build.

**Measuring root strength.** Track *root-caused rework*: the share of downstream NEEDS-INPUT outcomes and rework traced to a gap in the Foundation. It is reported per project and per skill every week.

## Skill chaining

Skills never talk to each other; each writes a typed artifact, the harness checks it, and the workflow engine hands references to the next skill.

&#91;embedded content: skill chaining · design-time type check, run-time harness, invalidation\]

Bad chains fail at design time, before any run. Bad outputs fail at the harness, before the next skill sees them.

**Skill contract (in SKILL.md frontmatter under `metadata.truminds`)**

| Field | Purpose |
| --- | --- |
| `inputs` / `outputs` | Artifact types with version ranges, for example `intent.v1`, `story-set.v1` |
| `preconditions` | What must be true before running (Foundation baselined, pack fresh) |
| `postconditions` | What the output guarantees (every story traces to a REQ) |
| `verification_level` | Minimum ladder level L0 to L4 the output must reach |
| `verifier_profile` | Required profile, or `any` for text-only artifacts |
| `human_gate` | none, review-before-write or approval-required |
| `allowed_tools` | MCP tools the skill may call; enforced by the policy engine |
| `context_needs` | Which pack sections to load, keeping context small |

**Core artifact types for v1:** `plan.v1`, `system-card.v1`, `intent.v1`, `review-report.v1`, `impact-report.v1`, `adr.v1`, `story-set.v1`, `test-plan.v1`, `code-change.v1`, `test-result.v1`, `verification-record.v1`, `release-checklist.v1`, `defect-triage.v1`. Each is a JSON Schema in the type registry.

**Artifact envelope**

```yaml
artifact_id: ART-8812
type: story-set.v1
produced_by: story-writer@1.2.0
run_id: RUN-2031
foundation_baseline: FND-order-history@v1   # plus content hash
inputs: [ART-8807]                          # exact upstream versions, with hashes
traces: [REQ-001, REQ-002]
open_items: [{id: Q-4, owner: product-owner}]
verification: {level: L3, hard_gates: pass, coverage: 0.94, judge: 4.4}
confidence: high
outcome: PASS
status: current                             # current | stale | superseded
```

**Workflow definition (engine-neutral YAML, compiled to the engine)**

```yaml
workflow: brownfield-feature
version: 2.1.0
lockfile: brownfield-feature.lock            # exact skill versions
steps:
  - id: review
    skill: requirement-review@^1.1
    gate: foundation-readiness
  - id: impact
    skill: impact-analysis@^1.0
    needs: [review]
    gate: design
  - id: stories
    skill: story-writer@^1.2
    needs: [impact]
  - id: tests
    skill: test-plan-generator@^1.0
    needs: [stories]
  - id: code
    skill: code-change@^1.0
    needs: [stories]
    loop: {until: verifier.pass, max: 3}
  - id: judge
    skill: verification-review@^1.0
    needs: [tests, code]
    gate: pr-review
on_outcome:
  RETRY: {max: 2, then: ESCALATE}
  NEEDS-INPUT: {notify: owners_of(open_items), pause: true}
  ESCALATE: {notify: tech_lead, pause: true}
  ABORT: {notify: [tech_lead, requester]}
```

**Run-time rules**

- Steps with no dependency between them run in parallel (`tests` and `code` above) and join before `judge`.
- A skill receives artifact references plus only the context sections it declared, never the full history.
- Every external write is dry-run first and carries an idempotency key, so a retry never duplicates a ticket or commit.
- A paused run resumes from the last passed step; completed steps are never re-executed.

## Harness: verification, confidence rules and outcomes

The harness is a rules engine that turns evidence into a confidence band and one of six outcomes; the generating model never scores its own work.

&#91;embedded content: harness decision flow · ladder, hard gates, signals, band, autonomy, calibration\]

Hard gates are checked first and cannot be outweighed by good scores. Only an artifact that passes them, with no open decisions, gets a band.

**Verification ladder.** Each artifact type declares its minimum level in the type registry.

| Level | What runs | Example |
| --- | --- | --- |
| L0 Schema | JSON Schema validation, required sections | `story-set.v1` has IDs, traces, Known/Assumed/Unknown |
| L1 Deterministic | The verifier profile: compile, tests, lint, SAST, contract and rule checks | Jest passes, Semgrep clean, OpenAPI diff has no breaking change |
| L2 Grounding | Every claim resolves to a cited source in the pack, repo or spec | "Retention is 24 h" cites `data-model.md` line 40 |
| L3 Independent judge | Rubric review with a separate context, ideally a different model | Scores 1 to 5 per rubric item, must-NOT-do list checked |
| L4 Human | A named person approves at a gate | Tech lead approves the design |

**Tier 1: hard gates (any failure blocks PASS)**

| Rule | Check | On failure |
| --- | --- | --- |
| H1 | Artifact validates against its schema | RETRY |
| H2 | Required sections present, including Known / Assumed / Unknown | RETRY |
| H3 | Verifier profile checks pass | RETRY (fix loop), then ESCALATE |
| H4 | No forbidden content: invented values in an AC, secrets, PII, client names | ABORT for secrets or PII; RETRY for invented values |
| H5 | Trace links to Foundation items present and resolving | RETRY |
| H6 | All input artifacts are `current`, not stale | Re-run upstream branch |
| H7 | Only permitted tools were called (policy engine log) | ABORT |

**Tier 2: scored signals**

| Signal | Measure | High needs |
| --- | --- | --- |
| S1 Evidence coverage | Share of claims with a resolving citation | 90% or more |
| S2 Check pass rate | Share of verifier checks passed, beyond the hard-gate minimum | 100% |
| S3 Judge score | Mean rubric score from the independent judge | 4.0 of 5 or more |
| S4 Open blockers | Count of open `decision` items | 0 |
| S5 Context completeness | Declared context sections present and fresh | All |
| S6 Change risk | Diff size, files touched, sensitive paths | Below the skill's risk limit |

**Tier 3: bands.** High = every Tier 2 threshold met. Medium = hard gates pass, S4 = 0, S5 complete, one or more other signals below threshold. Low = anything else that passed hard gates. No context pack caps any output at Medium. The starting thresholds above are proposals; pilot data sets the real ones per skill.

**Autonomy matrix (band x action risk)**

| Action | High | Medium | Low |
| --- | --- | --- | --- |
| Draft artifact, read-only | Auto-proceed | Proceed, findings flagged | Human review |
| Write to Jira or Confluence | Review before write | Review before write | Human rewrite |
| Open a pull request | Open for review | Open as draft | Human decides |
| Merge, deploy, change infrastructure | Always human | Always human | Always human |

**Calibration** makes the bands mean something. Each week humans audit a random 10% of High outputs per skill. If more than 5% are rejected, that skill's thresholds tighten and it drops one autonomy column until the rate recovers.

## Verifier profiles

A verifier profile is a versioned container image plus a check list for one stack; a stack without one cannot be advertised or reach `pilot` maturity.

**When verifiers are decided (never mid-run)**

1. **Stack onboarding.** The profile is built and tested on a reference repo before any skill targets that stack.
2. **Project onboarding.** The context pack declares the project's stacks; profiles are resolved and a missing one is flagged then.
3. **Workflow pre-flight.** The engine confirms each step's required ladder level can be met in this environment.

**Tiers**

| Tier | When it applies | Example checks | If unavailable |
| --- | --- | --- | --- |
| A Generic | Standard toolchains that run in a container | Compile, unit tests (Jest, JUnit, pytest), lint, Semgrep, gitleaks, Trivy | Not allowed; Tier A is mandatory |
| B Stack-specific | Needs an emulator, cluster or contract environment | Android or iOS emulator, a local Kubernetes cluster (kind), Pact contract tests, Schemathesis API tests, Playwright | Confidence capped at Medium |
| C Special | Needs hardware, RF, protocol conformance, real-time behaviour or a regulated standard | Embedded: cross-compile, MISRA checks, [Renode](https://antmicro.com/blog/2024/10/renode-github-action-for-automated-testing-in-simulation) or QEMU simulation, hardware-in-the-loop rig; telecom protocol testers; network and radio conformance labs; safety-standard toolchains | Capped at Medium plus a mandatory human check in place of the verifier |

**Profile manifest (example)**

```yaml
profile: node-20-service
version: 1.3.0
image: registry.truminds.internal/verifiers/node20@sha256:...
tier: A
checks:
  - {id: build,    cmd: "npm ci && npm run build",    blocking: true}
  - {id: unit,     cmd: "npm test -- --ci",            blocking: true}
  - {id: lint,     cmd: "npx eslint .",                blocking: true}
  - {id: sast,     cmd: "semgrep --config auto",       blocking: true}
  - {id: secrets,  cmd: "gitleaks detect",            blocking: true}
  - {id: coverage, cmd: "npm run coverage", threshold: "no drop vs main", blocking: false}
sandbox: {network: deny-by-default, cpu: 2, memory: 4Gi, timeout: 15m}
```

First profiles to build, in order: Node 20 service, React web, Java 21 service, Python 3.12, then one Tier C embedded C profile for the embedded pilot.

## Knowledge plane: context packs, domain packs, reference systems

Three kinds of knowledge ground every skill: a context pack describes one system, a domain pack describes one industry, and a reference system is a safe codebase to demo and test on.

**Context pack (one per system, lives in that system's repo).** It is a prerequisite for brownfield work, not for the library itself. The library ships the spec and `system-context-builder`; each project builds its pack during onboarding, owned by that product's tech lead.

| Class | Examples | Rule | Refresh |
| --- | --- | --- | --- |
| Facts | Services, DB schema, endpoints, dependencies, build and deploy manifests | Extracted by scripts into `generated/`; never hand-typed | Every merge, in CI; drift fails the build |
| Judgement | Why components exist, ownership, known quirks, ADRs | Written by the tech lead, reviewed in a PR; carries `Owner:` and `Verified:` | Quarterly and on every ADR |
| History | What past tickets concluded | Never stored; queried live through Jira or Confluence MCP | Every run |

```
context/<system>/
  system-card.md     always loaded, about one page
  glossary.md
  architecture.md
  data-model.md      entities, lifecycles, retention
  api-surface.md
  constraints.md
  known-quirks.md
  decisions/         ADRs
  generated/         DO NOT EDIT: services.json, schema.json, endpoints.json
```

**Domain pack (one per industry).** It is the experienced engineer's knowledge written down, plus an exam that proves it works.

&#91;embedded content: domain pack harvest · two sources, one proof loop\]

A heuristic without an eval case is not accepted into the pack. The lift measurement is what Sales shows: the same skill scored on the same exam with and without the pack.

```
domain-packs/<domain>/   e.g. telecom, embedded, iot, payments, healthcare, networking
  glossary.md        domain terms and acronyms
  heuristics.md      rules of thumb experts apply ("if X, always check Y")
  checklists/        what a complete requirement or design must cover in this domain
  known-pitfalls.md  recurring failure causes from past projects
  examples/          good reference artifacts
  verifiers/         domain-specific checks (protocol, compliance, safety)
  evals/             30 to 100 cases, each with must-do and must-NOT-do
```

A domain pack is optional. Any brownfield system can run every workflow with only its context pack; a domain pack adds expert judgement where the engagement needs it.

**Reference systems (one per domain).** A Truminds-owned, sanitised codebase with its own context pack, used for demos, pilot runs and eval corpora. It never contains client code or client data. The first is domain-neutral: a small multi-service application (web UI, REST API, two services, a relational database and CI) that looks like typical client brownfield code. Domain-specific reference systems are added only when a domain pack is built.

## Self-improvement loop

The library improves from its own usage, but every change is a pull request that must beat the current version on evals and be approved by the skill's owner.

&#91;embedded content: improvement loop · 7 steps, 1 rollback path\]

A failing case always becomes a new eval case first, so the same failure cannot silently return. The holdout set is never visible to the improver agent, which stops it from gaming the evals.

**Signals captured on every run**

| Signal | Source | Used for |
| --- | --- | --- |
| Gate decision (accept, edit, reject) and reason code | Human gates | First-pass acceptance rate |
| Diff of the human edit | Artifact store | What the skill keeps getting wrong |
| Retries and hard-gate failures | Harness | Brittle procedures, weak verifiers |
| Downstream rework traced upstream | Trace graph | Which skill caused the problem |
| Calibration audit results | Weekly audit | Threshold tuning |
| Cost and latency | Tracing, gateway | Budget regressions |

**What the same loop improves**

- **Skills:** procedure changes, new references, new house defaults.
- **Domain packs:** heuristics harvested from expert edits.
- **Context packs:** root amendments from downstream discoveries.
- **Workflows:** a gate that never rejects is a candidate to automate; a gate that always rejects means the step before it is broken.
- **Harness thresholds:** through calibration.

**Guardrails**

- Promotion is never automatic; the owner approves every version.
- A PR must improve the target cluster, show no regression on any must-NOT-do rule, and stay within cost and latency budgets.
- Canary runs one week on one pilot team or 10% of runs before promotion.
- Rollback is a version-pin change and takes minutes.

**Worked example.** Reviewers keep adding a pagination criterion to `story-writer` output. The weekly job clusters those edits; the improver adds a proposed default ("paginate above 100 rows") and three eval cases; evals pass; the owner approves; after a week's canary the edit rate falls and v1.3.0 is promoted.

## Entry points and distribution

Engineers never download skill ZIPs: every entry point installs from one registry, stays on a pinned version channel, and reports usage back.

&#91;embedded content: distribution backbone · one source, six entry points, one telemetry stream\]

Single skills run locally in the engineer's tool. Multi-step workflows with gates run on the platform, because only there can the harness, audit trail and resumability be guaranteed.

**Why no separate adapters are needed any more.** The Agent Skills format is now read natively by Claude Code, GitHub Copilot, VS Code, Cursor, Codex and Gemini CLI, among others ([agentskills.io](https://agentskills.io/home)). The build therefore ships the same SKILL.md folders everywhere and only packages them differently (a Claude Code plugin, a repo `.github/skills` folder). Organisation-wide distribution uses a private [plugin marketplace](https://code.claude.com/docs/en/plugin-marketplaces) that an administrator can require on every machine.

**Engineer onboarding flow**

1. Sign in to the Backstage portal with company SSO.
2. Choose role (Developer, QA, Architect, DevOps, Delivery) and project.
3. The portal recommends a role pack and shows the project's context pack status.
4. One command installs the pack and links the project's context pack.
5. A guided first run on the reference system, then a first run on a real ticket.

**Sales and pre-sales experience.** The capability map is a Backstage plugin that reads only registry data: domain x lifecycle stage, each cell showing production skills, eval results, lift over a generic model, real-run count and a link to a replay on the reference system. Cells without evidence show as roadmap. The pod builder (next section) sits beside it.

## AI-augmented pod packaging

Truminds sells pods of people made faster by AI, never AI agents as headcount; the pod builder turns a client ask into a pinned manifest in minutes.

&#91;embedded content: pod builder · ask, resolver, manifest, four outputs\]

The resolver only picks items that exist in the registry. Anything below `production` maturity lands in the gaps list and is never shown to the client as capability.

**Pod manifest (example)**

```yaml
pod: brownfield-feature-pod
version: 1.0.0
humans: {solution-architect: 1, fullstack-dev: 1, qa: 1}
autonomy: L2        # L1 assist | L2 draft and review | L3 execute with gates
roles:
  solution-architect:
    agent: architecture-agent@1.x
    skills: [impact-analysis@1.2, adr-writer@1.0, nfr-review@1.1]
  fullstack-dev:
    agent: developer-agent@1.x
    skills: [code-change@1.0, unit-test-gen@1.3, code-review@1.1]
    verifiers: [node-20-service@1.3, react-web@1.1]   # resolved from the client's stack
  qa:
    agent: quality-agent@1.x
    skills: [test-plan-generator@1.2, api-test-gen@1.0]
context_pack: required                        # built for the client's system in onboarding
domain_packs: []                              # optional, e.g. [payments@1.0] or [telecom@1.0]
workflows: [brownfield-feature@2.1, defect-triage@1.0]
integrations: [jira, confluence, github]      # MCP servers
deployment: truminds-hosted                   # or client-vpc
onboarding: [build-context-pack, capture-baseline-metrics]
evidence: registry://pods/brownfield-feature-pod/evidence
gaps: [api-test-gen (pilot): excluded from client claims]
```

**Pod lifecycle**

| Stage | What happens | Owner |
| --- | --- | --- |
| Pre-sales | Pod sheet and a replay on the reference system | Pre-sales lead |
| Onboarding | Context pack built; baseline metrics captured before AI use | Delivery tech lead |
| Delivery | Workflows run under the manifest's autonomy level | Pod lead |
| Monthly | Uplift report from telemetry against the baseline | Delivery manager |
| Renewal | Evidence-backed review; autonomy level raised only if calibration holds | Account owner |

**Eight standard agents (roles):** Requirements Analyst, Solution Architect, Developer, Quality Engineer, DevOps Engineer, Security Reviewer, UX Designer, Delivery Manager. Each holds 3 to 10 skills; Mobile, Data and domain specialisms are skill packs on these agents, not new agents.

## Security, governance, legal and cost controls

Every ticket, repo and document the platform reads is treated as untrusted input, and every write is permissioned, logged and reversible.

| Area | Control | Implemented with |
| --- | --- | --- |
| Identity | Company SSO for portal, CLI and platform; no custom auth; roles per project | Company IdP (OIDC), Backstage auth |
| Authorisation | Tool permissions per agent and skill; autonomy matrix as policy code | OPA policies checked before every tool call |
| Tenant isolation | One namespace, artifact store prefix and context pack per client; no cross-client retrieval | Kubernetes namespaces, per-tenant DB schemas |
| Secrets | Never in prompts, context packs or repos; short-lived tokens injected into sandboxes | Secrets vault, gitleaks in CI and in H4 |
| Data protection | PII detected and masked before model calls; encryption at rest and in transit | Microsoft Presidio, platform encryption |
| Prompt injection | Ticket and repo text wrapped as data; injection classifier on inputs; tools limited by policy | Classifier, OPA, sandbox network deny-by-default |
| Sandboxing | Generated code runs only in isolated containers with no production credentials | Kubernetes jobs, verifier images |
| Fixtures and demos | No client code or client data in evals, fixtures or reference systems | CI scanner, review checklist |
| Audit | Every run records inputs, versions, model, tools, outputs, verification and human decisions | Temporal history, Langfuse traces, audit log |
| Model governance | Approved model list per client; client may require its own model endpoint | LiteLLM model allowlists |
| Cost | Budget per team, project and workflow run; hard stop at the cap | LiteLLM budgets and rate limits |

**Legal and commercial (to agree with Legal before the first client pod)**

- Ownership of AI-generated code and documents under each contract; default is that it belongs to the client like any other deliverable.
- Disclosure clause stating where AI is used and which human gates apply.
- Model and data-residency terms per client (for example, no data leaves the client's region).
- Open-source licence scanning on generated code before merge.

**Governance roles**

| Role | Responsibility |
| --- | --- |
| Platform owner | Roadmap, standards, the spec and the harness rules |
| Skill owner (named person per skill) | Quality, evals, approving every new version |
| Stage approver (per lifecycle stage) | Promotes skills to `production` in that stage (CODEOWNERS) |
| Context pack owner (tech lead per system) | Accuracy and freshness of the pack |
| Security reviewer | Reviews any skill that writes, deploys or touches credentials |

## Versioning plan

Everything that can change a run's result is versioned, and every run records the exact versions it used, so any run can be replayed.

| Object | Scheme | Major change means | Where the version lives |
| --- | --- | --- | --- |
| Skill | Semver | Inputs or outputs change (minor: procedure; patch: wording) | `metadata.truminds.version` in SKILL.md |
| Artifact type | `name.vN` | Any breaking schema change | Type registry; skills declare accepted ranges |
| Workflow | Semver plus lockfile | Steps, gates or order change | Workflow YAML and `.lock` of exact skill versions |
| Agent | Semver | Permitted tools or skills change | Agent YAML |
| Domain pack | Semver | Heuristics removed or reversed | Pack manifest |
| Context pack | Baseline ID plus content hash | Any approved change | Pack repo tag; recorded in every artifact |
| Verifier profile | Semver plus image digest | Check removed or threshold loosened | Profile manifest |
| Harness rules and thresholds | Semver | A gate added or removed | Rules repo; recorded per run |
| Model | Provider model ID, pinned | Any change | Gateway config; recorded per run |
| Pod | Semver | Any pinned item changes major version | Pod manifest |

**Channels and lifecycle.** Skills move `draft` to `pilot` to `production` to `deprecated`. Distribution channels are `beta` (pilot and above) and `stable` (production only). A deprecated major version stays supported for 90 days after its replacement reaches production.

**Rules**

- A running workflow never picks up a new skill version; only a new run with a new lockfile does.
- Promotion to `production` needs evals passing, a named owner, a stage approver's sign-off and a completed pilot period with telemetry.
- The run record stores every version above; replaying a run uses the same pins.

## Technology stack: reuse versus build

Every component below is an existing standard or product except the Truminds IP layer; each pick was checked against its primary source in September 2026, and two ownership changes were found that shape the plan.

| Component | Pick | Alternatives | Verified fact behind the pick |
| --- | --- | --- | --- |
| Skill format | [Agent Skills (SKILL.md)](https://agentskills.io/home) | None comparable | Open standard originated by Anthropic; read natively by Claude Code, Copilot, VS Code, Cursor, Codex, Gemini CLI and others |
| Tool access | [MCP](https://blog.modelcontextprotocol.io/posts/2025-12-09-mcp-joins-agentic-ai-foundation/) | Direct APIs | Donated to the Linux Foundation's Agentic AI Foundation on 9 December 2025; vendor-neutral governance |
| Agent executor | [Claude Agent SDK](https://code.claude.com/docs/en/agent-sdk/skills) | OpenAI Agents SDK, Google ADK, Microsoft Agent Framework | Loads SKILL.md from the filesystem; a `skills` allowlist limits which skills a session may invoke, matching our per-agent permissions |
| Workflow engine | [Temporal](https://docs.temporal.io/ai-cookbook/human-in-the-loop-python) | LangGraph, GitHub Actions | Signals plus wait conditions hold a run for hours or days at a human gate with no compute used, and survive infrastructure failure |
| Model gateway | [LiteLLM proxy](https://docs.litellm.ai/docs/proxy/users) | Portkey, cloud gateways | Budgets and TPM/RPM limits per key, user and team; self-hosted |
| Policy | [Open Policy Agent](https://www.cncf.io/projects/open-policy-agent-opa/) | Custom code | CNCF graduated project since 29 January 2021 |
| Portal and catalogue | [Backstage](https://www.cncf.io/blog/2022/03/15/backstage-project-joins-the-cncf-incubator/) | Custom portal | CNCF incubating project since 15 March 2022; catalogue and plugin model fit skills, agents and pods |
| Tracing | [Langfuse](https://langfuse.com/blog/joining-clickhouse), on OpenTelemetry | Arize Phoenix | **Now owned by ClickHouse**; stays open source and self-hostable with no licensing change planned |
| Evals | [promptfoo](https://qaskills.sh/blog/openai-promptfoo-acquisition-explained-2026) runner | DeepEval, Inspect AI | **OpenAI agreed to acquire it on 9 March 2026**; remains MIT and multi-provider by stated intent only |
| Embedded simulation | [Renode](https://antmicro.com/blog/2024/10/renode-github-action-for-automated-testing-in-simulation) | QEMU | Runs firmware tests in CI without hardware, with a GitHub Action |
| Distribution | [Claude Code plugin marketplace](https://code.claude.com/docs/en/plugin-marketplaces) | Repo skill folders | A private git repo with `marketplace.json`; administrators can require it on every machine |
| PII masking | Microsoft Presidio | Cloud DLP services | Open-source PII detection and anonymisation |
| Store | Git plus PostgreSQL with pgvector | Object store, OpenSearch | Artifacts diffable and reviewable as files; one database for metadata, traces and search |

**How the two ownership changes shape the plan.** Eval cases are stored in our own format and converted to the runner's config at build time, so promptfoo can be swapped for DeepEval or Inspect AI in a day. Langfuse is used only through OpenTelemetry, so the trace backend can change without touching skills.

**What Truminds builds (the IP layer).** Artifact type registry and envelope; workflow templates and the YAML-to-Temporal compiler; harness rules and confidence calculator; verifier profiles; context-pack spec and `system-context-builder`; domain packs and eval sets; reference systems; improvement jobs; Backstage plugins for the capability map and pod builder; the `tsl` CLI.

## Metrics and observability

Success is measured by weekly usage and measured uplift against a pre-rollout baseline, never by the number of skills.

| Group | Metric | Definition | Reviewed |
| --- | --- | --- | --- |
| Adoption | Weekly active engineers | Distinct engineers with at least one run in the week | Weekly |
| Adoption | Skill runs per week | Runs across all entry points | Weekly |
| Quality | First-pass acceptance | Share of gated artifacts accepted without edit | Weekly, per skill |
| Quality | Root-caused rework | Share of downstream rework traced to a Foundation gap | Weekly, per project |
| Quality | Calibration error | Share of High outputs rejected in the audit | Weekly, per skill |
| Reliability | Workflow completion rate | Runs reaching release without ABORT | Weekly |
| Reliability | Human intervention rate | NEEDS-INPUT plus ESCALATE per 100 steps | Weekly |
| Uplift | Time to ready story | Raw requirement to Foundation baseline, versus baseline | Monthly |
| Uplift | Escaped defects | Defects found after release, versus baseline | Monthly |
| Cost | Cost per workflow run | Model plus compute cost from gateway and cluster | Weekly |
| Evidence | Production skills per capability cell | Count backing each map cell | Monthly |

**Baseline first.** Pilot teams record time-to-story, rework rate, estimate stability and escaped defects for a baseline period before first use; without it no uplift can be claimed.

**Tracing.** Every run is one trace: planner, each step, each tool call, each check and each human decision are spans, linked by `run_id` and `artifact_id`. Traces feed the audit log, the improvement loop and the capability map.

## Implementation plan

The build runs in four phases, each ending at a gate with written exit criteria; a phase starts only when the gate before it passes. Phases are defined by scope, not by dates.

### Phase 0: Foundations

Goal: agree the contracts and prove each reused component works before any skill is written.

| Plane | Modules built or decided |
| --- | --- |
| Capability | Skill Spec v1 (frontmatter under `metadata.truminds`); artifact type registry with first 5 JSON Schemas (`plan`, `intent`, `review-report`, `story-set`, `verification-record`) |
| Control | Workflow engine chosen (Temporal or LangGraph) from a spike; a sample workflow that pauses at a human gate and resumes on approval |
| Execution | Agent SDK executor spike: one skill run headless through the LiteLLM gateway inside a container |
| Knowledge | Context-pack spec (facts, judgement, history); scope of the domain-neutral reference system |
| Experience | Catalog model for skills, agents, workflows and pods in Backstage; wireframes for portal, gate approval and run views |
| Cross-cutting | Repo, CI skeleton, company SSO wiring, secrets vault, private plugin marketplace |

**Exit gate G0:** stack confirmed or swapped per component; spec reviewed by 3 tech leads; owners named for every module.

### Phase 1: Core chain

Goal: one brownfield chain works end to end on the reference system with every gate enforced.

| Plane | Modules built |
| --- | --- |
| Capability | First 8 skills (1 to 8 in the table below); 3 agents: Requirements Analyst, Developer, Quality Engineer |
| Control | YAML-to-engine workflow compiler with type-check and lockfile; harness L0 to L2 with hard gates H1 to H7; six outcomes; human gates; planner v1 (template matching only) |
| Execution | Sandboxed runner; Node and React verifier profiles; Jira and GitHub MCP connections; dry-run and idempotent writes |
| Knowledge | `system-context-builder` (fact extractors for OpenAPI, DB schema, dependencies, manifests); reference system with its context pack; artifact and trace store (Git plus Postgres) |
| Experience | `tsl` CLI (`init-context`, `run`, `verify`); gate approval view; run timeline view |
| Cross-cutting | OPA tool-permission policies; audit log; secrets injected into sandboxes only |

**Exit gate G1:** `brownfield-feature` and `defect-triage` run end to end on the reference system with all gates; every hard gate demonstrably blocks a seeded bad output.

### Phase 2: Pilots

Goal: three real teams use the platform weekly and the confidence bands are calibrated on real work.

| Plane | Modules built |
| --- | --- |
| Capability | Skills 9 to 12; all 8 agents; workflows `brownfield-feature` and `defect-triage` promoted to pilot |
| Control | Harness L3 independent judge; signals S1 to S6; confidence bands; autonomy matrix; weekly calibration audits; improvement loop run by hand |
| Execution | Java and Python verifier profiles; budgets and rate limits per team; Confluence and Slack MCP |
| Knowledge | First domain pack (the first pilot team's domain) with eval set; context packs for the three pilot systems; baseline metrics captured before first use |
| Experience | Backstage portal live; capability map plugin (read-only); marketplace install flow; Jira label and PR comment triggers |
| Cross-cutting | PII masking; prompt-injection guard; tenant isolation per client |

**Exit gate G2:** 3 teams using it weekly for 4 consecutive weeks; first-pass acceptance and calibration error reported per skill; no open security finding.

### Phase 3: Scale

Goal: widen skills and domains, and make the platform sellable as AI-augmented pods.

| Plane | Modules built |
| --- | --- |
| Capability | 25 to 40 skills; 10 or more promoted to `production`; pod manifests |
| Control | Improvement loop automated up to the PR; canary and rollback; planner v2 (proposes workflows for unmatched requests, human-approved) |
| Execution | First Tier C verifier (embedded C with Renode); model routing by skill |
| Knowledge | Second domain pack; second reference system |
| Experience | Pod builder plugin; skills served over MCP; demo replay viewer for Sales |
| Cross-cutting | Client-VPC deployment option; legal clauses in contracts; security review for all write skills |

**Exit gate G3:** measured uplift against baseline on at least 2 metrics; the capability map shows only evidence-backed cells.

**First 12 skills, in build order**

| # | Skill | Stage | Mode | Phase |
| --- | --- | --- | --- | --- |
| 1 | `system-context-builder` | discovery | brownfield | 1 |
| 2 | `requirement-review` | requirements | both | 1 |
| 3 | `intent-cross-check` | requirements | brownfield | 1 |
| 4 | `story-writer` | requirements | both | 1 |
| 5 | `impact-analysis` | design | brownfield | 1 |
| 6 | `test-plan-generator` | test | both | 1 |
| 7 | `code-change` | build | both | 1 |
| 8 | `defect-triage` | operate | brownfield | 1 |
| 9 | `verification-review` (independent judge) | test | both | 2 |
| 10 | `adr-writer` | design | both | 2 |
| 11 | `release-readiness` | release | both | 2 |
| 12 | `skill-finder` | meta | both | 2 |

`defect-triage` moved into Phase 1 because G1 needs it; the September prototype's lessons (four-type finding classification, house defaults kept out of acceptance criteria, an input hint on every skill) carry into skills 2, 4 and 6.

## Architecture build-out by phase

Every phase delivers a working slice across all planes rather than finishing one plane at a time, so each gate can be tested end to end.

&#91;embedded content: architecture build-out · 6 planes x 4 phases\]

Read a column to see what exists at the end of a phase; read a row to see how one plane grows. Phase 1 is highlighted because its gate decides whether pilots start.

**Completion state of each architecture component**

| Component (section) | Phase 0 | Phase 1 | Phase 2 | Phase 3 |
| --- | --- | --- | --- | --- |
| Skill spec and artifact types | Spec v1, 5 schemas | All 13 v1 types | Stable | Extended per domain |
| Workflow engine and compiler | Chosen, gate demo | Compiler, lockfile | Pilot workflows | Planner v2 |
| Harness | Rules drafted | L0 to L2, hard gates | L3, bands, calibration | Thresholds tuned per skill |
| Verifier profiles | Format agreed | Node, React | Java, Python | Tier C embedded |
| Foundation and context packs | Spec | Builder, reference pack | 3 pilot packs | All active systems |
| Domain packs | Harvest plan | Interviews started | First domain pack and evals | Second domain |
| Improvement loop | Signals defined | Signals captured | Run by hand | Automated to PR |
| Entry points | Marketplace skeleton | CLI, gate views | Portal, map, triggers | Pod builder, MCP |
| Security and governance | SSO, vault | OPA, audit | PII, injection, tenancy | Client-VPC, legal |

## Team assignments: Phase 0 exploration

Each team member owns one slice of Phase 0 and brings a written understanding and plan by Oct 1, 2026; together the five findings decide gate G0.

| Person | Area | Architecture parts owned | Questions to answer | Hands-on spike | Bring by the deadline |
| --- | --- | --- | --- | --- | --- |
| **Abhishek** (backend) | Control plane | Workflow engine, YAML compiler, artifact and trace store | Temporal or LangGraph for durable runs with human gates? How does a YAML workflow compile to it? How do we store artifacts (Git) and metadata (Postgres)? | A 3-step workflow that pauses at a human gate, resumes on an approval signal, and survives a worker restart | Engine recommendation with trade-offs; draft workflow YAML schema; store design |
| **Shubham** (backend) | Execution plane | Agent executor, model gateway, MCP tools, sandboxes, verifier profiles | How do we run one skill headless with the Claude Agent SDK? How does LiteLLM enforce budgets per team? Which Jira and GitHub MCP servers do we use? How are sandboxes isolated? | Run `requirement-review` headless through LiteLLM inside a container; run a Node verifier profile (build, test, lint, Semgrep) on a sample repo | Executor design; gateway config; MCP shortlist; verifier profile format |
| **Japman** (backend) | Harness and knowledge | Harness rules, confidence calculator, OPA policies, evals, context-pack extractors | How are hard gates H1 to H7 implemented? Which eval runner (promptfoo, DeepEval, Inspect AI)? Which tools extract facts (OpenAPI, DB schema, dependencies) for context packs? | JSON Schemas for `intent.v1` and `story-set.v1` with a validator; one OPA policy that blocks a disallowed tool; one eval case run in the chosen runner | Harness rule design; eval runner recommendation; context-pack extractor list |
| **Ekjot** (frontend) | Portal and capability map | Backstage portal, catalog model, capability map, marketplace install flow | How do we model Skill, Agent, Workflow and Pod as Backstage catalog kinds? How does a Backstage plugin read registry data? How does "Install" map to a marketplace command? | Local Backstage with 3 sample skills as catalog entities and a stub capability-map page | Catalog model; capability-map wireframe; portal plugin plan |
| **Gaurav** (frontend) | Human-gate and run experience | Gate approval view, run timeline, artifact diff review, pod builder UI, Jira and Slack surfaces | What does a reviewer need to approve, edit or reject an artifact fast? How does a paused run appear in Jira and Slack? What inputs does the pod builder need? | Clickable wireframes for gate approval, run timeline and pod builder, reviewed with 2 engineers | UX flows; component list; open questions for the backend owners |

**Same format for every findings note (two pages at most)**

1. What exists already and what we reuse.
2. What we must build, and how.
3. Risks and unknowns.
4. Proposed Phase 0 and Phase 1 task list, each task sized S, M or L.
5. Interfaces with the other four areas (inputs, outputs, owner).

**Pairings and handoffs.** Abhishek and Japman agree the artifact envelope together, since the store and the harness both depend on it. Shubham and Japman agree how verifier results reach the harness. Ekjot and Gaurav share one component library and one design for artifact and run views. Gaurav takes gate and run API needs to Abhishek.

**Readout on Oct 1, 2026.** Each person presents for 10 minutes; decisions are recorded against gate G0 in the open-decisions table.

## Risks and mitigations

The biggest risk is scope: building both audiences and our own control plane only works if the platform stays thin and pilots start on a proven chain.

| Risk | Early signal | Mitigation |
| --- | --- | --- |
| Scope creep across both audiences | Phase 1 exit gate keeps slipping | Sales sees only a read-only view of engineering evidence; nothing Sales-only is built before G2 |
| Weak root in real projects | High root-caused rework in pilots | Readiness Gate enforced; context pack required for brownfield; pack owner named per system |
| Context packs go stale | Linter flags `Verified:` older than two quarters | Generated facts rebuilt in CI; drift fails the build; pack ownership in the tech lead's goals |
| Confidence bands mean nothing | Calibration error above 5% | Weekly audits; automatic threshold tightening and autonomy downgrade |
| Low adoption | Weekly active engineers flat through the pilot phase | Meet engineers in their IDE and Jira; pilot teams chosen with their consent; publish time saved per team |
| Skills rot without owners | Skill with no reviewed change in 90 days and falling acceptance | CI blocks unowned skills; deprecate rather than keep unowned ones |
| Vendor or ownership change in a dependency | Licence or roadmap change (see promptfoo, Langfuse) | Own formats for evals and traces; every dependency behind an interface |
| Prompt injection or data leak | Injection classifier hits; PII detector hits in logs | Untrusted-input handling, deny-by-default sandboxes, OPA on every tool call, security review for write skills |
| Over-claiming to clients | Pod sheet cites a pilot skill | Pod builder excludes non-production items automatically; pre-sales review before any client deck |
| Model cost overrun | Cost per run rising week on week | LiteLLM budgets with hard caps; cheaper models for low-risk steps once evals prove parity |

## Open decisions and authenticity check

Nine decisions need an owner before Phase 0 ends; the architecture itself holds up against its sources, with two ownership changes and one simplification found in the check.

**Decisions needed by G0**

| # | Decision | Recommendation |
| --- | --- | --- |
| O1 | Written definition of success at gate G3, signed by the sponsor | Three teams using it weekly on real work; measured uplift on 2 metrics; capability map fully evidence-backed |
| O2 | Which three pilot teams | Ask teams first; all on brownfield systems, from different domains and stacks |
| O3 | Context pack owner for each pilot system | That system's tech lead, never the library team |
| O4 | Hosting account, region and repo host | Truminds cloud account in India region; private GitHub organisation |
| O5 | Default model and approved model list | One default model; allowlist per client in the gateway |
| O6 | Staffing beyond the current five | Owners per area as in the team assignments; add a platform lead and a QA/eval engineer as the team grows |
| O7 | Subject-matter expert for the first domain pack | 20% of one senior engineer from the first pilot's domain, for Phases 1 and 2 |
| O8 | Legal clauses for AI use in client contracts | Legal review before the first client pod sheet |
| O9 | Stage approvers (CODEOWNERS) per lifecycle stage | One named approver per stage |

**What the check confirmed**

- The skill format, SKILL.md loading and skill allowlists work as the design assumes.
- Temporal holds human gates for days without compute and survives failures.
- LiteLLM enforces budgets and rate limits per key, user and team.
- OPA is CNCF graduated; Backstage is CNCF incubating; MCP now sits under the Linux Foundation.
- Renode runs embedded firmware tests in CI, making a Tier C simulation verifier feasible.

**What the check changed**

- **Adapters dropped.** Copilot, VS Code, Cursor, Codex and Gemini CLI now read SKILL.md natively, so the earlier per-tool adapter build is replaced by packaging only.
- **promptfoo** is being acquired by OpenAI (announced 9 March 2026) and **Langfuse** has been acquired by ClickHouse. Both stay open source by stated intent, so both are kept behind our own formats.

**What is still an assumption, to confirm in the spike or pilots**

- Confidence thresholds (90% coverage, 4.0 judge score, 10% audit, 5% rejection) are starting proposals; pilot data sets the real values.
- Team split and the first-12 order are planning estimates.
- The exact skill folder each client tool reads (for example `.github/skills` in Copilot) is checked per tool in the spike.
- Build effort of the YAML-to-Temporal compiler versus adopting LangGraph is measured in the spike before G0.
- Uplift figures do not exist yet; none are claimed until pilot baselines are compared.

**Sources (opened September 2026)**

- [Agent Skills overview](https://agentskills.io/home)
- [Agent Skills in the Claude Agent SDK](https://code.claude.com/docs/en/agent-sdk/skills)
- [Create a Claude Code plugin marketplace](https://code.claude.com/docs/en/plugin-marketplaces)
- [MCP joins the Agentic AI Foundation](https://blog.modelcontextprotocol.io/posts/2025-12-09-mcp-joins-agentic-ai-foundation/)
- [Temporal human-in-the-loop AI agent](https://docs.temporal.io/ai-cookbook/human-in-the-loop-python)
- [LiteLLM budgets and rate limits](https://docs.litellm.ai/docs/proxy/users)
- [Open Policy Agent at CNCF](https://www.cncf.io/projects/open-policy-agent-opa/)
- [Backstage joins the CNCF incubator](https://www.cncf.io/blog/2022/03/15/backstage-project-joins-the-cncf-incubator/)
- [Langfuse joins ClickHouse](https://langfuse.com/blog/joining-clickhouse)
- [OpenAI's Promptfoo acquisition explained](https://qaskills.sh/blog/openai-promptfoo-acquisition-explained-2026)
- [Renode GitHub Action for testing in simulation](https://antmicro.com/blog/2024/10/renode-github-action-for-automated-testing-in-simulation)

  |  |  |  |
  | --- | --- | --- |
  |  |  |  |
  |  |  |  |
