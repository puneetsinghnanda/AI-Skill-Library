# Changelog: requirement-review

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
