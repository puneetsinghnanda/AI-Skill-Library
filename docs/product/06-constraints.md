# Truminds AI Skill Library — 6. Constraints & Out-of-Scope

Oct 6, 2026 · @Puneet Singh Nanda

## 1. Document control

| Field | Value |
| --- | --- |
| Document | 6 of 6 — Constraints & Out-of-Scope |
| Status | Draft for review |
| Owner | Puneet Singh Nanda |
| Related | [PRD](01-prd.md) · [Personas & Stories](02-personas-and-stories.md) · [Architecture](../architecture/03-architecture.md) · [Design & UX](../ux/04-design-and-ux.md) · [API & Rules](../architecture/05-api-and-rules.md) |

**How to use this list:** a constraint (C) is a fixed boundary the design must respect. An assumption (A) is something believed true but not yet confirmed; each has an owner to confirm it. A limitation (L) is a known gap we accept and how we handle it. An X item must not be built in Release 1 — a PR that builds one is rejected unless Puneet removes it from this list first.

## 2. Constraints

| ID | Constraint | Source | Effect on design |
| --- | --- | --- | --- |
| C-01 | All LLM execution is local in the Claude Code desktop app with the Truminds plugin | Decision D-10 | No server-side agents; harness decisions in local `tsl` |
| C-02 | No Claude API is used anywhere (including CI and reports) | D-11 | CI re-runs code checks only; improvement report is plain code; evals run on seats |
| C-03 | Company Claude seats only; personal accounts never used for client code | Org rule | Managed settings; seat assignment in onboarding (US-18) |
| C-04 | Client code processed only with written client consent | Org rule | `tsl init-context` blocked without consent record (E-CONS-01) |
| C-05 | Company SSO only; no custom auth | Org rule | OIDC for `tsl login` and portal |
| C-06 | No secrets in code or config; data encrypted at rest | Org rule | Secrets via CI secrets/keychain; DB and backups encrypted (NFR-08) |
| C-07 | Data residency: where the telemetry service and database may be hosted is not decided | OQ-02, OQ-03 | Hosting choice must allow region pinning; metadata-only events reduce exposure |
| C-08 | Never write to Jira, Confluence or a client system without explicit approval | Org rule | Policy hook + approval entries (R-14) |
| C-09 | No client names, customer data or credentials in Truminds repos, evals, fixtures or demos | Org rule | H4 check; T-01 test-data rule; code-only identifiers |
| C-10 | Domain-agnostic: no skill may hard-code a domain or system; knowledge comes from the context pack (and optional domain pack) | Puneet | Skill review checklist; evals on more than one sample system |
| C-11 | Team of five: Ekjot, Gaurav (frontend); Abhishek, Shubham, Japman (backend) | Puneet | Scope per phase sized to this team; ownership in Doc 3 §12.2 |
| C-12 | Phases are defined by scope and gates, not calendar dates | Puneet | Release plan in Doc 1 §6 has gates G0–G3, no dates |
| C-13 | Seats are org-wide; per-client model choice or per-client model settings are not available | Claude seat model | One model policy for all clients; recorded in consent |
| C-14 | Merge, deploy and infrastructure changes are always human | Autonomy matrix | Policy blocks merge/deploy tools |
| C-15 | Rules conflicts are flagged, never worked around | Org rule | R-17 |

## 3. Assumptions and compliance

### 3.1 Assumptions to confirm

| ID | Assumption | Confirm with | If false |
| --- | --- | --- | --- |
| A-01 | Every engineer in scope has a company Claude seat with Claude Code desktop | Admin | Rollout limited to seated engineers |
| A-02 | Admins can enforce the Truminds marketplace and hooks via managed settings on all engineer machines | Admin / IT | Hooks may be bypassed → rely more on CI (E-CI-01) |
| A-03 | Client product repos are on GitHub (for `tsl pr`, CI action and webhooks) | Delivery manager per client | Need a GitLab/Bitbucket adapter (X-12) |
| A-04 | Engineers' laptops can run Docker for verifier containers | IT | Verifiers run only in CI; laptop band capped at Medium |
| A-05 | Clients will allow a read-only CI token for the companion repo and a webhook on their repos | Client, via consent | No CI verify; PR review only |
| A-06 | Seats' Claude Code OpenTelemetry export can be enabled by managed settings | Admin | Token and cost metrics missing from dashboards |
| A-07 | Proposed thresholds (Doc 3 §5.3, §6) are reasonable starting points | Pilot data, Puneet (OQ-12) | Tuned per skill after pilot |

### 3.2 Privacy and compliance

This is a design summary, not legal advice; legal review of consent wording and processing is open (OQ-06).

| Topic | Applies because | How the design handles it |
| --- | --- | --- |
| India DPDP Act 2023 | Truminds processes personal data of its own employees (telemetry) and may see personal data in client code | Telemetry is metadata only; users shown by pseudonym; purpose stated in onboarding; retention limit (OQ-08); deletion on request by removing the user mapping |
| EU GDPR | Clients or employees in the EU | Same controls; data residency (C-07) decided with hosting; client data never leaves the laptop/Claude seat and the client's own repos except as code changes |
| Client contracts / NDAs | Client code is sent to Claude via company seats | Written consent required (C-04) naming the model provider and seat type |
| Personal data in client code or tickets | Cannot be masked inside Claude Code (L-01) | Sensitive files blocked from reading; H4 stops PII in artifacts; consent covers residual exposure |

**Personal data we store:** SSO subject, email, pseudonym, role grants, public keys, event metadata linked to pseudonym. **We do not store:** prompts, code, artifact text, client end-user data.

## 4. Known limitations

| ID | Limitation | Why | How we handle it |
| --- | --- | --- | --- |
| L-01 | PII inside normal source files cannot be masked before Claude reads them | Claude Code reads files directly; there is no masking layer between file and model | PreToolUse blocks known sensitive files; H4 blocks PII in outputs; client consent covers residual risk |
| L-02 | No per-client model controls | Seats are org-wide (C-13) | Single model policy, disclosed in consent |
| L-03 | Hooks do not stop plain Claude use outside the plugin | Hooks only run when the plugin is enabled | CI fails code PRs without records (E-CI-01); adoption metric "PRs without run" |
| L-04 | CI cannot re-check meaning (reviewer result) | No LLM in CI (C-02) | Reviewer result is a signed attestation; human PR review is the check; calibration audits |
| L-05 | Reviewer may be the same model as the generator | One seat, one model family | Separate context and rubric; must cite; code verifies citations; human gates |
| L-06 | A signature proves who ran the harness, not that they did not tamper with the reviewer output | The engineer controls the laptop | CI re-runs code checks; reviewer tampering only affects meaning checks, covered by PR review; audit trail by key |
| L-07 | Bash policy is pattern-based, not a sandbox | Claude Code hook model | Network commands denied by pattern; managed permissions; review of hook logs |
| L-08 | Lock needs network (git push) to start a run | Git is the lock server | Offline runs can continue but not start |
| L-09 | Metrics are only as complete as events received | Outbox may hold events while offline | Dashboards show "last event received" per user/device |
| L-10 | Android and iOS verifier profiles not in Release 1 | Docker cannot run iOS toolchains; Android emulation is heavy | Phase 2 (X-08); mobile changes run with band capped at Medium |
| L-11 | Figma and other MCP servers are read-only by default | Approval rule C-08 | Writes need an approval entry |

## 5. Out of scope — DO NOT BUILD in Release 1

| ID | Do not build | Why | Earliest |
| --- | --- | --- | --- |
| X-01 | Starting or running workflows from the portal or any server | C-01 local only | Not planned |
| X-02 | Any use of the Claude API (agents, CI review, report summaries, evals) | C-02 | Not planned |
| X-03 | Automatic merge, deploy or infrastructure change | C-14 | Not planned |
| X-04 | Pod builder UI (assembling pods from the catalogue) | Needs Release-1 usage data first | Phase 3 (US-22) |
| X-05 | Writing to Jira, Confluence, Figma or client systems without an approval entry | C-08 | Not planned |
| X-06 | Storing prompts, code, artifact text or findings text in the cloud | NFR-10, privacy | Not planned |
| X-07 | Custom login or user database separate from company SSO | C-05 | Not planned |
| X-08 | Android and iOS verifier profiles | L-10 | Phase 2 |
| X-09 | Per-client model selection | C-13 | Only if seat model changes |
| X-10 | PII masking/redaction proxy in front of Claude | Not possible inside Claude Code (L-01) | Not planned |
| X-11 | Auto-applying skill improvements without an eval case and owner review | Self-improvement must be evidence-first (US-16) | Not planned |
| X-12 | GitLab / Bitbucket support | A-03 | Phase 2, if a pilot needs it |
| X-13 | Showing client names, ticket ids or repo names on the capability map or any sales view | C-09 | Not planned |
| X-14 | Domain-specific hard-coded skills (e.g. a skill that only works for one product line) | C-10 | Not planned; domain knowledge goes in packs |
| X-15 | Real-time streaming dashboards | Batch/near-real-time is enough for Release 1 | Later, if asked |
| X-16 | Policy engine beyond YAML (e.g. OPA/Rego) | Small rule set | Revisit if rules outgrow YAML |
| X-17 | Using client code, data or names in evals, fixtures, sample systems or demos | C-09, T-01 | Not planned |

### 5.1 Open questions raised across Docs 3–6 (to add to Doc 1 §8)

- OQ-10 Which GitHub org hosts companion repos (Truminds or client)?
- OQ-11 Sampling rate for calibration audits.
- OQ-12 Confirm default limits (pack age, drift, change size, stale lock).
- OQ-13 Brand colours and logo for the portal.
- OQ-14 May client people answer open-questions files directly?
