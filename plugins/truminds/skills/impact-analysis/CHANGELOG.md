# Changelog: impact-analysis

## 1.3.0
- Run HMS-4 (brownfield-change 1.3.0): impact escalated with band Low (S1 0.6, 8 of 14 claims
  verified) and design used up its checks budget on cite errors; about 8 of 19 questions asked
  were facts the pack or product code answers, and answered questions were asked again.
- New section "Look before you ask": reuse answers already given (runs/<run_id>/ide-answers.md
  and data.prior_answers); only decisions are put to the user in the IDE; facts are looked up in
  the listed sections, then the generated facts, then the product code at the pinned SHA, and
  stated as cited claims; only assumptions that cannot be checked are confirmed; trivial names
  get a default with a one-line trade-off.
- Inputs: the listed context sections are read first; product code at the pinned SHA may be read
  when a fact needs it (replaces "Read only these sections ... Never read the whole context pack").
- New citation rule: valid anchor forms (never <artifact>.md#C7 or manifest.json#...), one
  verbatim backticked key term per claim, IDE answers cited only when they exist, every decided
  item cites its answer, resolves[].how repeated word for word in the body.
- Method step 4: call, ui and sym facts and the product code settle most caller, renderer
  and type-location questions; only what they cannot settle becomes a question.
- Rubric: minor trigger "Question asked that the context pack or product code answers" (one
  finding per such question).
- Eval cases EC-12, EC-13 and EC-14: an answer already in ide-answers.md is reused, not asked;
  a fact in the pack is cited, not asked; a claim with a supporting cite uses valid anchors and
  one key term. MINOR: new rules and eval cases, no output change (SDD-01 §6.2). Needs a
  signed eval result for this version.

## 1.2.0
- Before writing, the skill asks the user every open question and confirms every assumption in
  the IDE (AskUserQuestion), then writes the impact from the answers. Questions cover what the
  generated facts cannot settle: caller sets (no call edges), where a contract type is declared,
  and baseline drift when tsl warns E-CTX-10.
- The tsl post-tool hook records each answer in `runs/<run_id>/ide-answers.md` (A-nn, with who
  answered). Modules, APIs, tables and claims an answer decided cite
  `runs/<run_id>/ide-answers.md#a-nn`. An assumption is asked about the claim that states it.
  New optional `answers` list in `impact.v1` (`about`: Q-nn or claim id; `decides`: item ids).
- New check IA-C01 (`answers.logged` with `targets`, `field: decides`, `noun: item`; H4): the
  artifact's answers match the log exactly, none is left out, and each item an answer decided
  cites it.
- New rule: never state a set as complete ("only", "all", "none") without a fact that proves
  it; ask instead.
- Skipped questions, or runs without an IDE (evals), fall back to open questions and the
  existing pause for input.
- The user's answer always decides the item, even when it differs from the facts. The
  difference is recorded in the answer's `mismatch`. Rubric: an item decided by a cited answer
  is honest status (IA-R4); a guess stated as fact where a question was possible scores low; new
  major trigger for an unproven exclusive claim; a missing `mismatch` is at most minor.
- Eval case EC-11: the facts cannot show the callers of a changed API; without an IDE the
  artifact keeps an open non-blocking question and makes no "only caller" claim.

## 1.1.1
- Eval set completed to 10 cases (EC-04 to EC-10): normal cases in the sample order, support-ticket and
  library-loan systems, missing and ambiguous input, a conflict with the context pack, and the missing
  adversarial or forbidden-content case (SDD-01 §10.3, §10.4). PATCH: new eval cases only (SDD-01 §6.2).
  Needs a signed eval result for this version before any status change (SKL-V13).

## 1.1.0
- First version in the plugin (SDD-01 §12, row IA).
- R1 target status `production`. Ships 3 starter eval cases; the full set of at least 10 is needed before
  the next status change (SDD-01 §7.1, §10.3).
