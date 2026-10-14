# harness-evals/ — harness accuracy labelled set (starter)

The labelled set that `tsl harness eval` scores (SDD-03 §16, TST-01 §3.2–§3.3). Each folder under `cases/` is one
case: `case.yaml` (`harness-case.v1`, hand-written labels), `artifact.md` (an invented artifact), optional
`review.json` (a canned reviewer output for code-only cases), `inputs/` and `context/`.

**Status: starter set, draft for owner review** (owners Japman Singh, Yash Khorwal). It holds 12 cases on the invented
order-history ticket ABC-142 and the `requirement-review` skill. SDD-03 §16.1 proposes about 85 cases for the pilot;
the rest are to be written by the owners.

| Kind | Cases | Scored |
| --- | --- | --- |
| `gate` | `clean-intent-01`, `h2-missing-unknown-01`, `h2-missing-open-questions-01`, `h2-missing-out-of-scope-01` | By code, in CI |
| `citation` | `cite-fabricated-path-01`, `cite-fabricated-line-01` | By code, in CI |
| `decide` | `decide-low-score-01`, `decide-blocking-question-01`, `decide-minor-finding-01` | By code, in CI |
| `reviewer` | `reviewer-planted-retention-01`, `reviewer-injection-retention-01` (TST-01 §3.2 injection row), `reviewer-clean-01` | On a seat only: the reviewer subagent must produce `review.json` first |

## Run

```sh
cd tsl
uv run tsl harness eval --code-only --dir ../harness-evals/cases     # what CI checks
```

Without `--dir`, `tsl` reads `harness-evals/cases` next to the installed plugin's repository. The test
`tsl/tests/test_companion_harness.py::test_committed_labelled_set_is_on_target` keeps the code-scored cases on target.

## Rules

- Invented data only: no client code, names or data (T-01, TST-01 §9).
- Labels are written from the SDD rules, never copied from `tsl` output.
- Case ids are kebab-case; they are a separate series from skill eval cases `EC-nn` (registry §9).
