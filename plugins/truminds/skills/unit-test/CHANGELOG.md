# Changelog: unit-test

## 1.4.0
- Roadmap A3 (content self-check and local checks): on 0.1.7 `ut` retried in 6 of 7 team runs
  on reviewer findings it could have found itself (HMS-24, 26, 28, 30, 31, 33), and HMS-33 used
  both verifier retries on a type error and a lint slip in its own tests.
- checks.yaml: `unit-test.acs-named` (H5, kind named-in): every AC of the stories is named on a
  Tests line as `S-n ACm`, or under Unknown. `unit-test.reqs-traced` (H5, coverage with
  or_named_in): every REQ the stories trace is in trace, or under Unknown. Both skip without a
  stories input (defect runs). `unit-test.ac-values-in-tests` (hint, kind values-in-code): an AC
  named as covered has one of its values in the lines the step added to its tests. A hint because
  it matches text and can be wrong: the self-check shows it in data.hints; it does not lower S2.
- Method: before writing a test, check its data can tell right from wrong (each status the AC
  names, two candidates for an order rule, data of the count or size the AC needs, a test that
  guards each answer the user gave). New Method 4 runs the local checks
  (`tsl verify --self-check --local`: type check and lint of the changed files on this machine;
  no attempt used) and fixes what they list before code[] is copied.
- Output: each Tests line names its REQ and every AC it covers as `S-n ACm` (S-n alone does not
  count).
- MINOR: changed instruction and new checks, same tools, inputs and output schema. Needs a signed
  eval result for this version before any status change (SKL-V13).

## 1.3.0
- Runs are independent (HMS-5 rerun: the skill read the earlier run's artifacts and feedback
  "as a starting point" at every step). data.prior_answers now holds this run's answers only;
  never read or cite another run's files, even of the same ticket. The pre-tool hook refuses
  such reads while a step is open, and tsl verify fails an artifact that names another run
  (E-H1-06).
- MINOR: changed instruction, same tools, inputs and output schema. Needs a signed eval
  result for this version before any status change (SKL-V13).

## 1.2.0
- Roadmap item 2 (self-checks): run HMS-9 requirement-review went to band Low on S2 alone
  (RR-C12, summary over 5 sentences), which nothing reported before the review.
- Hand-over: after writing, run `tsl verify <data.artifact_path> --self-check --json` once and fix
  every item in data.fix (failing checks, soft checks, claims that will not verify) with targeted
  edits to only the parts each item names (never a full rewrite or a re-run of the step); never run
  it twice. Replaces "Do not run checks". MINOR: new instruction, same inputs and output schema.
  Needs a signed eval result for this version before any status change (SKL-V13).

## 1.1.0
- Run HMS-4 (brownfield-change 1.3.0): impact escalated with band Low (S1 0.6, 8 of 14 claims
  verified) and design used up its checks budget on cite errors; about 8 of 19 questions asked
  were facts the pack or product code answers, and answered questions were asked again.
- New section "Look before you ask": reuse answers already given (runs/<run_id>/ide-answers.md
  and data.prior_answers); only decisions are written as open questions; facts are looked up in
  the listed sections, then the generated facts, then the product code at the pinned SHA, and
  stated as cited claims; only assumptions that cannot be checked are confirmed; trivial names
  get a default with a one-line trade-off.
- Inputs: the listed context sections are read first; product code at the pinned SHA may be read
  when a fact needs it (replaces "Read only these sections ... Never read the whole context pack").
- New citation rule: valid anchor forms (never <artifact>.md#C7 or manifest.json#...), one
  verbatim backticked key term per claim, IDE answers cited only when they exist, every decided
  item cites its answer, resolves[].how repeated word for word in the body.
- Rubric: minor trigger "Question asked that the context pack or product code answers" (one
  finding per such question).
- Eval cases EC-11, EC-12 and EC-13: an answer already in ide-answers.md is reused, not asked;
  a fact in the pack is cited, not asked; a claim with a supporting cite uses valid anchors and
  one key term. MINOR: new rules and eval cases, no output change (SDD-01 §6.2). Needs a
  signed eval result for this version.

## 1.0.1
- Eval set completed to 10 cases (EC-04 to EC-10): normal cases in the sample order, support-ticket and
  library-loan systems, missing and ambiguous input, a conflict with the context pack, and the missing
  adversarial or forbidden-content case (SDD-01 §10.3, §10.4). PATCH: new eval cases only (SDD-01 §6.2).
  Needs a signed eval result for this version before any status change (SKL-V13).

## 1.0.0
- First version in the plugin (SDD-01 §12, row UT).
- R1 target status `production`. Ships 3 starter eval cases; the full set of at least 10 is needed before
  the next status change (SDD-01 §7.1, §10.3).
