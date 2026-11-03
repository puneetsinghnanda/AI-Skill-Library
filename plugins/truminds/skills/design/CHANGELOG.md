# Changelog: design

## 1.6.0
- Asks the user in the IDE before writing (AskUserQuestion), the same way impact-analysis 1.2.0
  does: an open question Q-nn for each contract choice no input fixes (field name, format or unit)
  and an assumption claim for each unproven file or type location. Writes the design from the
  answers; rule 12: never write an answer the user did not give.
- design.v1: optional `id` (CO-n, EP-n) and `cites` on components and endpoints, and an optional
  `answers` list (id, kind, about, answer, decides, mismatch). Backward compatible; fixture added.
- New check DS-C02 answers.logged (H4) with targets components, endpoints and claims, field
  decides, noun item. Claims are a target because a confirmed or corrected assumption decides its
  own claim id. answers.logged now skips target items without an `id`, so design artifacts
  written before 1.6.0 pass and requirement-review and impact-analysis are unchanged.
- Retry: tsl now passes dropped findings as `data.retry.dropped` ({id, severity, text, reason});
  the skill fixes the real ones and lists them in resolves.
- Rubric DS-R4: an item decided by a cited IDE answer is honest status; a guess stated as fact
  where a question was possible scores low. Minor trigger for an answer that differs from an input
  without a mismatch.

## 1.5.0
- Run HMS-4 needed 3 attempts: a1 described the new response field only as "a nullable last-visit date
  field", and marked the api and web list row types changed with no cite (the review finding was
  dropped, then raised again at a2).
- Rule 10 and Method step 5: every new or changed endpoint states each new or changed field (name,
  type, nullable, format or unit, example, known or assumed). Where an AC tests a value, the format
  lets it be checked exactly.
- Rule 11 and Method step 6: a file or type marked new or changed cites a module-map or impact fact,
  or goes under Assumed ("implement must confirm") or becomes a question. A sibling symbol proves the
  file, never the type.
- design.v1: optional `endpoints[].fields` (backward compatible) with fixtures.
- New check `DS-C01` contract-stated (H4, library check `contract.stated`): a new or changed endpoint
  has at least one `fields` entry.
- Retry: dropped findings in `data.retry.dropped` are fixed and listed in `resolves` when that changes
  no other item. tsl does not pass dropped findings yet; this applies once it does.
- Rubric: DS-R3 and DS-R4 descriptors; new major trigger for a new or changed field without a type and
  a format.
- Eval cases EC-11 (exact date format) and EC-12 (row types absent from the module map). MINOR: new
  rules, an optional output key and a new check (SDD-01 §6.2).

## 1.4.1
- Eval set completed to 10 cases (EC-04 to EC-10): normal cases in the sample order, support-ticket and
  library-loan systems, missing and ambiguous input, a conflict with the context pack, and the missing
  adversarial or forbidden-content case (SDD-01 §10.3, §10.4). PATCH: new eval cases only (SDD-01 §6.2).
  Needs a signed eval result for this version before any status change (SKL-V13).

## 1.4.0
- First version in the plugin (SDD-01 §12, row DS).
- R1 target status `production`. Ships 3 starter eval cases; the full set of at least 10 is needed before
  the next status change (SDD-01 §7.1, §10.3).
