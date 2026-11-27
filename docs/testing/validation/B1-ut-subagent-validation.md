# B1 validation: `ut` as a forked subagent

| Field | Value |
| --- | --- |
| Status | Draft |
| Owner and approver | Gaurav Saini |
| Roadmap item | B1 (Skill Library Roadmap 25–27 Nov) |
| Validators | Japman (Windows), Shubham (Ubuntu) |
| Branch | `feat/ut-subagent` (includes PR #65, `feat/step-allowed-tools`) |
| Due | Fri 27 Nov: a results table and a go / no-go for `ut` |

## 1. What changed

**Change 1: each step is told its allowed tools (PR #65)**
- `tsl verify <artifact> --inputs` now returns `data.allowed_tools`. That is the skill's `allowed_tools` plus `Bash(tsl verify *)`.
- All 17 step skills now say: "Use only the tools in data.allowed_tools … Bash runs only `tsl verify`."
  - Before this change, steps learned their tools from E-POL-06 refusals.
  - Each of those skills got a minor version bump and a CHANGELOG entry.
- The hooks now log `agent_type` in `tool-log.jsonl` and `hook.log` when a call comes from a subagent. That is how we can tell which calls ran inside the step subagent.

**Change 2: a step can run in a forked subagent (`feat/ut-subagent`)**
- You switch it on with the environment variable `TSL_STEP_RUNNER`, for example `ut=full` or `ut=artifacts`. When it is not set, nothing changes.
- `tsl state start` reads the variable once and keeps the choice in `state.json` as `step_runners`. It is then fixed for the whole run.
- For a step listed there, `tsl next` adds `data.runner` to the step's `run_skill` action. The `run` skill then invokes the internal `step` skill instead of `truminds:unit-test`.
- The `step` skill has `context: fork` and runs as the `truminds:step-runner` agent. That agent has only Read, Grep, Glob, Write, Edit and Bash, and the hook still limits Bash to `tsl verify`.
- Its preamble runs `tsl step brief <artifact> --context <c>`, which does four things:
  - It gives the subagent the same SKILL.md text as the main session. The `--inputs` preamble is replaced by its JSON data.
  - It adds the run's open questions.
  - With `full` (option b), it preloads the step's context-pack sections and this run's answers, up to half the step's token budget. With `artifacts` (option a), it preloads nothing, and the subagent reads files itself as the skill says.
  - It records `"runner": {"mode": "fork", "context": ...}` on the attempt in `state.json`.
- Verify, review and decide still run in the main session, as before.

## 2. Install the branch

The steps match the setup guide §7a, but use the branch instead of `main`. Run them from your clone.

```bash
git fetch origin
git checkout feat/ut-subagent
git pull
```

Reinstall `tsl` with `TSL_ORG_FILE` set. Never use `--editable`.

Windows (PowerShell):
```powershell
$env:TSL_ORG_FILE = "$PWD\deploy\render\tsl-org.github.toml"
uv tool install --python 3.12 --reinstall --no-cache .\tsl
Remove-Item Env:TSL_ORG_FILE
```

Ubuntu:
```bash
TSL_ORG_FILE="$PWD/deploy/render/tsl-org.github.toml" uv tool install --python 3.12 --reinstall --no-cache ./tsl
```

Update the plugin, then restart Claude Code:
```text
claude plugin marketplace update truminds-skill-library
claude plugin update truminds@truminds-skill-library
```

Check, before any run:
- `tsl step --help` lists `brief`. If it doesn't, the old `tsl` is still on your PATH.
- `tsl doctor` has no ✖ line.
- `claude plugin list` shows the truminds plugin from your clone.

Finish or stop any run you have open before you switch branches.

## 3. The ticket

Use **HMS-34**: "Mark past appointments that were not completed or rescheduled as Stale".
- It adds a new appointment status, so it touches the database, the API and the UI. That makes it a good test for `ut`.
- I ran it on Windows on Wed, so we can compare across OSes. Copy the ticket file from `tickets/HMS-34.md` (ask me for it) into the tickets folder next to your companion clone.
- Give the same answers in every run. Write down the questions and your answers in run 1, then reuse them.
- If you have time, repeat with HMS-23 (the golden run), which already has a main-session baseline.

## 4. The three runs

Run them one after another in your companion clone, each in a **new Claude Code session**. Set the variable in the shell before you start Claude Code. Then every `tsl next` sees it, and no command needs a prefix or an extra approval.

| Run | What | Start Claude Code with |
| --- | --- | --- |
| 1 | Subagent, option (b): artifacts + context pack + answers | PowerShell: `$env:TSL_STEP_RUNNER = "ut=full"; claude` · bash: `TSL_STEP_RUNNER=ut=full claude` |
| 2 | Subagent, option (a): previous artifacts only | `ut=artifacts` the same way |
| 3 | Baseline: main session, as today | Unset the variable first. PowerShell: `Remove-Item Env:TSL_STEP_RUNNER`; bash: start a new terminal, or `unset TSL_STEP_RUNNER` |

In each session:
```text
/truminds:run brownfield-small HMS-34 ../tickets/HMS-34.md
```

The runner is read once, when the run starts, and kept in `state.json` (`step_runners`). After that, `tsl next` ignores the variable. So:
- At the start of each run, the session tells you which steps run in a subagent, from `data.step_runners`. Runs 1 and 2 must show `ut` with the context you chose. Run 3 must show none.
- If the start doesn't show what you expect, cancel that run and start again in a new session.
- Putting the variable in front of `tsl next` does nothing. It has to be set before Claude Code starts.

While a run goes:
- At `ut` in runs 1 and 2, the transcript should show the `step` skill starting a subagent, not `truminds:unit-test`.
- Do not answer for the run. Do not use other tools while a step is open.
- Each run opens a PR on the sample app. Close the PRs afterwards.
- Note anything odd as you go: refusals, a hang, the subagent asking you something, a hook blocking a write.

## 5. What to check

Do this in a **new session after all runs** (a session that holds a run cannot read other runs). Read only; do not change anything in `runs/` or `artifacts/`.

**Sanity checks (runs 1 and 2).** Each one is pass or fail.

| Check | Where | Expected |
| --- | --- | --- |
| Runner recorded | `runs/<id>/state.json`, step `ut`, each attempt | `"runner": {"mode": "fork", "context": "full"}` (or `"artifacts"`). Run 3: no `runner` |
| Calls ran in the subagent | `runs/<id>/tool-log.jsonl`, lines in the `ut` window | `"agent_type": "truminds:step-runner"`. Run 3: no `agent_type` |
| H7 (tool window) passed | the `ut` checks record next to the ut artifact | H7 pass on every attempt |
| No refusals | `runs/<id>/tool-log.jsonl`: lines with `"decision": "deny"` in the `ut` window (also in `~/.truminds/logs/hook.log`) | no E-POL-06 inside `ut`; list any E-POL-04/05/06 with the call refused |
| Artifact written | `artifacts/HMS-34/<id>/ut...` | exists, and the run got past `ut` |

**Comparison: one column per run.**
- Number of attempts. Was the first attempt a pass (verifier H3 and review)?
- Final band and review score.
- Retries, and what caused each one: checks, verifier build, lint, tests, or a review finding.
- E-POL-06 refusals in the step.
- Tool calls, by tool.
- Wall time of `ut`, from `skill_started_at` to `decided_at` of the last attempt.
- Tests run and passed, and coverage, from the verifier.
- Questions raised.
- Tokens: from the session transcript and the subagent transcript under `~/.claude/projects/`. If you can't find them, write "n/a". Don't estimate.

Also note whether `req`, `split`, `design` or `impl` came out differently between the runs: different answers, retries, or a larger impl diff. If they did, the `ut` comparison is weaker, so say so.

The easiest way is a fresh Claude Code session in the companion repo:

> Read runs `<id1>`, `<id2>`, `<id3>` (state.json, tool-log.jsonl, the ut checks and review records, ~/.truminds/logs/hook.log for their time windows). Read only. Fill in the sanity checks and the comparison table from docs/testing/validation/B1-ut-subagent-validation.md §5 in the AI-Skill-Library repo. Say where each number came from, and never estimate.

## 6. What to send back

Send it by Fri 27 Nov midday, either as a reply to me or as `docs/testing/validation/B1-<os>-results.md` in a PR:
1. Your environment: OS, Claude Code version, `tsl --version`, and the branch commit (`git rev-parse --short HEAD`).
2. The run ids and PR links.
3. The sanity-check table and the comparison table.
4. Anything that broke, with the error text. Log it, don't fix it.
5. Your call: would you keep `ut` in a subagent? If so, `full` or `artifacts`?

With 1 run per option per OS, this is a first signal, not proof. I'll combine Windows (mine and Japman's) and Ubuntu (Shubham's) into one table and the go / no-go.

## 7. Known limits

- A forked subagent can't ask the user questions, so `req` and `design` stay in the main session until B2. `ut` raises questions only in its artifact.
- Token counts per step need D1. Until it lands, tokens come from transcripts or are "n/a".
- Setting `TSL_STEP_RUNNER` for one step leaves every other step in the main session.
