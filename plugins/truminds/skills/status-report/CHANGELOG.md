# Changelog: status-report

## 1.3.0
- Roadmap 25-27 Nov, B (each step knows its tools): the step was never told its allowed
  tools and learned them from pre-tool refusals (E-POL-06), even for a read-only `grep`.
  tsl verify --inputs now lists them in data.allowed_tools, and the preamble says to use
  only those.
- MINOR: changed instruction, same tools, inputs and output schema. Needs a signed eval
  result for this version before any status change (SKL-V13).

## 1.2.0
- Run HMS-21: the hook refused 24 Edit calls (requirement-review 15, design 6,
  secure-code-review 3), because the skill had no Edit tool although its hand-over says to
  fix self-check items with targeted edits. Each refusal ended in a full rewrite.
- allowed_tools gains Edit, so self-check fixes are edits to the named parts only. The
  pre-tool hook still limits writes to the run's paths. MINOR: new tool, same inputs and
  output schema. Needs a signed eval result for this version before any status change
  (SKL-V13).
- Runs are independent, with one exception for this skill: it may still Read or Glob every
  run's runs/<run>/state.json and cite them, and nothing else of another run. Inputs now say
  to Glob runs/*/state.json: tsl never listed the files (source: run gives the run's ticket
  snapshot), so "listed by tsl" was wrong.

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
- First version in the plugin (SDD-01 §12, row SR).
- R1 target status `production`. Ships 3 starter eval cases; the full set of at least 10 is needed before
  the next status change (SDD-01 §7.1, §10.3).
