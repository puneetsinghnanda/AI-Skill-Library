# truminds — the Truminds AI Skill Library plugin for Claude Code

The `truminds` plugin brings the Release-1 SDLC skills, the workflows that chain them and the quality-harness hooks
into Claude Code. It runs only in **local** sessions of the Claude desktop app (Code tab) or the Claude Code CLI on a
company seat (C-16), natively on Windows (C-17). There are no Claude API calls. Every pass or fail decision is made
by code in `tsl` (SDD-04); the model only proposes.

## Layout

```text
plugins/truminds/
├─ .claude-plugin/plugin.json      name truminds; version must equal the tsl version (SDD-05 §3.2, §7.1)
├─ skills/
│  ├─ run, resume, status, eval, improve, context-draft    command skills: /truminds:<name> (registry §3.2)
│  ├─ review/                      harness review step; forks truminds:reviewer (SDD-05 §4.4)
│  └─ <17 SDLC skills>/            SKILL.md, skill.yaml, rubric.md, checks.yaml, CHANGELOG.md, evals/ (SDD-01)
├─ agents/reviewer.md              read-only reviewer subagent (Read, Grep, Glob)
├─ hooks/hooks.json                SessionStart, PreToolUse (2), PostToolUse, SessionEnd → bin/tsl-hook
├─ bin/tsl-hook, bin/tsl-hook.cmd  hook launcher: version check, stdin pipe, fail-closed/fail-open rules
├─ workflows/<id>.workflow.yaml    workflow.v1 files (SDD-02)
├─ policy/policy.yaml              org policy.v2 read by the pre-tool and pre-mcp hooks (SDD-05 §6.4)
└─ tests/                          structural, deny-list and hook-launcher tests (pytest)
```

Pods are not part of the plugin: they live at the repository root in `pods/<id>/` because Claude Code never needs
them at run time (SDD-10 §3.1). The spike plugin lives in `spikes/` (SDD-05 §8).

## Install

**Production:** IT force-enables the plugin through managed settings (`managed-settings/`, SDD-05 §6). Engineers
cannot switch it off. Then install `tsl` at the same version:

```bash
uv tool install "truminds-tsl @ <release wheel URL for v<plugin version>>"
tsl doctor
tsl login
```

**Development seats only** (production managed settings block this, see DEV-01 §5):

```bash
claude plugin marketplace add ./                      # from the repository root
claude plugin install truminds@truminds-skill-library
uv tool install --editable ./tsl --force              # tsl version must equal plugin.json version
```

Open the desktop app, Code tab, **Local** session on a companion repo, and type `/truminds:status`.

## Commands

| Command | First thing it does (runs as code before the model reads the skill) |
| --- | --- |
| `/truminds:run <workflow> <ticket>` | `` !`tsl state start $0 $1 --json` ``, then the SDD-02 §7 loop |
| `/truminds:resume <run_id>` | `` !`tsl state resume $0 --json` ``, then the same loop |
| `/truminds:status [run_id]` | `` !`tsl state show $0 --json` `` |
| `/truminds:eval <skill> [version]` | `` !`tsl eval plan $0 --json` `` |
| `/truminds:improve <skill>` | `` !`tsl improve plan $0 --json` `` |
| `/truminds:context-draft <section>` | `` !`tsl context draft-prepare $0 --json` `` |

Every command skill sets `disable-model-invocation: true`, so only a person typing the command starts it.

## SDLC skills (SDD-01 §12)

| Skill | Code | Role | Phase | Output | Version | Status | Eval cases |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `requirement-review` (reference, SDD-01 §13) | RR | business-analyst | requirements | `intent.v1` | 1.0.0 | draft | 10 |
| `story-split` | SS | business-analyst | requirements | `stories.v1` | 1.0.0 | production | 3 |
| `impact-analysis` | IA | solution-architect | design | `impact.v1` | 1.1.0 | production | 3 |
| `design` | DS | solution-architect | design | `design.v1` | 1.4.0 | production | 3 |
| `implement` | IM | developer | build | code + `change.v1` | 1.0.0 | production | 3 |
| `unit-test` | UT | developer | build | tests + `ut-result.v1` | 1.0.0 | production | 3 |
| `defect-triage` | DT | developer | operate | `triage.v1` | 1.0.0 | production | 3 |
| `test-plan` | TP | qa-engineer | test | `test-plan.v1` | 1.0.0 | production | 3 |
| `test-automation` | TA | qa-engineer | test | test code + `test-result.v1` | 1.0.0 | pilot | 3 |
| `threat-model` | TM | security | design | `threat-model.v1` | 1.0.0 | production | 3 |
| `secure-code-review` | SC | security | build | `secure-review.v1` | 1.0.0 | production | 3 |
| `pipeline-review` | PL | devops | operate | `pipeline-review.v1` | 1.0.0 | pilot | 3 |
| `deployment-failure-analysis` | DF | devops | operate | `deploy-failure.v1` | 1.0.0 | pilot | 3 |
| `ux-flow-review` | UF | ux-designer | design | `ux-flow.v1` | 1.0.0 | pilot | 3 |
| `accessibility-review` | AR | ux-designer | design | `a11y.v1` | 1.0.0 | pilot | 3 |
| `estimate-review` | ER | delivery-manager | requirements | `estimate.v1` | 1.0.0 | production | 3 |
| `status-report` | SR | delivery-manager | operate | `status.v1` | 1.0.0 | production | 3 |

Every SDLC skill body starts with the input check `` !`tsl verify $0 --inputs --json` `` and has the sections Job,
Inputs, Rules, Method, Output, If this is a retry and Hand-over (SDD-01 §3.2). Status is the Release-1 target status
from SDD-01 §12; `requirement-review` stays `draft` as SDD-01 §13.1 specifies. **The 16 non-reference skills ship 3
starter eval cases each.** Their `skill.yaml` and `eval-set.yaml` still declare `min_cases: 10` (the schema minimum),
so `tsl validate` (SKL-V10) and `/truminds:eval` will report them short until the full sets are written; see "Gaps".
All eval data is invented: the sample order system, plus a support-ticket and a library-loan system for
`requirement-review` EC-08 to EC-10. Fake secrets use the reserved `FAKE-KEY-*` pattern (SDD-01 §10.4), inside `evals/**` only.

## Workflows (SDD-02, Doc 3 §7.1)

| Workflow | Steps | Gates | Kind | Status |
| --- | --- | --- | --- | --- |
| `brownfield-change` | req → split → impact → design → G-design → threat → impl → ut → secrev → tplan → PR | G-design, PR review | delivery | draft |
| `greenfield-feature` | req → split → design (intent baseline) → G-design → threat → impl → ut → secrev → tplan → PR | G-design, PR review | delivery | draft |
| `defect-fix` | triage → impl → ut → PR | PR review | delivery | production |
| `ux-review` | uxflow → a11y → G-ux-comments | comment approval | read_only | pilot |
| `estimate` | est | none | read_only | production |
| `quality-uplift` (proposed, SDD-10 §4.2) | req → split → tplan → tauto → PR | PR review | delivery | draft |
| `security-review` (proposed) | threat → G-threat-review | threat review | read_only | draft |
| `pipeline-check` (proposed) | pipe | none | read_only | draft |
| `deploy-failure` (proposed) | dfa | none | read_only | draft |

`brownfield-change` is SDD-02 §4 verbatim plus the `status` field that registry §10 row 24 made required. A
workflow's status is never above the lowest status of its skills (SDD-01 §7), so the two workflows that start with
`requirement-review` are `draft`. The four proposed workflows exist so the Quality and Security Pod resolves
(POD-V04); SDD-02 has not confirmed them (SDD-10 O-03).

## Hooks and the launcher (SDD-05 §5)

`hooks.json` is SDD-05 §5.2 unchanged. Every hook runs `bin/tsl-hook <event>`, which:

1. finds `tsl` (PATH, then `~/.local/bin/tsl`);
2. checks `tsl --version` equals `version` in `.claude-plugin/plugin.json`;
3. pipes the hook JSON on stdin to `tsl hook <event>` and passes its stdout through unchanged;
4. stops `tsl` at its own deadline (12 s session hooks, 8 s pre-tool and pre-mcp, 85 s post-write), just under the
   `hooks.json` timeouts, so the launcher and not Claude Code decides what a slow `tsl` means (spike S-15);
5. applies SDD-05 §5.4 when `tsl` is missing, outdated, crashes or times out:

| Hook | Inside a run | Outside a run |
| --- | --- | --- |
| pre-tool, pre-mcp | deny with `E-HOOK-01` and the install command (fail closed) | allow: exit 0, no output (fail open) |
| post-write | allow, `systemMessage` warning (fail open) | same |
| session-start, session-end | missing or wrong version: `systemMessage` with the install command; crash or timeout: ignored, logged | same |

"Inside a run" means a run lock file `runs/active/<ticket>__<workflow>.lock` exists (registry §8). The launcher
finds it through this session's index `~/.truminds/sessions/<session_id>.json` (SDD-04 §6.14), or by walking up
from the hook's `cwd` to the companion repo root (the folder with `tsl.yaml`) and looking in `runs/active/`. Failures
the launcher handles are logged as one line in `~/.truminds/logs/hook.log`; `tsl` itself logs the normal path.
`TSL_HOOK_BUDGET_S` can only lower the deadline (used by the tests); nothing switches a check off.

`bin/tsl-hook` is POSIX sh (dash, bash, macOS sh, Git Bash) and shellcheck-clean. `bin/tsl-hook.cmd` is the cmd.exe
fallback with the same contract; its logic runs in Windows PowerShell because cmd.exe has no timeout or JSON parser.

## Tests

```bash
cd plugins/truminds/tests
uv run --python 3.12 pytest          # about 1 970 tests, about 25 s
uv run --python 3.12 ruff check .
```

| File | What it checks |
| --- | --- |
| `test_structure.py` | Every YAML, JSON and markdown front matter with a `schema:` key validates against `schemas/`; plugin and marketplace manifests; `hooks.json` = SDD-05 §5.2; reviewer and `review` skill; command skills from registry §3.2 have `disable-model-invocation: true` and their exact `tsl` preamble; SDLC SKILL.md template (SKL-V01, V04, V05, V07, V09, V11); catalogue = SDD-01 §12; eval cases, every referenced input file, JMESPath and regex in assertions; `requirement-review` EC-01..EC-10 and examples; `brownfield-change` = SDD-02 §4; workflow skill ranges, graph and input bindings (E-WFL-02..04); pods (POD-V01, V03..V05, V07..V12); plugin version = `tsl` version (skipped when `tsl` is absent) |
| `test_denylist.py` | No secrets, no fake key outside `evals/**`, no personal data, no networking-domain wording, and no client names (hashed n-grams against `TRUMINDS_DENYLIST_FILE`, a list kept outside the repo; skipped when not set) |
| `test_tsl_hook.py` | `bin/tsl-hook` under sh, dash and bash with a fake `tsl` on PATH: version mismatch, missing, crash and timeout, each in a run (deny `E-HOOK-01`) and out of a run (allow) for pre-tool and pre-mcp; post-write fail open; session warnings; stdin and stdout pass-through; session-index route; log line; no temp files left |

The `.cmd` launcher is not exercised in CI here (no Windows runner); TC-HK-007 covers it on Windows.

## Traceability

| Source | Implemented in |
| --- | --- |
| SDD-05 §3.1, §3.2, §3.3 | layout, `.claude-plugin/plugin.json`, `/.claude-plugin/marketplace.json` |
| SDD-05 §4.1, §4.2; SDD-02 §7 | `skills/run`, `skills/resume`, `skills/status`, `skills/eval`, `skills/improve` |
| SDD-06 §6.4 | `skills/context-draft` |
| SDD-05 §4.3, §4.4 | `agents/reviewer.md`, `skills/review` |
| SDD-05 §5.2, §5.4; SDD-04 §6.14 | `hooks/hooks.json`, `bin/tsl-hook`, `bin/tsl-hook.cmd`, `tests/test_tsl_hook.py` |
| SDD-05 §6.4 | `policy/policy.yaml` |
| SDD-01 §2–§10, §13 | `skills/requirement-review/**` |
| SDD-01 §12; SDD-03 §5.4 | `skills/<16 skills>/**` |
| SDD-01 §14.1 (subset), TST-01 §2.6 | `tests/test_structure.py` |
| SDD-02 §3, §4; Doc 3 §7.1 | `workflows/*.workflow.yaml` |
| SDD-10 §3, §4 | `/pods/<id>/` |
| C-09, T-01, SDD-01 §10.4, SDD-11 §7.3 | `tests/test_denylist.py` |
| SDD-05 §8.1 | `/spikes/` |

## Gaps and conflicts (flagged, not worked around)

- Resolved (registry §10 #44): `brownfield-change` now pins `requirement-review@^1.0` and binds `intent_baseline`,
  matching SDD-01 §13.1; SDD-02 §4 was updated to the same values.
- Status: SDD-01 §12 says every skill starts at `draft`; this build sets the Release-1 target status as instructed,
  which needs signed eval results and 10 cases (SDD-01 §7.1) that do not exist yet. No `*.eval-result.json` is
  committed; only `tsl eval run` on a seat can produce one.
- SDD-01 names the artifact file after the output (`intent.md`); SDD-02 and registry §8 name it after the step
  (`req.md`). `tsl next` decides the path; `skill.yaml` keeps SDD-01's `file`.
- To let the proposed Quality and Security workflows bind, `design`, `implement`, `test-plan` and `threat-model`
  declare some upstream artifacts as optional (`required: false`); SDD-10 O-03 must confirm.
- SDD-03 check kinds have no cross-file parameter; checks that need an input artifact use `$.inputs.<name>` and the
  secure-code-review scan lookup uses `{ticket}`/`{run_id}` placeholders. SDD-03 owners must confirm.
- `/truminds:run` cannot pass `--pod` (E-POD-01) because its preamble is fixed to `$0 $1` (SDD-05 §4.2).
- `/truminds:context-draft` calls `tsl context build --check --sections`, a flag SDD-04 §6.15 does not list.
- SDD-05 §5.4 says hook log lines go to `~/.truminds/hook.log`; SDD-04 §6.14 and registry §8 use `logs/`. The launcher
  uses `~/.truminds/logs/hook.log`. It cannot queue `hook.decision` events itself (the outbox needs `tsl`).
