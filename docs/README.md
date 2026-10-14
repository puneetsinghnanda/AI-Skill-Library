# Documents

Every document lives here and changes by pull request (GOV-01). The earlier Claude Docs versions carry a "Moved to repo" banner and are no longer edited.

## Product
| # | Document | Path |
| --- | --- | --- |
| 1 | Product Requirements | [product/01-prd.md](product/01-prd.md) |
| 2 | Personas and Stories | [product/02-personas-and-stories.md](product/02-personas-and-stories.md) |
| 6 | Constraints and Out-of-Scope | [product/06-constraints.md](product/06-constraints.md) |

## Architecture
| # | Document | Path |
| --- | --- | --- |
| 3 | System Architecture and Tech Stack | [architecture/03-architecture.md](architecture/03-architecture.md) |
| 5 | API Specifications and Rules | [architecture/05-api-and-rules.md](architecture/05-api-and-rules.md) |
| REG-01 | Canonical registry: error codes, commands, endpoints, events, schemas, tables, paths, ID series (wins over any other doc) | [architecture/registry.md](architecture/registry.md) |

## UX
| # | Document | Path |
| --- | --- | --- |
| 4 | Design and UI/UX Assets | [ux/04-design-and-ux.md](ux/04-design-and-ux.md) |
| — | Web UI prototype (15 screens) | [ux/prototype/](ux/prototype/README.md) |
| — | Figma (partial) | https://www.figma.com/design/bMcqK99UQTiGOIf4G6PT4Z |

## Software design documents (SDD)
| ID | Title | Owner | Path |
| --- | --- | --- | --- |
| SDD-01 | Skill authoring standard and catalogue | Abhishek Verma, Ekjot Singh | [design/SDD-01-skill-authoring.md](design/SDD-01-skill-authoring.md) |
| SDD-02 | Workflow orchestration and chaining | Abhishek Verma, Ekjot Singh; Shubham Bansal | [design/SDD-02-workflow-orchestration.md](design/SDD-02-workflow-orchestration.md) |
| SDD-03 | Harness: checks, reviewer, decide, CI verify | Japman Singh, Yash Khorwal | [design/SDD-03-harness.md](design/SDD-03-harness.md) |
| SDD-04 | `tsl` command-line tool | Japman Singh, Yash Khorwal | [design/SDD-04-tsl-cli.md](design/SDD-04-tsl-cli.md) |
| SDD-05 | Claude Code integration | Shubham Bansal | [design/SDD-05-claude-code-integration.md](design/SDD-05-claude-code-integration.md) |
| SDD-06 | Context pack and extractors | TBD by Puneet | [design/SDD-06-context-pack.md](design/SDD-06-context-pack.md) |
| SDD-07 | Identity, signing and keys | TBD by Puneet | [design/SDD-07-identity-signing.md](design/SDD-07-identity-signing.md) |
| SDD-08 | Telemetry and insights service, database | Gaurav Saini | [design/SDD-08-telemetry-insights.md](design/SDD-08-telemetry-insights.md) |
| SDD-09 | Web portal and read API | Gaurav Saini; UI owner TBD by Puneet | [design/SDD-09-web-portal.md](design/SDD-09-web-portal.md) |
| SDD-10 | Pods | Abhishek Verma, Ekjot Singh | [design/SDD-10-pods.md](design/SDD-10-pods.md) |
| SDD-11 | Improvement loop | Abhishek Verma, Ekjot Singh; Gaurav Saini | [design/SDD-11-improvement-loop.md](design/SDD-11-improvement-loop.md) |
| SDD-12 | Companion repo lifecycle | TBD by Puneet | [design/SDD-12-companion-repo.md](design/SDD-12-companion-repo.md) |
| SDD-13 | Onboarding and administration | TBD by Puneet | [design/SDD-13-onboarding-admin.md](design/SDD-13-onboarding-admin.md) |

## Security, test, development, operations, planning, governance, legal
| ID | Title | Owner | Path |
| --- | --- | --- | --- |
| SEC-01 | Security design and threat model | Security reviewer TBD by Puneet | [security/SEC-01-threat-model.md](security/SEC-01-threat-model.md) |
| TST-01 | Master test plan | Each area owner | [testing/TST-01-master-test-plan.md](testing/TST-01-master-test-plan.md) |
| TST-02 | Team validation plan (who tests what, how to report, verdict) | Puneet Singh Nanda | [testing/TST-02-team-validation-plan.md](testing/TST-02-team-validation-plan.md) |
| DEV-01 | Developer guide | TBD by Puneet | [development/DEV-01-developer-guide.md](development/DEV-01-developer-guide.md) |
| OPS-01 | Deployment and hosting | TBD by Puneet | [operations/OPS-01-deployment-hosting.md](operations/OPS-01-deployment-hosting.md) |
| OPS-02 | Monitoring and alerting | Gaurav Saini | [operations/OPS-02-monitoring-alerting.md](operations/OPS-02-monitoring-alerting.md) |
| OPS-03 | Release, rollout and support | TBD by Puneet | [operations/OPS-03-release-rollout-support.md](operations/OPS-03-release-rollout-support.md) |
| OPS-04 | Failure-mode runbook | TBD by Puneet | [operations/OPS-04-failure-runbook.md](operations/OPS-04-failure-runbook.md) |
| PLN-01 | Delivery plan | Puneet | [planning/PLN-01-delivery-plan.md](planning/PLN-01-delivery-plan.md) |
| GOV-01 | ADR log and change process | Puneet | [governance/GOV-01-adr-and-change-process.md](governance/GOV-01-adr-and-change-process.md) |
| LEG-01 | Client consent and data-processing template (draft for legal) | Legal, TBD by Puneet | [legal/LEG-01-client-consent-template.md](legal/LEG-01-client-consent-template.md) |

## Planning and presentations
- [Implementation Readiness Tracker](planning/readiness-tracker.md)
- [Traceability: tracker, requirements and stories to the repo](planning/traceability.md) — status of every tracker item
- [Backlog (importable CSV, from PLN-01 §7)](planning/backlog.csv) — rebuilt by `scripts/build_backlog.py`; nothing is sent to Jira
- [Release 1 done-gate checklist (G2)](planning/release-1-gate-checklist.md)
- [Architecture deck (.pptx)](presentations/Truminds_Skill_Library_Architecture.pptx), [PDF](presentations/Truminds_Skill_Library_Architecture.pdf), source [build.js](presentations/build.js)

## Training
- [Training and onboarding](training/README.md) — onboarding checklist, persona training outlines, hands-on session guide (SDD-13 §3–§4)

## Decision records
- [docs/adr/](adr/README.md)

## Archive (superseded, read-only)
- [PRD v1](archive/prd-v1-superseded.md)
- [Architecture and Implementation Plan, 28 Sep](archive/architecture-plan-2026-09-28.md)
