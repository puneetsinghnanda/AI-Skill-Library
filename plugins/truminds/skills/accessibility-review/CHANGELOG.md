# Changelog: accessibility-review

## 1.4.0
- Roadmap 25-27 Nov, B (each step knows its tools): the step was never told its allowed
  tools and learned them from pre-tool refusals (E-POL-06), even for a read-only `grep`.
  tsl verify --inputs now lists them in data.allowed_tools, and the preamble says to use
  only those.
- MINOR: changed instruction, same tools, inputs and output schema. Needs a signed eval
  result for this version before any status change (SKL-V13).

## 1.3.0
- Run HMS-21: the hook refused 24 Edit calls (requirement-review 15, design 6,
  secure-code-review 3), because the skill had no Edit tool although its hand-over says to
  fix self-check items with targeted edits. Each refusal ended in a full rewrite.
- allowed_tools gains Edit, so self-check fixes are edits to the named parts only. The
  pre-tool hook still limits writes to the run's paths. MINOR: new tool, same inputs and
  output schema. Needs a signed eval result for this version before any status change
  (SKL-V13). Follows 1.2.0 on main (#41).

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
