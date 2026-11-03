# Changelog: story-split

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
