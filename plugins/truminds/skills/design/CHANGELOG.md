# Changelog: design

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
