# Training outline: Tech lead (T1–T2)

| Field | Value |
| --- | --- |
| Status | Draft for owner review |
| Owner | TBD by Puneet (SDD-13 owner) |
| Approver | Puneet Singh Nanda |
| Audience | P-10 tech leads, P-12 engineering leads |
| Prerequisite | The [engineer path](engineer.md) is done |
| Format | T1 45 minutes, T2 30 minutes, live on `SYS-SMP` |
| Completion evidence | A signed approval block and a re-signed training pack after a drift exercise |

Source: [SDD-13 §4.1](../design/SDD-13-onboarding-admin.md#41-paths-per-persona), [SDD-06](../design/SDD-06-context-pack.md), [SDD-03 §16](../design/SDD-03-harness.md#16-harness-accuracy-tracker-q27).

## T1 · Context pack (45 minutes)

| Step | Do | Expect | Reference |
| --- | --- | --- | --- |
| 1 | `tsl init` in the training companion clone | `tsl.yaml` validated; consent for `CL-INT` found | SDD-12 §5.3 |
| 2 | `tsl context build` | `context/generated/*.json` and `manifest.json` with commit SHAs | SDD-06 §6.2 |
| 3 | `/truminds:context-draft` | Judgement sections drafted with `Status: drafted` | SDD-06 §6.4 |
| 4 | Review each section; correct it; set `Verified:` | Only a human sets `reviewed` | SDD-06 §3.3 |
| 5 | `tsl context sign` | `context/pack.signature.json` | SDD-06 §6.3, SDD-07 §6.5 |
| 6 | Drift drill: change a route in the training product repo; run `tsl context build --check` | Pack shows `stale` until re-signed | SDD-06 §7, US-06 |

## T2 · Approvals, locks and audits (30 minutes)

| Topic | Do | Reference |
| --- | --- | --- |
| Approve a design gate | `tsl approve <run_id> G-design`; try approving your own run and see it refused | SDD-02 §9.2, SDD-07 §6.4 |
| Reject with a reason | The run returns to the `on_reject` step with the reason as input | US-07 AC3 |
| Stale locks | `tsl state unlock` rules and the stale-lock definition (DEF-06) | SDD-02 §11 |
| Calibration audit | Review a High-band result; record `deserved` or `miss` in `audits/<run_id>/<step>.audit.json` | SDD-03 §16.3, TST-01 §3.3 |
| Read a verification record | Band, signals, dropped findings, signature | SDD-03 §12 |

## Open items

| Item | Owner |
| --- | --- |
| Audit rate 1 in 10 during the pilot (OQ-11) | Puneet Singh Nanda |
