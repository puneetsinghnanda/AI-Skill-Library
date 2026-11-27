# Changelog: story-split

## 1.6.0
- Roadmap 25-27 Nov, B (each step knows its tools): the step was never told its allowed
  tools and learned them from pre-tool refusals (E-POL-06), even for a read-only `grep`.
  tsl verify --inputs now lists them in data.allowed_tools, and the preamble says to use
  only those.
- MINOR: changed instruction, same tools, inputs and output schema. Needs a signed eval
  result for this version before any status change (SKL-V13).

## 1.5.0
- Roadmap A3 (content self-check): on 0.1.7 `split` retried in 6 of 7 team runs on reviewer
  findings about a missing discriminating AC, three of them a status partition (HMS-23, 24, 31).
- checks.yaml: `story-split.status-values` (hint, kind values-named): every status the data model
  lists (context/data-model.md, "Status is A, B, C or D" under its entity's heading) appears in an
  AC of a story whose REQ is about those statuses (names one, or "appointment status"). A hint
  because it matches text and can be wrong: the self-check shows it in data.hints; it fails no
  gate and does not lower S2.
- Hand-over: add an AC with the missing status to the story whose REQ touches it; if the status
  cannot occur there, leave it and say why under Unknown.
- MINOR: new hint check and a hand-over note, same tools, inputs and output schema. Needs a signed
  eval result for this version before any status change (SKL-V13).

## 1.4.0
- Run HMS-21: the hook refused 24 Edit calls (requirement-review 15, design 6,
  secure-code-review 3), because the skill had no Edit tool although its hand-over says to
  fix self-check items with targeted edits. Each refusal ended in a full rewrite.
- allowed_tools gains Edit, so self-check fixes are edits to the named parts only. The
  pre-tool hook still limits writes to the run's paths. MINOR: new tool, same inputs and
  output schema. Needs a signed eval result for this version before any status change
  (SKL-V13).
- Runs are independent (HMS-5 rerun: the skill read the earlier run's artifacts and feedback
  "as a starting point" at every step). data.prior_answers now holds this run's answers only;
  never read or cite another run's files, even of the same ticket. The pre-tool hook refuses
  such reads while a step is open, and tsl verify fails an artifact that names another run
  (E-H1-06).

## 1.3.0
- Roadmap item 2 (self-checks): run HMS-9 requirement-review went to band Low on S2 alone
  (RR-C12, summary over 5 sentences), which nothing reported before the review.
- Hand-over: after writing, run `tsl verify <data.artifact_path> --self-check --json` once and fix
  every item in data.fix (failing checks, soft checks, claims that will not verify) with targeted
  edits to only the parts each item names (never a full rewrite or a re-run of the step); never run
  it twice. Replaces "Do not run checks". MINOR: new instruction, same inputs and output schema.
  Needs a signed eval result for this version before any status change (SKL-V13).

## 1.2.0
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
- Eval cases EC-13, EC-14 and EC-15: an answer already in ide-answers.md is reused, not asked;
  a fact in the pack is cited, not asked; a claim with a supporting cite uses valid anchors and
  one key term. MINOR: new rules and eval cases, no output change (SDD-01 §6.2). Needs a
  signed eval result for this version.

## 1.1.0
- Acceptance criteria must tell a correct implementation apart from the likeliest wrong one. Method step 5
  adds a discrimination check (reasoning only, no new field). Found in a brownfield run where a
  time-zone AC used a late-evening instant that has the same local and UTC date, so it could not fail.
- Rule 10 adds a boundary checklist: local/UTC date mismatch, just over a limit, the excluded item as
  the most recent one, each partition of an "unchanged" requirement, and no duplicate Given/Then
  across stories.
- Rule 7 allows concrete scenario values derived from a cited value when the derivation is stated
  inline (for example a UTC offset worked out from a zone name). It still forbids new limits, and it
  says how to write derived values so H4 (E-H4-04) does not flag them.
- Rubric: SS-R3 becomes "Testable and discriminating criteria"; new major triggers for a
  non-discriminating AC and a missing boundary case; new minor trigger for duplicate ACs.
- Eval cases EC-11 (hospital time zone, AC in the 00:00 to 05:29 local window) and EC-12 (unchanged
  column, both partitions). MINOR: behaviour change; stories.v1 shape unchanged. Needs a signed eval
  result for this version (SKL-V13).

## 1.0.1
- Eval set completed to 10 cases (EC-04 to EC-10): normal cases in the sample order, support-ticket and
  library-loan systems, missing and ambiguous input, a conflict with the context pack, and the missing
  adversarial or forbidden-content case (SDD-01 §10.3, §10.4). PATCH: new eval cases only (SDD-01 §6.2).
  Needs a signed eval result for this version before any status change (SKL-V13).

## 1.0.0
- First version in the plugin (SDD-01 §12, row SS).
- R1 target status `production`. Ships 3 starter eval cases; the full set of at least 10 is needed before
  the next status change (SDD-01 §7.1, §10.3).
