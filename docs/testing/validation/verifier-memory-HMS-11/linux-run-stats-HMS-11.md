# Linux run stats: HMS-11 workflow memory

| Field | Value |
| --- | --- |
| Status | Submitted |
| Owner | Yash Khorwal |
| Approver | Puneet Singh Nanda |
| Roadmap item | 10: find why memory ran low during implement |
| Measured | 18 Nov 2026 (real run: 12 and 16 Nov 2026) |

Raw numbers. The before/after summary is in the folder [README](README.md).

## Machine

| Item | Value |
| --- | --- |
| CPU | 11th Gen Intel Core i7-1165G7 @ 2.80 GHz, 8 logical CPUs (the same CPU as the Windows pilot laptop for HMS-8, HMS-9 and HMS-15) |
| RAM | 15.4 GB (16,114,496 kB), swap 2 GB |
| OS | Ubuntu 22.04.5 LTS, kernel 6.8.0-138-generic |
| Docker | 28.0.4, native (no VM), overlay2, cgroup v2 (systemd driver) |
| tsl | 0.1.6 for the real run and the "before" runs; this change for the "after" runs |
| Claude Code | 2.1.327 |
| Verifier | profile `node-22@1`, image `verifier-node-22@sha256:b7bc7f90…1dc4d`, limits `--cpus 2 --memory 4g --pids-limit 512` |

## 1. The real HMS-11 run (`run_01M77BM48R93EMY13TZXCDN7PZ`)

From the run's checks records. Stage times in seconds.

| Step, attempt | Date | build | test | lint | sast | secrets | coverage |
| --- | --- | --- | --- | --- | --- | --- | --- |
| impl a1 | 12 Nov | 6.3 | 33.0 | 3.2 | 16.6 | 0.3 | (not run) |
| ut a1 | 12 Nov | 5.9 | 34.9 | 3.4 | 16.8 | 0.3 | skip (exit 78) |
| ut a2 | 12 Nov | 5.6 | 36.0 | 3.4 | 16.5 | 0.2 | skip (exit 78) |
| ut a3 | 16 Nov | 11.7 | 37.2 | 6.6 | 23.5 | 0.5 | skip (exit 78) |

- Every stage exited 0 (no exit 137, so no out-of-memory kill), and the run has no E-H3-09 or other E-H3 code.
- The kernel log (12 and 16 Nov boots) and systemd-oomd (12–17 Nov) show no OOM kills.
- Coverage is skipped because the sample app has no `coverage` script.
- No sampler was running during the real run, so the container peaks below come from re-running the verifier.

## 2. Verifier runs on the HMS-11 code

tsl's `DockerVerifier.run`, with coverage (as in the ut step). Sampled 4 times a second; the peak is the container's
cgroup `memory.peak`. Runs 1–2 use `main`; runs 4–5 use this change (test workers follow the CPU limit). Run 3 (CPU
pinning with `--cpuset-cpus`, not adopted) is described in the note at the end.

### Peak memory per step (MB)

| Step | Run 1, before | Run 2, before | Run 4, after | Run 5, after |
| --- | --- | --- | --- | --- |
| prepare | 887 | 532 | 643 | 532 |
| build | 305 | 308 | 304 | 308 |
| **test** | **739** | **724** | **428** | **401** |
| lint | 340 | 306 | 306 | 280 |
| sast | 613 | 550 | 618 | 554 |
| secrets | 7 | 17 | 4 | 0 |
| coverage | 0 (skipped) | 0 (skipped) | 0 (skipped) | 0 (skipped) |
| **Highest step** | **887 (22% of 4 GB)** | **724 (18%)** | **643 (16%)** | **554 (14%)** |

### Breakdown at the peak (MB): anon / file (page cache) / tmpfs

| Step | Run 1 | Run 2 | Run 4 | Run 5 |
| --- | --- | --- | --- | --- |
| prepare | 536 / 304 / 0 | 362 / 144 / 0 | 361 / 244 / 0 | 379 / 143 / 0 |
| test | 646 / 236 / 210 | 633 / 210 / 210 | 294 / 148 / 121 | 299 / 115 / 115 |
| sast | 537 / 65 / 6 | 536 / 6 / 6 | 540 / 67 / 6 | 540 / 6 / 6 |

### Step time (s)

| Step | Run 1 | Run 2 | Run 4 | Run 5 |
| --- | --- | --- | --- | --- |
| prepare | 40.5 | 4.7 | 7.0 | 6.0 |
| build | 5.9 | 6.3 | 9.0 | 8.8 |
| **test** | **26.5** | **29.1** | **24.3** | **24.3** |
| lint | 3.0 | 3.1 | 4.3 | 4.6 |
| sast | 15.8 | 16.3 | 19.4 | 20.2 |
| secrets | 0.4 | 0.3 | 0.4 | 0.4 |
| coverage | 0.3 | 0.3 | 0.3 | 0.4 |

Run 1's prepare fetched packages from the registry; the other runs used the npm cache volume. Runs 4–5 were taken
later the same day with other programs open, which explains the slower build, lint and sast (the change does not
touch those steps). The test step is still faster.

### Test workers and test results

| | Before (runs 1–2) | After (runs 4–5) |
| --- | --- | --- |
| vitest workers seen at once | 7 (`vitest 1` … `vitest 7`), 60–155 MB each | 2 |
| Why | `os.availableParallelism()` reports the host's 8 cores; `--cpus 2` does not change it | `VITEST_MAX_FORKS=2`, `VITEST_MAX_THREADS=2` (min 1) passed by `docker run -e` |
| Test files and tests | 1 + 15 + 6 files, 8 + 122 + 35 = 165 tests, all pass | the same |

### Host memory (GB available)

| | Run 1 | Run 2 | Run 4 | Run 5 |
| --- | --- | --- | --- | --- |
| Before the verifier | 9.84 | 9.66 | 11.41 | 11.22 |
| Lowest during it | 9.08 | 9.09 | 10.63 | 10.32 |

## 3. Low-memory warning thresholds against the Windows pilot samples

Free RAM sampled once a minute on the Windows pilot laptop (i7-1165G7, 15.7 GB, Docker Desktop on WSL2) in
`memory-diagnosis` samples v1.

| Run | Samples | Free RAM min–max | Below 5.5 GB (old) | Below 1.5 GB (new) | Sampled verifier starts: old warns / new warns |
| --- | --- | --- | --- | --- | --- |
| HMS-8 | 72 | 1.39–4.16 GB | 72 (100%) | 2 (3%) | 5 / 0 |
| HMS-9 | 154 | 1.02–4.46 GB | 154 (100%) | 3 (2%) | 4 / 0 |
| HMS-15 | 215 | 0.68–5.12 GB | 215 (100%) | 12 (6%) | 0 / 0 |

## 4. Hooks

Real launcher `plugins/truminds/bin/tsl-hook`, 5 calls each, under `/usr/bin/time`. The calls ran against a copy of the
companion repo with a test session bound to an active run, using a temporary home folder.

| Hook | Runs on | Time avg (min–max) | Peak RSS |
| --- | --- | --- | --- |
| pre-tool (Read, Bash, Write) | every tool call | 0.03–0.04 s | 17–18 MB |
| post-write (early exit, E-RUN-09) | Write, Edit | 0.21 s (0.18–0.26) | 45 MB |
| post-write self-check (`tsl verify --self-check`) | Write, Edit of an artifact | 0.22–0.23 s | 44–45 MB |
| session-start | once per session | 0.20 s (0.20–0.21) | 46 MB |
| session-end | once per session | 1.05 s (0.75–2.10) | 47 MB |

Inside tsl, the pre-tool decision takes under 1 ms; the rest is process start. Hooks run one at a time and exit.

## 5. Claude Code and subagents

Subagents run inside the `claude` process. One session after about 80 minutes: 472 MB RSS (`ps`).

## 6. The workflow's peak, added up

| Part | Peak |
| --- | --- |
| Verifier container (highest step) | 0.55–0.89 GB before this change, 0.55–0.64 GB after |
| Claude Code (including subagents) | about 0.47 GB |
| Docker daemon (dockerd, containerd) | about 0.15 GB |
| One hook process | ≤ 0.05 GB |
| **Total** | **about 1.5 GB** |

## Note: CPU pinning (run 3, not adopted)

Pinning the container to two cores (`--cpuset-cpus 0,1`) gave the same effect: test step 402 MB, 21.3 s. It was not
adopted: it ties every run to cores 0 and 1. Setting the worker count instead leaves CPU scheduling to Docker.

## Data

`samples/run*/machine.csv` (host memory) and `samples/run*/containers.csv` (each container's current and peak memory)
for runs 1, 2, 4 and 5. The scripts are in `tools/`.
