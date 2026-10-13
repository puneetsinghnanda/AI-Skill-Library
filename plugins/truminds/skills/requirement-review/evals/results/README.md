# Signed eval results

`tsl eval run requirement-review` writes `<version>.eval-result.json` (eval-result.v1) here, signed with the
skill author's key and bound to the skill's content hash (SDD-01 §6.2, §10.2). Results are produced on a
company seat, never in CI and never by hand.
