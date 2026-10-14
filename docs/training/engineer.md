# Training outline: Engineer (E1–E4)

| Field | Value |
| --- | --- |
| Status | Draft for owner review |
| Owner | TBD by Puneet (SDD-13 owner) |
| Approver | Puneet Singh Nanda |
| Audience | P-01 to P-08 |
| Format | E1 self-study 20 min; E2 30 min; E3 30 min live; E4 30 min |
| Completion evidence | A signed check record on `SYS-SMP` made with the trainee's key |

Source: [SDD-13 §3–§4](../design/SDD-13-onboarding-admin.md#4-training-paths).

## E1 · Concepts (self-study, 20 minutes)

Read the portal "How it works" page, then check you can answer:

- The seven objects: skill, workflow, pod, context pack, run, artifact, check record (SDD-13 §4.1).
- The harness order: code checks H1–H7, then the reviewer subagent, then code checks every citation, then `tsl decide` (SDD-03 §3).
- Signals S1–S6, the High / Medium / Low band, and the six outcomes PASS, PASS-WITH-FINDINGS, RETRY, NEEDS-INPUT, ESCALATE, ABORT (SDD-03 §9–§11).
- Why confidence is computed by code and never self-reported (D-16).

## E2 · Setup (30 minutes)

Lines 8–12 of the [onboarding checklist](onboarding-checklist.md).

## E3 · Hands-on (30 minutes, live)

The session in [hands-on-session.md](hands-on-session.md): `estimate` to completion, then `brownfield-change` to the design approval gate.

## E4 · Pauses, PR evidence and rules (30 minutes)

| Topic | Do | Reference |
| --- | --- | --- |
| Answer open questions | Fill `runs/<run_id>/open-questions.md`; every answer names a decider with an email address; then `/truminds:resume <run_id>` | SDD-02 §9.1, US-03, US-04 |
| Approval gates | Ask a tech lead to run `tsl approve`; you cannot approve your own work | SDD-02 §9.2, US-07 |
| Read the PR evidence | Verification table, decisions with deciders, unit-test results; `tsl-ci-verify` must pass | SDD-03 §13, US-05 |
| Stale lock | `tsl state show`; only a tech lead may `tsl state unlock` | SDD-02 §11, US-21 |
| Rules | Company seat only; Local sessions only, no WSL; no writes to Jira, Confluence or GitHub without a signed approval; never paste client data into a prompt outside the run | C-16, C-17, SEC-01 §6 |
| When something breaks | Find the error code in OPS-04 §3; raise a support issue without client data | OPS-04, OPS-03 §6 |

## Open items

| Item | Owner |
| --- | --- |
| How a training run reads a ticket from a file instead of the Jira MCP (OI-13-05) | Abhishek Verma, Ekjot Singh |
