# Hands-on session (E3, 30 minutes) — facilitator guide

| Field | Value |
| --- | --- |
| Status | Draft for owner review |
| Owner | TBD by Puneet (SDD-13 owner) |
| Approver | Puneet Singh Nanda |
| Source | [SDD-13 §3.7, §4.2, §4.3](../design/SDD-13-onboarding-admin.md#42-hands-on-session-e3-30-minutes) |

## 1. Preparation (before the session)

| # | Step | Who | Done |
| --- | --- | --- | --- |
| 1 | `CL-INT`, `PRJ-SMP`, `SYS-SMP` registered; consent recorded as "internal, invented data, no client code" | Insights admin | [ ] |
| 2 | Training product repo created from `examples/sample-system/`; companion repo created, initialised, pack built and signed | GitHub org admin, facilitator | [ ] |
| 3 | `TRN-01` … `TRN-<n>` ticket files copied from `examples/sample-system/tickets/ABC-170.md` and `ABC-142.md`, one per trainee | Facilitator | [ ] |
| 4 | `engineer@SYS-SMP` for the cohort; `tech_lead@SYS-SMP` for tech-lead trainees; GitHub team membership | Insights admin, GitHub org admin | [ ] |
| 5 | Every trainee finished lines 1–12 of the [onboarding checklist](onboarding-checklist.md) | Trainees | [ ] |

## 2. Run sheet

| Minutes | Activity | Facilitator checks |
| --- | --- | --- |
| 0–5 | Everyone opens a Local session in the training companion clone; `/truminds:status` | Plugin visible on every seat |
| 5–12 | Run 1: `/truminds:run estimate TRN-<nn>`; read the status line, band and check record | Every trainee has PASS or PASS-WITH-FINDINGS |
| 12–25 | Run 2: `/truminds:run brownfield-change TRN-<nn>` to `G-design`; look at a RETRY if one happens and at `artifact.checks.json` | Runs reach PAUSED_APPROVAL |
| 25–30 | Tech-lead trainees `tsl approve <run_id> G-design`; engineers `/truminds:resume <run_id>`; questions | Signed approvals in `approvals.md` |

## 3. After the session

| # | Step | Done |
| --- | --- | --- |
| 1 | Close training PRs without merging; remove stale locks | [ ] |
| 2 | Record tokens per run from the portal (metric M-32) for spike S-11 | [ ] |
| 3 | Record each trainee's completion evidence (signed check record on `SYS-SMP`) | [ ] |

## Open items

| Item | Owner |
| --- | --- |
| How a run reads `TRN-<nn>` from a file instead of the Jira MCP (OI-13-05) | Abhishek Verma, Ekjot Singh |
| Seat usage for the session is not yet measured (Q38, spike S-11) | Claude org admin, TBD by Puneet |
