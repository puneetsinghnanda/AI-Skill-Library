# Training outline: Skill author and owner (A1–A2)

| Field | Value |
| --- | --- |
| Status | Draft for owner review |
| Owner | TBD by Puneet (SDD-13 owner); content reviewed by Abhishek Verma, Ekjot Singh |
| Approver | Puneet Singh Nanda |
| Audience | P-11 skill authors and owners |
| Prerequisite | The [engineer path](engineer.md) is done |
| Format | A1 60 minutes, A2 30 minutes |
| Completion evidence | A signed eval result for an existing skill on the sample system |

Source: [SDD-01](../design/SDD-01-skill-authoring.md), [SDD-11](../design/SDD-11-improvement-loop.md), [DEV-01 §6](../development/DEV-01-developer-guide.md#6-adding-a-skill-or-a-workflow).

## A1 · Skill standard and evals (60 minutes)

| Minutes | Topic | Walk through | Reference |
| --- | --- | --- | --- |
| 0–10 | Folder layout | `plugins/truminds/skills/requirement-review/` | SDD-01 §2 |
| 10–20 | `SKILL.md` template and the input-check preamble | The reference skill body | SDD-01 §3, §13.3 |
| 20–30 | `skill.yaml` (`skill-metadata.v1`), inputs and outputs, versioning | `tsl validate plugins/truminds` | SDD-01 §4–§6 |
| 30–40 | Rubric and checks | `rubric.md`, `checks.yaml` | SDD-01 §8–§9 |
| 40–55 | Eval cases and the required case mix | `evals/eval-set.yaml`, `evals/cases/EC-01` | SDD-01 §10 |
| 55–60 | `/truminds:eval` on your seat; the result is signed with your key | — | SDD-04 §6.16 |

## A2 · Improvement loop (30 minutes)

| Topic | Do | Reference |
| --- | --- | --- |
| Read the weekly report | Portal improvement report: failure clusters, links to records, metadata only | SDD-11 §4 |
| `/truminds:improve <skill>` | Add an eval case that reproduces the failure **first**; it must fail before the fix | SDD-11 §5, X-11 |
| No-regression rule | `tsl improve check`: the new case passes and no existing case regresses | SDD-11 §6 |
| Release | PR through CODEOWNERS; skill owner approves; stage approver promotes | SDD-01 §7, OPS-03 |
| Invented data only | A real failure becomes an invented case; CI scans for forbidden content | SDD-11 §7 |

## Open items

| Item | Owner |
| --- | --- |
| Authors cannot load unreleased skills because managed settings block sideloading (SDD-01 O-02, OI-13-14); A1 uses released skills until decided | Puneet Singh Nanda, Shubham Bansal |
| Stage approvers (OQ-07) | Puneet Singh Nanda |
