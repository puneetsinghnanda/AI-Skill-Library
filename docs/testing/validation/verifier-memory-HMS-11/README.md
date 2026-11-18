# Verifier memory: evidence for the low-memory warning and test-worker changes

Measured on 18 Nov 2026 for roadmap item 10 ("find why memory ran low during implement"). The verifier was run on the
HMS-11 code from the sample app (branch `tsl/HMS-11/run_01M77BM48R93EMY13TZXCDN7PZ`), the same code the HMS-11
unit-test step verified. Machine: i7-1165G7, 8 logical CPUs, 15.4 GB RAM, Ubuntu 22.04, native Docker 28.0.4
(cgroup v2). Full numbers: [linux-run-stats-HMS-11.md](linux-run-stats-HMS-11.md).

## Before and after

### Test workers follow the 2-CPU limit

| Test step | Before (`main`, runs 1–2) | After (this change, runs 4–5) | Change |
| --- | --- | --- | --- |
| vitest workers | 7 | 2 | −5 |
| Container peak (`memory.peak`) | 739 / 724 MB | 428 / 401 MB | **−43%** (avg 732 → 415 MB) |
| tmpfs at the peak | 210 MB | 121 / 115 MB | −44% |
| Step time | 26.5 / 29.1 s | 24.3 / 24.3 s | **−13%** (avg 27.8 → 24.3 s) |
| Tests run | 22 files, 165 tests, all pass | 22 files, 165 tests, all pass | none |

The highest step of a whole verifier run was 887 / 724 MB before, and 643 / 554 MB after. The 4 GB container limit
is unchanged.

### Low-memory warning

| | Before | After |
| --- | --- | --- |
| Warns below | 5.5 GB free (4 GB limit + 1.5 GB) | 1.5 GB free |
| Says | "may use up to 4 GB" | "needs about 1 GB (its limit is 4 GB)", plus the top 3 memory users |
| Windows pilot samples (HMS-8, HMS-9, HMS-15) below the threshold | 441 of 441 (100%) | 17 of 441 (2–6% per run) |
| At the 9 sampled verifier starts | warned 9 times | warned 0 times |

The workflow's measured peak is about 1.5 GB in total (verifier container ≤ 0.89 GB, Claude Code about 0.47 GB, Docker
daemon about 0.15 GB, one hook ≤ 0.05 GB). So 1.5 GB free is the point where a run can really run short.

## Files

| Path | Contents |
| --- | --- |
| [linux-run-stats-HMS-11.md](linux-run-stats-HMS-11.md) | All measured numbers: the real HMS-11 run, verifier runs before and after, hooks, Claude Code |
| `samples/run1-before/`, `samples/run2-before/` | `machine.csv` and `containers.csv` from the verifier on `main` |
| `samples/run4-after/`, `samples/run5-after/` | The same files from the verifier with this change |
| `tools/sample-linux.py` | Sampler: host memory and each container's cgroup `memory.peak` (anon, file, tmpfs), 4 times a second |
| `tools/run-verifier.py` | Runs tsl's `DockerVerifier` as the unit-test step does and logs when each step starts |
| `tools/analyse-verifier-run.py` | Lines the samples up with the steps: peak per step |

To reproduce, from the folder that holds `AI-Skill-Library` and the sample app:

```text
python3 sample-linux.py --out <samples-dir> --duration 400 &
uv run --project AI-Skill-Library/tsl python run-verifier.py AI-Skill-Library/plugins/truminds <product-repo> <out-dir>
python3 analyse-verifier-run.py <samples-dir> <out-dir>
```
