# Release 1 done-gate checklist (G2)

| Field | Value |
| --- | --- |
| Status | Draft for owner review (criteria proposed, needs Puneet decision) |
| Owner | Puneet Singh Nanda |
| Approver | Puneet Singh Nanda |
| Source | [PLN-01 §3.3](PLN-01-delivery-plan.md#33-g2--release-1-done-proposed-needs-puneet-decision), PRD §6 G2, tracker Q16 |

Use this sheet at the G2 review. Each line needs evidence (a link or path) and a reviewer's initials. The gate passes only when every line is ticked **and** Puneet signs at the bottom. G0 and G1 must already be signed (PLN-01 §3.1–§3.2). The targets are the PLN-01 proposals; change them in PLN-01 first, then here.

## 1. Preconditions

| # | Check | Evidence | Done |
| --- | --- | --- | --- |
| P-1 | G0 signed (PLN-01 §3.1) | | [ ] |
| P-2 | G1 signed (PLN-01 §3.2) | | [ ] |
| P-3 | R1-1 to R1-11 accepted, changed or removed by Puneet; "proposed" label dropped (PLN-OI-06) | GOV-01 decision log row | [ ] |

## 2. Criteria

| # | Criterion | Target (proposed) | How to check | Evidence | Done |
| --- | --- | --- | --- | --- | --- |
| R1-1 | Pilot system(s) chosen and consented (OQ-04, OQ-06) | At least 1 Truminds internal system; client systems only with signed consent | `client.consent_ref` set for every pilot client; LEG-01 §14 checklist filed | | [ ] |
| R1-2 | `brownfield-change` on real pilot tickets | 10 tickets end to end | Run folders in the companion repos; runs COMPLETED | | [ ] |
| R1-3 | First-try pass rate on pilot runs | ≥ 70% of steps PASS or PASS-WITH-FINDINGS on attempt 1 | Insights Engineering tab (`step` table; metric definition SDD-08 §10.4, config RD-5) | | [ ] |
| R1-4 | Merged PRs that bypassed records | 0 | `tsl-ci-verify` is a required check on every pilot repo; `ci.verified` events match merged PRs | | [ ] |
| R1-5 | Calibration audit | 1 in 10 High results audited (OQ-11); every audited High deserved High | `audits/<run_id>/<step>.audit.json`; `audit.recorded` counts | | [ ] |
| R1-6 | Weekly use | 3 teams weekly for 4 consecutive weeks | Weekly active engineers per team (PRD §5) | | [ ] |
| R1-7 | Per-skill acceptance shown | First-try pass per skill on the portal | Portal skill-performance tab | | [ ] |
| R1-8 | Security | SEC-01 review by a named reviewer; no open security finding | SEC-01 §12.5 sign-off | | [ ] |
| R1-9 | Catalogue | All 17 Release-1 skills and 5 workflows at `production` or `pilot`, each with signed evals | Catalogue screen; `eval-result.v1` files; `tsl validate plugins/truminds` | | [ ] |
| R1-10 | Baseline recorded | Each pilot team recorded the PRD §5 baseline before first use | Baseline sheet | | [ ] |
| R1-11 | Operations | OPS-02 alerts live; OPS-03 rollback tested once; OPS-04 runbook reviewed | Alert test log; rollback record; OPS-04 status | | [ ] |

## 3. Repository checks that must be green on the release commit

| # | Check | Command | Done |
| --- | --- | --- | --- |
| C-1 | Every component test suite | `make test-all` | [ ] |
| C-2 | Linters and type checkers | `make lint-all` | [ ] |
| C-3 | Links, registry ids, doc control rows, backlog in sync | `make docs-check` | [ ] |
| C-4 | Portal end-to-end and accessibility | `make test-portal-e2e` | [ ] |
| C-5 | Harness labelled set on target (code-scored cases) | `cd tsl && uv run tsl harness eval --code-only --dir ../harness-evals/cases` | [ ] |
| C-6 | Release checklist of OPS-03 §3.2 complete | OPS-03 §3.2 | [ ] |
| C-7 | No item in [traceability.md](traceability.md) is Missing | Status counts in its §1 | [ ] |

## 4. Sign-off

| Role | Name | Decision | Signature |
| --- | --- | --- | --- |
| Approver | Puneet Singh Nanda | Pass / Not yet | |
| Security reviewer (R1-8) | TBD by Puneet | | |

## Open items

| Ref | Item | Owner |
| --- | --- | --- |
| PLN-OI-01 | Whether "Release 1" means the end of Phase 2 (this sheet) or Phase 1 | Puneet Singh Nanda |
| PLN-OI-06 | Release-1 success criteria R1-1 to R1-11 | Puneet Singh Nanda |
| OQ-04 | Pilot teams and systems | Puneet Singh Nanda |
