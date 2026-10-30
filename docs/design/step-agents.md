# Step agents: code moves a run, each step runs in its own subagent

Oct 30, 2026 · @Puneet Singh Nanda

| Field | Value |
| --- | --- |
| Status | Design note and prototype (branch `feat/step-agents`) |
| Asked by | Ekjot Singh, HMS-6 pilot feedback, issue 4 (same change as the 16 Oct mods proposal) |
| Builds on | `fix/pilot-feedback` (pre-tool refuses off-step tools, E-POL-06; failed checks go to decide) |
| Touches | [SDD-02](SDD-02-workflow-orchestration.md) §6 (`tsl next`), [SDD-03](SDD-03-harness.md) §14 (H7), [SDD-05](SDD-05-claude-code-integration.md) §4 and §5.3 (run skill, pre-tool hook) |

## 1. Problem

Today the main Claude session drives a run. `/truminds:run` loads the run skill, and the model
runs the loop in it: `tsl next`, then the step's skill *in the same session*, then `tsl verify`,
the review, `tsl review record`, `tsl decide`, and round again. Three things go wrong:

1. **The main session grows with every step.** Each step's inputs, context sections and drafts
   stay in the one conversation. By the implement step of a brownfield run the session carries
   every earlier step's reading, which costs tokens and makes the model drift from the loop.
2. **A step's tools are only checked after the fact.** The session has the run skill's tools
   (`Bash(tsl *), Read, Grep, Glob, Write, Edit`), not the step's. `fix/pilot-feedback` added the
   up-front refusal (E-POL-06), but the session still *has* the tools and keeps trying them.
3. **A step can read anything in the companion repo.** Ekjot's HMS-6 run read HMS-4's
   `artifacts/` while designing. Nothing stopped it, and nothing in H7 flags a read.

## 2. Decision

### 2.1 One subagent per step, generated from `skill.yaml`

Every step skill (every `skills/<id>/` with a `skill.yaml`) gets a subagent definition
`plugins/truminds/agents/step-<id>.md`:

| Field | Value |
| --- | --- |
| `name` | `step-<id>`; the run loop calls it as `truminds:step-<id>` |
| `tools` | exactly `allowed_tools` from `skill.yaml`, plus `Bash(tsl verify *)`: the same set SKL-V09 requires in the skill's `allowed-tools` |
| `model` | `inherit` |
| body | a short header (run `tsl verify <artifact> --inputs --json` first; read only the inputs; reply with one line) followed by the skill's `SKILL.md` body from `## Job` on |

The files are generated, never edited: `python -m tsl.orchestrator.agents plugins/truminds`
writes them, and `--check` (also run by `tsl validate` on the plugin, E-CFG-01 `/agents/...`)
fails when one is missing, stale or left over from a removed skill. A skill author changes
`skill.yaml` or `SKILL.md`, regenerates, and commits both. The plugin tests check the same rule
without importing tsl.

Each dispatch is a fresh subagent: it starts with an empty context, reads its own inputs, writes
the one artifact and returns one line. The main session sees only that line.

Why the body is copied and not loaded with the `skills:` front matter field: the skill's
`!`tsl verify $0 --inputs --json`` preamble needs `$0`, which a preloaded skill does not get. The
agent runs the same command as its first tool call instead, which also marks the step's skill as
launched (`skill_started_at`), so the pre-tool hook scopes every later call to the step.

### 2.2 The run loop moves into tsl

The prototype keeps the loop in the run and resume skills but makes the main session a
dispatcher: `tsl next` now returns `data.agent` (`truminds:step-<id>`), and loop step 2 is
"dispatch to `data.agent` with the artifact path, feedback and answers; do not read anything
yourself". The rest (verify, review, record, decide) is unchanged.

The target, in two more steps:

| Stage | What the model does | What tsl does |
| --- | --- | --- |
| Prototype (this branch) | Calls `tsl next`, dispatches the step agent, calls `verify`, the review skill, `review record`, `decide` | Names the agent; scopes the step's tools and reads |
| Stage 2: `tsl advance` | Calls `tsl advance <run_id> --json` and does what `data.dispatch` says: either an agent (`step-<id>` or `reviewer`) with a given prompt, or stop and show a message | Runs `next`, `verify`, `review record` (reading the reviewer reply from the file the loop saved), `decide`, `pr` itself, in a loop, until it needs a model or a human. The run skill shrinks to "call advance, dispatch, repeat" |
| Stage 3: headless driver | Nothing in the main session; `/truminds:run` starts `tsl drive <run_id>` | Starts each step agent headless (`claude -p --agent truminds:step-<id>` with the run's session bound), and the reviewer the same way, between its own `verify` and `decide` calls |

Stage 2 is the change that makes "code, not the main session, moves the run" true: decisions
about the next call (gate failed → decide; E-REV-02 → re-review within budget; open_pr → pr) live
in `tsl advance`, tested in Python, not in prose the model may skip. It needs one new command and
the `review record --file` path the loop already uses. Stage 3 waits on a stable way to bind a
headless session to the run lock (U-06) and is not needed for the pilot.

### 2.3 A step reads only its inputs, the context pack and the product repos

While a step's skill is open (from `tsl verify --inputs` until `tsl decide`), the pre-tool hook
now checks Read, Grep and Glob, not only Write and Bash:

| Target | Allowed |
| --- | --- |
| Outside the companion repo (product repo clones, the plugin) | yes |
| Companion `context/`, `tsl.yaml` and other files outside `artifacts/` and `runs/` | yes |
| `artifacts/<ticket>/<run_id>/...` and `runs/<run_id>/...` of **this** run | yes |
| A path `tsl next` resolved as one of this step's inputs | yes |
| Any other path under `artifacts/` or `runs/` (another ticket, another run of the same ticket) | **refused, E-POL-07** |
| A Grep or Glob over the companion root, `artifacts/` or `runs/` as a whole | **refused, E-POL-07** ("search context/, this run's artifacts or a product repo") |

For Glob the fixed part of the pattern counts (`artifacts/HMS-4/**` from the root is refused,
`artifacts/HMS-6/<run>/*.md` is allowed). Paths are compared case-insensitively, after `..` and
backslashes are normalised. Like E-POL-06 the refusal happens before the tool runs and is not
written to the tool log, so the step carries on with the right reads. Bash reads (`cat`, `ls`)
were already refused for steps by E-POL-06.

Narrowing `context/` to the step's declared `context_sections` is a follow-up: the section to file
map lives in `context/manifest.json`, and some skills legitimately read generated facts that are
not listed as sections. It is not needed to stop cross-ticket reads.

## 3. Prototype on `feat/step-agents`

| Change | Where |
| --- | --- |
| Agent generator and staleness check | `tsl/src/tsl/orchestrator/agents.py`; `tsl validate` on the plugin |
| 17 generated agents, one per step skill | `plugins/truminds/agents/step-*.md` |
| `tsl next` names the agent (`data.agent`) | `tsl/src/tsl/orchestrator/next.py`, `schemas/next-action.v1.json` |
| Read scope while a step is open, E-POL-07 | `tsl/src/tsl/hooks/pre_tool.py`, `tsl/src/tsl/core/errors.py`, registry §2 |
| Run and resume dispatch each step to its agent | `plugins/truminds/skills/{run,resume}/SKILL.md` (and `Agent` in their tools) |
| Tests | `tsl/tests/test_step_agents.py`; `plugins/truminds/tests/test_structure.py` (agents match `skill.yaml`, loop dispatches) |

Not yet checked in a live Claude Code session (needs a pilot run):

- that a plugin agent's `tools` list honours `Bash(tsl verify *)` as a pattern rather than as
  plain `Bash`. Either way the pre-tool hook already narrows Bash to `tsl verify` for an open
  step, so the step cannot run anything else;
- that hooks see the subagent's tool calls under the parent `session_id` (documented behaviour;
  the run binding and H7 tool log depend on it).

## 4. Shipping the `truminds-runs` progress panel

The panel exists only as a local mod (`~/.claude/dev-mods/<id>/truminds-runs`): a desktop-app
plugin whose `hooks/hooks.json` is `{ "modules": ["./register.tsx"] }`. It lists `runs/*/state.json`
in the session's folder every 4 s and right after a `tsl` command, and draws each run's steps,
attempts, bands and PRs in a side pane.

Plan:

1. **Ship it as a second plugin in this marketplace, not inside `truminds`.** Its hooks file is a
   module list, and `tsl validate` requires the truminds `hooks/hooks.json` to list exactly the
   SDD-05 §5.2 command hooks. Move it to `plugins/truminds-runs/` and add it to
   `.claude-plugin/marketplace.json`. Users who install `truminds` add the panel with one more
   `/plugin install`; managed settings can enable both.
2. **Pin it with the harness.** Give it the same version as `truminds` and tsl, and add a plugin
   test that the two versions match (as `test_plugin_version_equals_tsl_version` does).
3. **Read a contract, not `state.json`.** `state.json` (run-state.v1) is internal. Add
   `tsl state list --json` returning `status.v1` rows, or read the existing `tsl state show`; the
   panel then calls it through the engine's command runner instead of parsing files. Until then,
   pin the fields it reads in a test fixture so a run-state change fails CI.
4. **Show the step agent.** With this change the panel can show which `step-<id>` agent is
   running and whether the step is open, from `cursor` and `skill_started_at`.
5. **CI.** Run its `tests/pane.test.tsx` and a type check in the plugin job, next to the Python
   plugin tests. Keep `.claude-plugin/types/` generated and ignored, as the mod does now.
6. **Docs.** One paragraph in SDD-05 §7 (packaging) and the onboarding guide.

## 5. Risks

| Risk | Mitigation |
| --- | --- |
| Agent files drift from the skills | Generated; `--check`, `tsl validate` and the plugin tests fail on drift |
| A subagent cannot ask the user (blocking questions) | Unchanged: steps never ask; they write open questions and `tsl decide` pauses the run (NEEDS-INPUT) |
| More tokens per run from repeated system prompts | Each agent reads only its own inputs; the main session no longer carries every step, which is the larger cost |
| A step needs a file outside its inputs (e.g. an older run's design) | Declare it as a workflow input binding; tsl resolves and hashes it, and the hook then allows it |
