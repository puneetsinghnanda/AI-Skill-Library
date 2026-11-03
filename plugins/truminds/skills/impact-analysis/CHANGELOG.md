# Changelog: impact-analysis

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
