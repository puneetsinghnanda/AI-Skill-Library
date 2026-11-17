# Changelog: accessibility-review

## 1.2.0
- #7: `accessibility-review.wcag-map` (H2) now runs. Before, tsl had no `enum-file` check and no
  allowlist, so the check skipped and a skip counts as a pass. Each finding's `wcag` must be one of the
  49 WCAG 2.1 A and AA criteria in tsl's `wcag21-aa-criteria.txt`, and its `level` must be that
  criterion's level (a stricter check).
- Rule 5: a finding carries its criterion's own level, and never maps to 4.1.1 Parsing (obsolete in
  the WCAG 2.1 errata; it is left out of the allowlist). MINOR: stricter check and a rules change, same
  inputs and output schema. Needs a signed eval result for this version before any status change
  (SKL-V13).

## 1.1.0
- Roadmap item 2 (self-checks): run HMS-9 requirement-review went to band Low on S2 alone
  (RR-C12, summary over 5 sentences), which nothing reported before the review.
- Hand-over: after writing, run `tsl verify <data.artifact_path> --self-check --json` once and fix
  every item in data.fix (failing checks, soft checks, claims that will not verify) with targeted
  edits to only the parts each item names (never a full rewrite or a re-run of the step); never run
  it twice. Replaces "Do not run checks". MINOR: new instruction, same inputs and output schema.
  Needs a signed eval result for this version before any status change (SKL-V13).

## 1.0.1
- Eval set completed to 10 cases (EC-04 to EC-10): normal cases in the sample order, support-ticket and
  library-loan systems, missing and ambiguous input, a conflict with the context pack, and the missing
  adversarial or forbidden-content case (SDD-01 §10.3, §10.4). PATCH: new eval cases only (SDD-01 §6.2).
  Needs a signed eval result for this version before any status change (SKL-V13).

## 1.0.0
- First version in the plugin (SDD-01 §12, row AR).
- R1 target status `pilot`. Ships 3 starter eval cases; the full set of at least 10 is needed before
  the next status change (SDD-01 §7.1, §10.3).
