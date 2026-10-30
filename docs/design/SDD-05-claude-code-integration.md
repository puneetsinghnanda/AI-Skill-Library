# SDD-05 · Claude Code Integration: Plugin, Commands, Hooks, Policy

Oct 12, 2026 · @Puneet Singh Nanda

## 1. Document control and scope

| Field | Value |
| --- | --- |
| ID | SDD-05 |
| Status | Draft for validation |
| Owner | Shubham Bansal |
| Approver | Puneet Singh Nanda |
| Author | Claude (for Puneet Singh Nanda) |
| Validator | Shubham Bansal (skill execution, hook execution) |
| Also reviewed by | Japman Singh, Yash Khorwal (harness hooks); Abhishek Verma, Ekjot Singh (skill and command surface) |
| Parent documents | [Doc 3 Architecture](../architecture/03-architecture.md) §2.2, §8 · [Doc 5 API and Rules](../architecture/05-api-and-rules.md) §2, §4 · [Doc 6 Constraints](../product/06-constraints.md) |
| Tracker | [Readiness Tracker](../planning/readiness-tracker.md) Q7, Q12, Q37 |

### 1.1 What this document decides

How the Truminds AI Skill Library plugs into Claude Code on an engineer's laptop:

- how the plugin is packaged and distributed;
- how users start runs (commands);
- how the reviewer subagent is defined;
- which hooks fire, with what input and output;
- how company policy is enforced so engineers cannot switch it off;
- how `tsl` is installed and version-matched;
- how Claude Code telemetry is turned on.

### 1.2 What it does not decide

These are covered in other documents:

- what `tsl` does inside each command: SDD-04;
- the check logic: SDD-03;
- workflow ordering: SDD-02;
- the skill format: SDD-01;
- the events API: SDD-08.

### 1.3 Ground rules from the architecture

- Execution is local, in the Claude Code desktop app (Code tab) on company Claude seats. There is no Claude API (D-10, D-11).
- Code makes every pass/fail decision. The AI only proposes (Doc 3 §5).
- Policy must hold even if an engineer edits their own settings (C-03, C-08, R-14).

### 1.4 Method

Every platform behaviour this design relies on was checked on 12 Oct 2026 against the official Claude Code documentation at code.claude.com/docs. Anything the documentation does not state is marked **unverified** and has a spike test in §8 before code depends on it.

## 2. Verified platform facts

Checked against code.claude.com/docs on 12 Oct 2026. Where a fact changes an earlier assumption in Doc 3 or Doc 5, the last column says what changes.

| # | Fact | Source | Effect on our design |
| --- | --- | --- | --- |
| V-01 | A plugin is a folder with an optional `.claude-plugin/plugin.json` (only `name` required). Skills, agents, commands, hooks, MCP servers and a `bin/` folder all sit at the plugin root | [Plugin manifest](https://code.claude.com/docs/en/plugins/manifest-reference.md) | Confirms the plugin approach |
| V-02 | Plugin components are namespaced: skill `run` in plugin `truminds` runs as `/truminds:run`; agent `reviewer` becomes `truminds:reviewer` | Plugin manifest | Confirms our command names |
| V-03 | Custom slash commands are now skills. `commands/*.md` still works, but skills are preferred for new plugins | [Skills](https://code.claude.com/docs/en/skills.md) | **Change:** our `/truminds:*` commands are built as skills, not command files |
| V-04 | `bin/` inside a plugin is added to the Bash PATH while the plugin is enabled. `${CLAUDE_PLUGIN_ROOT}` and `${CLAUDE_PLUGIN_DATA}` resolve in hook commands and skill bodies, but not inside Bash-tool commands | Plugin manifest | Hooks call `tsl` by absolute plugin path; skills call `tsl` through PATH |
| V-05 | A marketplace is a git repo with `.claude-plugin/marketplace.json` (`name`, `owner`, `plugins[]`). Install with `claude plugin install <plugin>@<marketplace>` | [Create a marketplace](https://code.claude.com/docs/en/plugins/create-marketplace.md) | Confirms distribution from GitHub |
| V-06 | Admins can pre-register the marketplace and force-enable the plugin with managed settings `extraKnownMarketplaces` + `enabledPlugins`. Users cannot turn a force-enabled plugin off | [Plugins for organisations](https://code.claude.com/docs/en/plugins/org.md) | Enforcement mechanism for C-03 / A-02 |
| V-07 | `strictKnownMarketplaces` (allowlist), `blockedMarketplaces`, `disableSideloadFlags` and `strictPluginOnlyCustomization` are managed-only keys | Plugins for organisations | Blocks unapproved plugins, skills and hooks |
| V-08 | `allowManagedHooksOnly: true` blocks user, project and plugin hooks, **except hooks from plugins force-enabled in managed `enabledPlugins`** | [Managed settings](https://code.claude.com/docs/en/managed-settings.md) | Our hooks run under this policy only if the plugin is force-enabled. Both must be set together |
| V-09 | Managed settings files: macOS `/Library/Application Support/ClaudeCode/managed-settings.json`, Linux `/etc/claude-code/managed-settings.json`, Windows `C:\Program Files\ClaudeCode\managed-settings.json`. Also delivered by MDM or from the claude.ai admin console. Managed settings override user and project settings | Managed settings | IT delivery options in §6 |
| V-10 | Permission rules are evaluated deny, then ask, then allow; an allow cannot override a deny. `allowManagedPermissionRulesOnly` makes managed rules the only source | [Permissions](https://code.claude.com/docs/en/permissions.md) | **Change:** fixed file and command blocks move from our hook into managed deny rules (native, cannot be bypassed) |
| V-11 | Hook events include PreToolUse, PostToolUse, SessionStart, SessionEnd, Stop, SubagentStart, SubagentStop and others. Input arrives as JSON on stdin with `session_id`, `cwd`, `hook_event_name`, `tool_name`, `tool_input`, `tool_use_id` | [Hooks](https://code.claude.com/docs/en/hooks.md) | Confirms our hook contract |
| V-12 | Exit 0 = success; exit 2 = block, with stderr fed back to Claude; other codes = non-blocking error. PreToolUse JSON output: `hookSpecificOutput.permissionDecision` = allow, deny, ask or defer, plus a reason. PostToolUse: `decision: "block"` + `reason` | Hooks | Confirms Doc 5 §4.2 |
| V-13 | Default hook timeout is 600 s; set per hook with `timeout`. All matching hooks run in parallel | Hooks | We set short explicit timeouts (§5) |
| V-14 | Subagents invoke through the tool named `Agent` (renamed from `Task`). Plugin agents ignore their own `hooks`, `mcpServers` and `permissionMode` frontmatter | [Subagents](https://code.claude.com/docs/en/sub-agents.md) | Reviewer restrictions come from its `tools` list plus managed rules |
| V-15 | A skill can run inside a chosen subagent with frontmatter `context: fork` + `agent: <name>`. Each subagent has its own context window, and only its final result returns | Skills, Subagents | Reviewer is called through a `review` skill with `context: fork` |
| V-16 | Skills can run shell commands before Claude sees the skill text using the `` !`command` `` syntax | Skills | Input checks run as code before the AI starts a step |
| V-17 | Telemetry: `CLAUDE_CODE_ENABLE_TELEMETRY=1` plus OTLP exporter variables, settable in the managed `env` block. Prompt text is excluded by default. `session.id` is on every metric and event | [Monitoring](https://code.claude.com/docs/en/monitoring-usage.md) | Confirms Doc 5 §5.4; join key is `session.id` |
| V-18 | The desktop app's Code tab supports plugins in **local** sessions. Plugins are **not** available in cloud sessions or WSL sessions | [Desktop](https://code.claude.com/docs/en/desktop.md) | **New constraint:** engineers must use local sessions; Windows engineers use native Windows, not WSL |
| V-19 | Node packages in a plugin are auto-installed; Python packages are not | Plugin loading | `tsl` needs its own install step (§7) |

### 2.1 Not yet verified — must pass a spike before code depends on it

| # | Assumption | Why it matters | Spike |
| --- | --- | --- | --- |
| U-01 | A PreToolUse matcher `Skill` fires when a skill is invoked, and its `tool_input` contains the skill name | Planned input-check hook | S-03. Fallback: input check via `!`tsl verify --inputs\`\` inside each skill (V-16), which is verified |
| U-02 | The PostToolUse input field name for the tool result (`tool_response`) | Post-write hook reads `tool_input.file_path` only, so low impact | S-04 |
| U-03 | `allowManagedHooksOnly` and force-enabled plugin hooks behave the same in the desktop app as in the CLI | Enforcement | S-06 |
| U-04 | The exact `tool_input` shape for the `Agent` tool | Policy on which subagents may run | S-05 |
| U-05 | Managed settings can pin a marketplace to a git tag or branch | Engineers get only reviewed releases | S-07. Fallback: only tagged, CI-passed merges reach main |
| U-06 | Variables a SessionStart hook writes to CLAUDE\_ENV\_FILE are visible to skill !\`...\` commands and Bash-tool commands | Tying a run to its session id and telemetry | S-08. Fallback: pre-tool hook binds the lock on the first tool call |

## 3. Plugin package design

### 3.1 Repository and plugin layout

The skill-library repo (`puneetsinghnanda/AI-Skill-Library` for now; the final GitHub org is OQ-10) is both the **marketplace** and the home of the **`truminds` plugin**.

```text
AI-Skill-Library/
├─ .claude-plugin/
│  └─ marketplace.json            # marketplace "truminds-skill-library"
├─ plugins/
│  └─ truminds/                    # the plugin (name: truminds)
│     ├─ .claude-plugin/plugin.json
│     ├─ skills/                   # user commands + SDLC skills (SDD-01)
│     │  ├─ run/SKILL.md           # /truminds:run
│     │  ├─ resume/SKILL.md        # /truminds:resume
│     │  ├─ status/SKILL.md        # /truminds:status
│     │  ├─ eval/SKILL.md          # /truminds:eval
│     │  ├─ improve/SKILL.md       # /truminds:improve
│     │  ├─ review/SKILL.md        # harness reviewer step (context: fork)
│     │  ├─ requirement-review/    # SDLC skill, one folder each
│     │  └─ ...
│     ├─ agents/
│     │  └─ reviewer.md            # truminds:reviewer subagent
│     ├─ hooks/
│     │  └─ hooks.json
│     ├─ bin/
│     │  └─ tsl-hook               # thin launcher: checks tsl version, runs `tsl hook <event>`
│     ├─ workflows/                # workflow.v1 files (SDD-02)
│     ├─ policy/
│     │  └─ policy.yaml            # org-level dynamic policy (§6.3)
│     └─ README.md
├─ tsl/                            # Python package source (SDD-04)
├─ schemas/                        # JSON Schemas (Doc 5 §3)
├─ managed-settings/               # templates for IT (§6)
├─ docs/adr/                       # decision records
└─ README.md
```

The repository also needs a `.mcp.json` once Jira, Confluence and GitHub MCP servers are wired in. That is out of scope for this document; the MCP write rules are in §6.

### 3.2 Plugin manifest (`plugins/truminds/.claude-plugin/plugin.json`)

```json
{
  "name": "truminds",
  "version": "0.1.0",
  "description": "Truminds AI Skill Library: SDLC skills, workflows and quality harness",
  "author": { "name": "Truminds" },
  "repository": "https://github.com/puneetsinghnanda/AI-Skill-Library",
  "license": "UNLICENSED",
  "keywords": ["sdlc", "harness", "truminds"]
}
```

Components use the default folders, so no component paths are needed in the manifest. The version follows SemVer and must equal the `tsl` version it requires (§7.1).

### 3.3 Marketplace file (`.claude-plugin/marketplace.json`)

```json
{
  "name": "truminds-skill-library",
  "owner": { "name": "Truminds AI Practice" },
  "plugins": [
    {
      "name": "truminds",
      "source": "./plugins/truminds",
      "description": "SDLC skills, workflows and quality harness"
    }
  ]
}
```

Engineers never install by hand in production; IT force-enables the plugin (§6). For development only:

```text
claude plugin marketplace add puneetsinghnanda/AI-Skill-Library
claude plugin install truminds@truminds-skill-library
```

### 3.4 Release rule

A plugin release is a git tag `vX.Y.Z` on `main`, after CI passes `tsl validate` on every skill and workflow. Engineers should only get reviewed releases. Whether managed settings can pin a marketplace to a tag or branch is not yet verified (U-05, spike S-07). Until it is, \`main\` only ever receives tagged, CI-passed merges.

**Release channels:** engineers install from the `channel/pilot` and `channel/stable` branches defined in [OPS-03 §4.2](../operations/OPS-03-release-rollout-support.md), never from `main`. That mechanism depends on S-07; if S-07 fails, OPS-03 §4.2 falls back to one distribution repo per channel.

## 4. User commands and the reviewer subagent

### 4.1 Commands are skills

The docs now merge slash commands into skills (V-03), so each `/truminds:*` command is a skill folder.

All command skills set `disable-model-invocation: true`, so Claude never starts a run on its own; only a person typing the command does.

| Command | Skill folder | Arguments | First thing it does (runs as code, before the AI reads the skill) |
| --- | --- | --- | --- |
| `/truminds:run` | `skills/run` | `<workflow> <ticket>` | `` !`tsl state start $0 $1 --json` ``, which takes the lock and returns `run_id` and the first step |
| `/truminds:resume` | `skills/resume` | `<run_id>` | `` !`tsl state resume $0 --json` ``, which refuses if blocking questions are unanswered |
| `/truminds:status` | `skills/status` | `[run_id]` | `` !`tsl state show $0 --json` `` |
| `/truminds:eval` | `skills/eval` | `<skill> [version]` | `` !`tsl eval plan $0 --json` `` |
| `/truminds:improve` | `skills/improve` | `<skill>` | `` !`tsl improve plan $0 --json` `` |

If the injected `tsl` call fails, its JSON error (with `code`, `exit` and `next`; Doc 5 §2.3) is what Claude sees, and the skill tells Claude to show the `next` action and stop.

### 4.2 Example: `skills/run/SKILL.md` (frontmatter and the start of the body)

```markdown
---
name: run
description: Start a Truminds workflow on a ticket. Only when the user types /truminds:run.
argument-hint: <workflow> <ticket>
disable-model-invocation: true
allowed-tools: Bash(tsl *), Read, Grep, Glob, Write, Edit
---

Run state from tsl (do not edit):
!`tsl state start $0 $1 --json`

If the JSON above has "ok": false, show its "message" and "next" to the user and stop.

Otherwise loop until tsl says the run is finished:
1. Run `tsl next <run_id> --json`. It names the next skill and its input files.
2. Use that skill to produce the artifact at the path tsl gives.
3. Run the `review` skill on the artifact.
4. Run `tsl decide <artifact> --json` and do exactly what its "next" field says
   (continue, retry with the findings, pause for input, pause for approval, stop).
Never decide pass or fail yourself.
```

The exact orchestration loop (`tsl next`, retries, gates) belongs to SDD-02. `tsl next` is a new command, added to SDD-04.

### 4.3 Reviewer subagent (`agents/reviewer.md`)

```markdown
---
name: reviewer
description: Truminds harness reviewer. Checks one artifact against the context pack and rubric and returns findings as JSON with citations. Use only through the truminds review skill.
tools: Read, Grep, Glob
model: inherit
---
You review one artifact. You did not write it.
For every finding give severity (blocker, major, minor), a one-line statement,
and at least one citation path#anchor that proves it.
If you cannot cite it, do not report it.
Return only JSON matching review.v1. Never edit files.
```

**Why read-only:** the reviewer gets only Read, Grep and Glob, so it cannot change the artifact or the evidence it judges. Plugin agents ignore their own hooks and permission settings (V-14), so the read-only limit comes from this `tools` list plus the managed deny rules in §6.

### 4.4 How the reviewer is called (`skills/review/SKILL.md`)

```markdown
---
name: review
description: Harness review step for one artifact. Used by truminds workflows only.
context: fork
agent: truminds:reviewer
user-invocable: false
---
Review package from tsl (artifact, rubric, cited context sections):
!`tsl review prepare $ARGUMENTS --json`
```

**Flow:**

1. The main session runs the `review` skill.
2. Claude Code starts the `truminds:reviewer` subagent with a fresh context window (V-15). That window holds only the review package, not the conversation that produced the artifact.
3. The subagent returns its JSON.
4. The main session runs `tsl review record <artifact>` with that JSON on standard input. `tsl` validates it against `review.v1` and writes `<artifact>.review.json`.
5. `tsl decide` then verifies every citation itself; any finding it cannot verify is dropped (Doc 3 §5).

**Accepted limit:** the main session handles the reviewer's JSON on its way to `tsl`, so in theory it could alter it. This is covered by L-06: citations are re-checked by code, and the human PR review stays as the final check.

## 5. Hooks

### 5.1 Changes from Doc 5 §4

| Doc 5 said | Now | Why |
| --- | --- | --- |
| PreToolUse hook on the `Skill` tool checks inputs | **Dropped.** Each skill checks its inputs with `` !`tsl verify --inputs` `` before Claude starts (V-16) | Matching on `Skill` is undocumented (U-01). The skill-level check is documented and runs as code |
| PreToolUse hook blocks `.env`, keys, `curl` and similar | **Moved** to managed permission deny rules (§6.2) | Native, faster, cannot be bypassed, and needs no Python (V-10) |
| — | **New:** SessionStart hook | Checks the `tsl` version and login, flushes queued events, and passes the session id to `tsl` |

### 5.2 `plugins/truminds/hooks/hooks.json`

```json
{
  "hooks": {
    "SessionStart": [
      { "hooks": [ { "type": "command", "command": "\"${CLAUDE_PLUGIN_ROOT}/bin/tsl-hook\" session-start", "timeout": 15 } ] }
    ],
    "PreToolUse": [
      { "matcher": ".*",
        "hooks": [ { "type": "command", "command": "\"${CLAUDE_PLUGIN_ROOT}/bin/tsl-hook\" pre-tool", "timeout": 10 } ] },
      { "matcher": "mcp__.*",
        "hooks": [ { "type": "command", "command": "\"${CLAUDE_PLUGIN_ROOT}/bin/tsl-hook\" pre-mcp", "timeout": 10 } ] }
    ],
    "PostToolUse": [
      { "matcher": "Write|Edit|NotebookEdit",
        "hooks": [ { "type": "command", "command": "\"${CLAUDE_PLUGIN_ROOT}/bin/tsl-hook\" post-write", "timeout": 90 } ] }
    ],
    "SessionEnd": [
      { "hooks": [ { "type": "command", "command": "\"${CLAUDE_PLUGIN_ROOT}/bin/tsl-hook\" session-end", "timeout": 15 } ] }
    ]
  }
}
```

`bin/tsl-hook` is a small launcher, the same on every OS (a shell script, plus a `.cmd` on Windows). It:

- finds `tsl` on the machine;
- checks that its version equals the plugin version;
- passes stdin to `tsl hook <event>`;
- applies the failure rules in §5.4 when `tsl` is missing or crashes.

### 5.3 Hook specifications

| Hook | Fires on | Reads from stdin | Does | Output | Time budget |
| --- | --- | --- | --- | --- | --- |
| **session-start** | Every session start | `session_id`, `cwd` | (1) Checks `tsl` is installed and the version matches. (2) Checks the `tsl login` token is valid. (3) Flushes the offline outbox. (4) Writes `export TSL_SESSION_ID=<session_id>` to `$CLAUDE_ENV_FILE`, so later `tsl` calls can tie a run to this session and to Claude Code telemetry (`session.id`). (5) If an unfinished run of this user exists in this companion repo, adds a one-line reminder | `additionalContext` with the reminder; `systemMessage` with a fix-it instruction when `tsl` is missing, outdated or logged out | ≤ 2 s typical |
| **pre-tool** | Every tool except MCP tools (matcher `.*`; MCP tools return at once and go to pre-mcp) | `tool_name`, `tool_input` (`file_path` or `command`), `cwd`, `session_id` | **Only while this session holds an active run lock.** While the cursor step's skill is open (`tsl verify --inputs` set `skill_started_at`; `tsl decide` has not set `decided_at`), a tool outside that skill's `allowed_tools` is refused before it runs (E-POL-06) and is not written to the tool log, so H7 has nothing to fail. Bash is compared after leading `cd <dir> &&` / `cd <dir>;` and safe env prefixes are removed; `tsl` commands and the run loop's own tools (Skill, Agent, Task, ToolSearch, AskUserQuestion, TodoWrite) stay allowed. Write and Edit targets must be inside the companion repo's `artifacts/`, `runs/` or a `product_repos` path from `tsl.yaml`. Bash commands are checked against `policy.yaml` patterns that depend on run context. Only Write, Edit, NotebookEdit and Bash are written to the tool log. Outside a run it allows everything; static rules still apply via managed settings | `permissionDecision: deny` + reason with error code (E-POL-01, E-POL-02, E-POL-06); otherwise exit 0 with no output | ≤ 500 ms p95 (NFR-02) |
| **pre-mcp** | Any MCP tool | `tool_name`, `tool_input` | Classifies the tool as read or write using `policy.yaml` (§6.3). Writes, such as creating a Jira issue or editing a Confluence page, are denied unless `approvals.md` of the active run has a signed approval for that action | `deny` + E-POL-03, or allow | ≤ 500 ms |
| **post-write** | Write, Edit, NotebookEdit | `tool_input.file_path` | If the path is an artifact (`artifacts/**/<name>.md`), runs `tsl verify <path>`. Any other file exits 0 at once | On check failure: `decision: "block"` + `reason` (E-CHK-01 with the failed gate), so Claude fixes and rewrites. On pass: exit 0 | ≤ 5 s p95 excluding verifier containers (NFR-01); hard timeout 90 s |
| **session-end** | Session close | `session_id` | Writes a heartbeat to `state.json` of an active run, sends `session.ended`, flushes the outbox | None, never blocks | ≤ 2 s |

### 5.4 Failure rules

| Situation | pre-tool / pre-mcp | post-write | session-start / end |
| --- | --- | --- | --- |
| `tsl` not installed or wrong version | Inside a run: deny (E-HOOK-01, "install tsl X.Y.Z"). Outside a run: allow | Allow, warn with `systemMessage` | Warn with `systemMessage` |
| `tsl` crashes or times out | Inside a run: deny (fail closed) | Allow, warn (fail open; never lose the engineer's work) | Ignore, log locally |
| Telemetry service unreachable | Not affected | Not affected | Events stay in the outbox (Doc 5 R-04) |

Every hook appends one line to `~/.truminds/hook.log` and one `hook.decision` event to the outbox (metadata only).

### 5.5 Why the session id goes through `CLAUDE_ENV_FILE`

Commands run through the Bash tool, or through the `` !`...` `` syntax in skills, do not receive the session id. The SessionStart hook is the only place that sees it and can export variables for later commands. Whether `` !`...` `` injection also sees exported variables is unverified (U-06, spike S-08). The fallback: the pre-tool hook binds the lock to the session on the first tool call after `tsl state start`.

## 6. Enforcement model

### 6.1 Three layers

| Layer | What it enforces | Can an engineer switch it off? |
| --- | --- | --- |
| **Managed settings** (from IT) | Plugin is installed and on; only the Truminds marketplace is allowed; only managed and Truminds hooks run; fixed deny rules; telemetry on | No (V-06, V-08, V-09) |
| **Plugin hooks + `policy.yaml`** | Rules that depend on the active run: allowed write paths, MCP write approvals | No, while the plugin is force-enabled and `allowManagedHooksOnly` is on |
| **CI (`tsl ci-verify`)** | Catches anything done outside the plugin: a PR with code but no records fails (E-CI-01) | No, if the repo requires the check |

### 6.2 Managed settings template (`managed-settings/managed-settings.json` in the repo)

```json
{
  "extraKnownMarketplaces": {
    "truminds-skill-library": {
      "source": { "source": "github", "repo": "puneetsinghnanda/AI-Skill-Library" }
    }
  },
  "enabledPlugins": { "truminds@truminds-skill-library": true },
  "strictKnownMarketplaces": [
    { "source": "github", "repo": "puneetsinghnanda/AI-Skill-Library" }
  ],
  "disableSideloadFlags": true,
  "allowManagedHooksOnly": true,
  "permissions": {
    "disableBypassPermissionsMode": "disable",
    "deny": [
      "Read(**/.env)", "Read(**/.env.*)", "Read(**/*.pem)", "Read(**/*.key)",
      "Read(**/id_rsa*)", "Read(**/secrets/**)",
      "Edit(**/.env)", "Edit(**/*.pem)", "Edit(**/*.key)",
      "Bash(curl *)", "Bash(wget *)", "Bash(ssh *)", "Bash(scp *)",
      "Bash(git push --force*)", "Bash(gh pr merge*)"
    ]
  },
  "env": {
    "CLAUDE_CODE_ENABLE_TELEMETRY": "1",
    "OTEL_METRICS_EXPORTER": "otlp",
    "OTEL_LOGS_EXPORTER": "otlp",
    "OTEL_EXPORTER_OTLP_PROTOCOL": "http/protobuf",
    "OTEL_EXPORTER_OTLP_ENDPOINT": "https://<insights-host>/otel",
    "OTEL_EXPORTER_OTLP_HEADERS": "Authorization=Bearer <collector-token>"
  }
}
```

**Notes on the template:**

- **Key names** are verified (V-06 to V-10, V-17).
- **Exact value shapes are not yet confirmed:** the `source` objects, the glob syntax inside `Read(...)` and `Edit(...)`, and the `strictKnownMarketplaces` entry. Spike S-01 and S-02 confirm them before IT rolls this out.
- **`allowManagedPermissionRulesOnly` is not set**, so engineers keep their own allow rules for convenience. Managed deny rules still win, because a deny is evaluated first and an allow cannot override it (V-10).
- **`<collector-token>`** is a shared, low-privilege ingest token for the telemetry collector (Doc 5 §5.4). It is not a secret that grants access to data, but it is still delivered only through managed settings, never committed (org rule: no secrets in git).
- **Placeholders:** the host, the repo name (OQ-10) and the protocol are filled in when hosting is decided (OQ-02).

### 6.3 Who delivers managed settings

| Option | How | Notes |
| --- | --- | --- |
| **Claude admin console (recommended)** | claude.ai › Organization settings › Claude Code › Managed settings | One place for every seat. Reaches local desktop sessions on eligible logins (V-09) |
| MDM | macOS profile domain `com.anthropic.claudecode`; Windows `HKLM\SOFTWARE\Policies\ClaudeCode` | Use if IT already manages laptops this way |
| File on disk | Paths in V-09 | Fallback, for testing only |

Only one managed source applies unless IT sets `managedSourcesBehavior: "merge"`, so pick one. **Owner: Claude organisation admin (TBD by Puneet).**

### 6.4 `policy.yaml` (run-dependent rules, read by the hooks)

This replaces Doc 5 §4.3. Static file and command blocks moved to §6.2.

```yaml
schema: policy.v2
write_scope:                     # applies only while this session holds a run lock
  allow:
    - "<companion>/artifacts/**"
    - "<companion>/runs/<run_id>/**"
    - "<product_repos>/**"       # expanded from tsl.yaml of the system
  deny:
    - "<companion>/context/pack.signature.json"
    - "**/.github/workflows/**"
bash_in_run:
  deny_patterns: ["git push", "git commit --amend", "rm -rf"]   # tsl pr does pushes, not Claude
mcp:
  read_tools: ["*__get*", "*__search*", "*__list*", "*__fetch*"]
  write_tools_need_approval: ["*__create*", "*__update*", "*__edit*", "*__add*", "*__transition*", "*__delete*"]
  unknown_tools: deny            # anything not classified is treated as a write
merge_and_deploy: never
```

A system's own `policy.yaml` may only **add** denies, never remove them. `tsl validate` checks this.

## 7. `tsl` installation, telemetry, desktop constraints

### 7.1 How `tsl` gets onto the laptop

Plugins install Node packages automatically but not Python packages (V-19), so `tsl` has its own install step during onboarding.

| Item | Decision |
| --- | --- |
| Package | `truminds-tsl`, a pure-Python wheel (Python 3.12). Its only native dependency, `cryptography`, ships prebuilt wheels for macOS, Windows and Linux |
| Where it comes from | A wheel attached to the same GitHub release tag as the plugin (`vX.Y.Z`) |
| Install command | `uv tool install "truminds-tsl @ <release-wheel-URL>"`, which gives an isolated environment and a `tsl` on PATH. `pipx install` works the same way |
| Version rule | `tsl --version` must equal the plugin version. `bin/tsl-hook` and the SessionStart hook check it and print the exact install command when they differ |
| Upgrades | IT bumps the plugin; at the next session start each engineer is told to run the install command for the new version. A run already in progress keeps working, because `tsl` reads schema versions N and N-1 (R-09) |
| Prerequisites | Python 3.12, `uv` (or pipx), git, Docker. Checked by `tsl doctor` |

### 7.2 Claude Code telemetry

- **Turned on by** the managed `env` block (§6.2). Engineers cannot redirect or disable it, and repo settings cannot change it (V-17).
- **Never turned on:** `OTEL_LOG_USER_PROMPTS`, `OTEL_LOG_ASSISTANT_RESPONSES`, `OTEL_LOG_RAW_API_BODIES` and `OTEL_LOG_TOOL_DETAILS`. Prompt and response text therefore never leave the laptop (NFR-10).
- **Joining telemetry to runs:** every Claude Code metric and event carries `session.id`. `tsl` records the same id in `run.started` (from `TSL_SESSION_ID`, §5.5), so the insights service can attach token use and cost to a run (SDD-08).
- **Metrics we keep:** session count, token usage, cost usage, active time, tool decisions, and the skill-activated and plugin-loaded events. Everything else is dropped at the collector.

### 7.3 Where runs can happen

These come from V-18 and become new constraints in Doc 6:

| ID | Constraint | Reason |
| --- | --- | --- |
| C-16 | Runs happen only in **local** sessions of the Claude Code desktop app (Code tab, "Local") or the Claude Code CLI. Not in cloud sessions, and not in the Cowork tab | Plugins are not loaded in cloud sessions; Cowork takes its plugins from claude.ai, not the managed marketplace |
| C-17 | On Windows, engineers run Claude Code natively, not inside WSL | Plugins are not available in WSL sessions |
| C-18 | The laptop needs Python 3.12, uv or pipx, git and Docker | `tsl`, hooks and verifier containers run locally |

## 8. Spikes, done criteria, changes to other documents

### 8.1 Spike plan

**Run by:** Shubham Bansal, on a company seat, in a local desktop session, using a throwaway test plugin and a stub `tsl` that only logs its stdin. Record each result in the "Result" column. A failed spike switches that item to its fallback.

| Spike | Proves | How | Pass condition | Result |
| --- | --- | --- | --- | --- |
| S-01 | Managed settings shapes (§6.2) | Apply the template to one test seat via the admin console | Plugin installs at next session start; a second marketplace is refused; `--plugin-dir` is refused |  |
| S-02 | Deny-rule globs | Try to read `a/b/.env`, `x.pem`; run `curl` | All three blocked, with no prompt |  |
| S-03 | U-01: PreToolUse on `Skill` | Hook with matcher `Skill` logs stdin | Fires, and the skill name is in `tool_input` (nice-to-have; not on the critical path) |  |
| S-04 | U-02: PostToolUse input | Log stdin after a Write | `tool_input.file_path` present; record the result field name |  |
| S-05 | U-04: `Agent` tool input | PreToolUse matcher `Agent` logs stdin | Subagent type visible |  |
| S-06 | U-03: hook enforcement in desktop | `allowManagedHooksOnly` + force-enabled plugin; add a user hook | Plugin hook fires; the user hook does not |  |
| S-07 | U-05: marketplace pinning | Try a `ref` or tag in the managed source | Only the tagged version installs |  |
| S-08 | U-06: env passing | SessionStart writes `TSL_SESSION_ID`; read it from `` !`env` `` in a skill and from a Bash call | Visible in both |  |
| S-09 | End to end | `/truminds:run demo T-1` with stub `tsl`: skill writes an artifact; post-write hook runs; `review` forks `truminds:reviewer`; returns JSON | Whole loop works; pre-tool ≤ 500 ms; post-write overhead ≤ 1 s with the stub |  |

Spikes raised by other documents. Ids come from the [registry](../architecture/registry.md) §9; never reuse one.

| Spike | Proves | Raised by | Run by | Result |
| --- | --- | --- | --- | --- |
| S-10 | OTel metric and event names and attribute keys for the SDD-08 allowlist | SDD-08 §5.3 | Shubham Bansal |  |
| S-11 | Seat usage (tokens) of one full workflow run | SDD-13 §8.3 | Claude org admin (TBD by Puneet) with Shubham Bansal |  |
| S-12 | Whether the admin console can apply managed settings to a subset or group of users | SDD-13 §6.2, OPS-03 §4.3 | Shubham Bansal with the Claude admin |  |
| S-13 | Managed deny-rule syntax for `WebFetch` and `WebSearch` | SEC-01 §6.3 | Shubham Bansal |  |
| S-14 | When Claude Code updates a force-enabled plugin after its marketplace changes | OPS-03 §4.1 | Shubham Bansal |  |
| S-15 | What Claude Code does when a hook's own `timeout` fires | OPS-04 §4.5 | Shubham Bansal |  |

### 8.2 Done criteria for the SDD-05 build

- Plugin and marketplace install from the repo on clean macOS and Windows (native) machines.
- All spikes recorded; every failed one has its fallback implemented.
- Managed settings template validated on a test seat and handed to the Claude admin.
- `hooks.json` contract tests: each hook has fixtures for allow, deny, fail-closed and fail-open, plus the 500 ms budget test.
- `bin/tsl-hook` works on macOS, Linux and Windows.
- Install guide for `tsl` written (feeds SDD-13).

### 8.3 Changes this document makes to other documents

| Document | Change |
| --- | --- |
| Doc 3 §2.2 | Commands are skills; reviewer called through the `review` skill (`context: fork`); input check is inside skills |
| Doc 5 §2.1 | Command table: each command is a skill with `disable-model-invocation` |
| Doc 5 §4 | Hooks replaced by §5 here; `policy.v1` replaced by `policy.v2` plus managed deny rules |
| Doc 6 | Add C-16 (local sessions only), C-17 (no WSL), C-18 (laptop prerequisites) |
| SDD-04 (`tsl`) | New commands: `tsl next`, `tsl review prepare`, `tsl review record`, `tsl hook <event>`, `tsl doctor`, `tsl eval plan`, `tsl improve plan` |
| SDD-02 | Owns the orchestration loop sketched in §4.2 |
| SDD-08 | Joins Claude Code telemetry to runs on `session.id` |

I will apply these once Shubham validates this document.

### 8.4 Open items

| Item | Owner |
| --- | --- |
| Who in the organisation applies managed settings (Claude admin) | TBD by Puneet |
| Final GitHub org and repo name for the marketplace (OQ-10) | TBD by Puneet |
| Telemetry collector host and ingest token (depends on hosting, OQ-02) | Gaurav Saini, after hosting choice |
| Docker Desktop licensing for Windows and macOS engineers | TBD by Puneet |
| Spike results S-01 to S-15 (S-11 and S-12 with the Claude admin) | Shubham Bansal |
