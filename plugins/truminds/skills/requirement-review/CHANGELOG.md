# Changelog: requirement-review

## 1.5.0
- Roadmap 25-27 Nov, B (each step knows its tools): the step was never told its allowed
  tools and learned them from pre-tool refusals (E-POL-06), even for a read-only `grep`.
  tsl verify --inputs now lists them in data.allowed_tools, and the preamble says to use
  only those.
- AskUserQuestion is now in allowed_tools: the skill asks the user before it writes, and
  "use only data.allowed_tools" must not forbid that (review of #65).
- MINOR: changed instruction and one added tool; same inputs and output schema. Needs a
  signed eval result for this version before any status change (SKL-V13).

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
  and data.prior_answers); only decisions are put to the user in the IDE; facts are looked up in
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

## 1.1.0
- Before writing, the skill asks the user every open question and confirms every assumed
  requirement in the IDE (AskUserQuestion), then writes the requirements from the answers.
- The tsl post-tool hook records each answer in `runs/<run_id>/ide-answers.md` (A-nn, with
  who answered). Requirements cite `runs/<run_id>/ide-answers.md#a-nn`; confirmed
  assumptions become `known`. New optional `answers` list in `intent.v1`.
- New check RR-C13 (`answers.logged`, H4): the artifact's answers match the log exactly,
  none is left out, and each requirement an answer decided cites it.
- Skipped questions, or runs without an IDE (evals), fall back to open questions and the
  existing pause for input.
- The user's answer always decides the requirement, even when it differs from the ticket or
  baseline. The difference is recorded in the answer's `mismatch` (text and cites), not
  raised as a question or finding. Rubric: a requirement written from a cited answer is
  honest status; a missing `mismatch` is at most a minor finding.

## 1.0.0
- First version, as specified in SDD-01 §13: SKILL.md, rubric RR-R1..R6, checks RR-C01..C12,
  ten invented eval cases (EC-01..EC-10), good and bad examples.
- Status `draft`. Promotion to `pilot` needs a signed eval result for this exact version (SDD-01 §7.1).
