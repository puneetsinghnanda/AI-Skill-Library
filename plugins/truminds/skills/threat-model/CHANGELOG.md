# Changelog: threat-model

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
- First version in the plugin (SDD-01 §12, row TM).
- R1 target status `production`. Ships 3 starter eval cases; the full set of at least 10 is needed before
  the next status change (SDD-01 §7.1, §10.3).
