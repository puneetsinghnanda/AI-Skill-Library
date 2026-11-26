# benchmarks/: the brownfield lite benchmark (roadmap E1)

A fixed set of tickets, rerun on every release, and a script that turns their run records into
one table: retries (and why), first-attempt pass, AI time, engineer wait and tokens per step,
by OS.

| File | What it is |
| --- | --- |
| `set.json` | The runs: the fixed set (`bench: true`: HMS-23, HMS-24, HMS-33) and the other 0.1.7 baseline runs |
| `bench_report.py` | The report script. Python 3.10+, standard library only |
| `metrics/<run_id>.json` | Token exports (`tsl state show <run> --metrics --json`) for runs from before D1 |
| `results/baseline-0.1.7.md` | The baseline table: the 8 brownfield lite runs on 0.1.7 |
| `tests/` | Tests on invented runs (`make test-bench`) |

## The fixed set

- **HMS-23**: the golden run (Windows).
- **HMS-24** (Linux): `impl` build slip and review retries in `split` and `ut`.
- **HMS-33** (Windows): build and lint slips in the generated tests used all of `ut`'s retries.

Between them they cover both OSes and the R1 target: no retry used by a build or lint slip.

## Run it

From the repo root, against the companion repo (no checkout or pull needed with `--ref`):

```sh
python3 benchmarks/bench_report.py --companion ../cl-int-sys-smp2-companion --ref origin/main
python3 benchmarks/bench_report.py --companion ... --ref origin/main --bench-only   # fixed set only
python3 benchmarks/bench_report.py --companion ... --release 0.1.7 --out benchmarks/results/baseline-0.1.7.md
python3 benchmarks/bench_report.py --companion ... --format json                    # for other tools
```

## Each release

1. Rerun HMS-23, HMS-24 and HMS-33 on the new release.
2. Add each run to `set.json` with its `release` and `bench: true`.
3. Regenerate the report: when the set holds more than one release, it adds a "Benchmark set by
   release" section comparing the fixed set across releases.

## Where the numbers come from

| Column | Source |
| --- | --- |
| Retries, why | Attempts with cause `retry_*` in `state.json`; the reason comes from the previous attempt's `feedback/<step>.a<n>.json` (review findings, verifier `build`/`lint`/`test` exit, harness checks) |
| 1st-attempt pass | Attempt 1's outcome is PASS or PASS-WITH-FINDINGS |
| AI min | D1 `metrics.active_ms`; before D1, the attempt's wall time less the B2 wait, or with questions included when there is no B2 record |
| Wait min | D1 `metrics.wait_s`, else `ide-questions.json` (B2); `n/r` before B2 |
| Questions | `## A-nn` entries in `ide-answers.md` |
| Tokens | D1 `metrics.tokens`, else an export in `metrics/`; `n/r` otherwise |
| OS | The set's `os`, else the absolute paths in `tool-log.jsonl` |

The 0.1.7 runs were made before B2 and D1, so wait is `n/r` for all of them, and tokens are known
only where the run's owner still has the Claude Code transcripts. The owner can add them from
the companion root with a tsl that has D1:

```sh
tsl state show <run_id> --metrics --json > <this repo>/benchmarks/metrics/<run_id>.json
```

Only the tokens are taken from an export. D1 reports a wait of 0 for runs from before B2, and
that is "not recorded", not "no wait".
