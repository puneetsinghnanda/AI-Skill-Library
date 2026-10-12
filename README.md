# Truminds AI Skill Library

SDLC skills, workflows and a quality harness that run locally in Claude Code (desktop app, company seats) through the `truminds` plugin. No Claude API calls. Approver: Puneet Singh Nanda.

This repository is the **source of truth** for every design document and all code. Change anything by pull request.

## Layout

```text
.claude-plugin/marketplace.json   marketplace "truminds-skill-library"
plugins/truminds/                 the plugin: skills, agents, hooks, workflows, policy
tsl/                              truminds-tsl, the Python 3.12 command-line tool (SDD-04)
schemas/                          JSON Schemas for every contract (Doc 5 §3)
managed-settings/                 managed-settings template for the Claude org admin (SDD-05 §6)
services/insights/                FastAPI insights service + PostgreSQL 16 (SDD-08)
portal/                           React intranet portal (SDD-09)
examples/sample-system/           React + Node.js brownfield sample system (TST-01)
spikes/                           spike plugin for unverified platform facts (SDD-05 §8)
docs/                             all documents — start at docs/README.md
```

## Team areas

| Area | Owners |
| --- | --- |
| Skills, workflows, roles | Abhishek Verma, Ekjot Singh |
| Harness, execution, `tsl verify` | Japman Singh, Yash Khorwal |
| Skill execution, hook execution | Shubham Bansal |
| Telemetry, logs, events, portal statistics | Gaurav Saini |
| Anything unassigned | TBD by Puneet |

## Rules that apply to every change

- Never write to Jira, Confluence or a client system without explicit approval.
- No client names, customer data, credentials or client code in this repo, evals, fixtures or demos.
- Use company SSO (Microsoft Entra ID) libraries for all authentication; never roll custom auth.
- No back doors, debug bypasses or hidden endpoints. Encrypt data at rest.
- No secrets, credentials or API keys in code or config committed to git.
- Flag rule conflicts instead of working around them.
- Domain-agnostic: examples must not assume any one client domain.
