# Training outline: Admins (M1–M2)

| Field | Value |
| --- | --- |
| Status | Draft for owner review |
| Owner | TBD by Puneet (SDD-13 owner) |
| Approver | Puneet Singh Nanda |
| Audience | The admin roles in SDD-13 §5.1 (Claude org admin, Entra app admin, GitHub org admin, insights admin, release maintainer) |
| Format | M1 self-study; M2 drills, 60 minutes |
| Completion evidence | Drill record filed in the skill-library repo, with no personal data |

Source: [SDD-13 §5–§9](../design/SDD-13-onboarding-admin.md#5-admin-roles-and-access).

## M1 · Self-study, per role

| Role | Read |
| --- | --- |
| Claude org admin | SDD-13 §6 (managed-settings rollout), SDD-05 §6, `managed-settings/managed-settings.template.json` |
| Entra app admin | SDD-07 §3 (app registrations, app roles), SDD-13 §3.2 |
| GitHub org admin | SDD-12 §6 (companion repo access), SDD-13 §7.3 (team sync) |
| Insights admin | SDD-13 §7 (clients, systems, consent, role grants), SDD-07 §5.6 (key revocation), LEG-01 §14 (engagement checklist), SEC-01 §7.4 (client-name denylist) |
| Release maintainer | OPS-03 (release, rollout, rollback), SEC-01 §8.2 (signed releases) |
| Everyone | SDD-13 §9 (offboarding), OPS-04 §5 (security incidents) |

## M2 · Drills (60 minutes, on test users and a test seat only)

| Drill | Steps | Pass when |
| --- | --- | --- |
| Managed-settings verification | Apply the template to a test seat; run the checks MS-01 to MS-06 | All recorded (SDD-13 §6.3) |
| Lost laptop (tabletop) | Revoke the test user's key; note the time T; try a record signed after T | CI rejects it (SDD-07 §5.7, SDD-13 §9.3) |
| Offboarding | Deactivate a test user; check grants and keys are revoked and GitHub team removed | `audit_log` shows `user_deactivate` (SDD-13 §9.2) |

## Open items

| Item | Owner |
| --- | --- |
| Named owner and backup for each admin role (Q30, OI-13-01) | Puneet Singh Nanda |
| Admin screens in the portal are not yet designed (tracker Q11, OI-13-04) | Gaurav Saini; UI owner TBD by Puneet |
