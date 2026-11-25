# Changelog: test-automation

## 1.3.0
- Roadmap 25-27 Nov, B (each step knows its tools): the step was never told its allowed
  tools and learned them from pre-tool refusals (E-POL-06), even for a read-only `grep`.
  tsl verify --inputs now lists them in data.allowed_tools, and the preamble says to use
  only those.
- MINOR: changed instruction, same tools, inputs and output schema. Needs a signed eval
  result for this version before any status change (SKL-V13).

## 1.2.0
- #6: `test-automation.results-linked` (H2) could never fail: it compared each result's covers with
  the covers of all results. It now reads the step's `test_plan` input and compares TP-n/S-n/ACn
  pairs: every pair of a non-manual planned test needs a result that ran (pass or fail; skip does not
  count). New `test-automation.results-planned` (H2) checks the other direction: no invented test
  ids and no criteria the plan does not give a test.
- results-linked waits while the step asks a blocking question that is not answered yet, so a step
  that stops to ask reaches NEEDS-INPUT instead of a retry.
- Rules 6 and 7 say what code checks and that a test that cannot run needs a blocking question.
  MINOR: stricter checks and a rules change, same inputs and output schema. Needs a signed eval
  result for this version before any status change (SKL-V13).

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
- First version in the plugin (SDD-01 §12, row TA).
- R1 target status `pilot`. Ships 3 starter eval cases; the full set of at least 10 is needed before
  the next status change (SDD-01 §7.1, §10.3).
