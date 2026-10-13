# spikes/ — Claude Code platform spikes S-01 to S-15

This folder holds a tiny, separate plugin (`tsl-spike`) and one runbook per spike in registry §9 (S-01 to S-15). Each
spike proves one Claude Code behaviour that the design relies on but the documentation does not state (SDD-05 §2.1,
§8.1). A failed spike switches its item to the fallback named in the runbook.

**Run by:** Shubham Bansal (S-11 and S-12 together with the Claude org admin, TBD by Puneet). **Where:** the Claude
desktop app, Code tab, **Local** session, on a company seat that is set aside for testing. Never on a production
seat and never on a client repository.

## What is here

```text
spikes/
├─ .claude-plugin/marketplace.json   marketplace "truminds-spikes" with one plugin
├─ tsl-spike/                        the spike plugin
│  ├─ .claude-plugin/plugin.json     name tsl-spike, version 0.0.1
│  ├─ hooks/hooks.json               logs stdin of every hook event; pre-tool/post-write call the stub tsl
│  ├─ bin/log-stdin (+ .cmd)         appends hook stdin to ~/.tsl-spike/log/hooks.jsonl, prints nothing
│  ├─ bin/tsl                        STUB tsl: canned answers for one demo run, logs every call
│  ├─ bin/slow-hook                  S-15 only: sleeps past its 3 s timeout while ~/.tsl-spike/S-15.on exists
│  ├─ skills/run                     /tsl-spike:run — the SDD-02 §7 loop against the stub (S-09)
│  ├─ skills/demo-step               an SDLC-style skill with the !`tsl verify $0 --inputs --json` preamble
│  ├─ skills/review, agents/reviewer the context: fork review path (S-09)
│  └─ skills/env-probe               /tsl-spike:env-probe — prints TSL_SESSION_ID two ways (S-08)
├─ settings/                         managed-settings and user-settings snippets per spike
├─ otel/                             local OTLP collector config and a name lister (S-10, S-11)
└─ sample-companion/                 empty invented companion repo to open in the Code tab
```

The stub `tsl` is **not** the real tool. It never touches git, the network or keys. The spike plugin must not be
enabled at the same time as the `truminds` plugin, because both put a `tsl` on the Bash PATH.

## Shared set-up (do once per test seat)

1. Make sure the seat has **no** production managed settings yet (S-01 and S-06 apply their own).
2. Clone this repository on the test laptop. Note the absolute path of `spikes/` (called `<spikes>` below).
3. Open the Claude desktop app, choose the **Code** tab, start a new session, pick **Local**, and select the folder
   `<spikes>/sample-companion`.
4. In the session, type `/plugin marketplace add <spikes>` and press Enter. Then type
   `/plugin install tsl-spike@truminds-spikes`. Accept the prompt.
5. Close the session and start a new Local session on `<spikes>/sample-companion` (plugins load at session start).
6. Type `/plugin` and check that `tsl-spike` shows as enabled. If `truminds` is also enabled, disable it for these spikes.
7. Logs appear under `~/.tsl-spike/log/` (Windows: `%USERPROFILE%\.tsl-spike\log\`). Delete that folder between
   spikes so each result starts clean.

Some managed-settings spikes need the spike marketplace in its own GitHub repository, because a marketplace is looked
up at the root of a repository (V-05). For those, copy the contents of `spikes/` to the root of a throwaway private
repository (`<test-org>/<spikes-repo>`) and use that name in the `settings/` files.

**Record results** in the table at the end of each runbook: who ran it, the OS and app version, what you saw, pass
or fail, and a link to the evidence (log file or screenshot in the team drive). Then copy the one-line result into
the "Result" column of SDD-05 §8.1 by pull request.

---

## S-01 · Managed settings shapes (SDD-05 §6.2)

**Proves:** the key names and value shapes of `managed-settings/managed-settings.template.json` are accepted: the
plugin installs from the allowed marketplace, a second marketplace is refused, and `--plugin-dir` is refused.

**Steps**

1. Ask the Claude org admin to apply `managed-settings/managed-settings.template.json` to the test seat through the
   admin console (claude.ai › Organization settings › Claude Code › Managed settings), with `<insights-host>` and
   `<collector-token>` replaced by test values. For a file-only test, place it at the V-09 path for the OS instead.
2. Quit the desktop app completely and start it again. Open the Code tab and start a Local session on any folder.
3. Type `/plugin`. Record whether `truminds@truminds-skill-library` is installed and enabled without any action.
4. Type `/plugin marketplace add <spikes>`. Record the message.
5. In a terminal on the same laptop, run `claude --plugin-dir <spikes>/tsl-spike`. Record the message.

**Expected observation:** step 3 shows the plugin installed and enabled; step 4 is refused (not on the allowlist);
step 5 is refused (`disableSideloadFlags`).

**Pass condition:** all three hold. **Fallback if it fails:** correct the template shapes with the app's error
messages and repeat; IT does not roll out until it passes.

| Run | Run by | OS / app version | Observation | Pass? | Evidence |
| --- | --- | --- | --- | --- | --- |
| 1 | | | | | |

## S-02 · Deny-rule globs (SDD-05 §6.2)

**Proves:** the managed deny rules block reads of nested `.env` and key files and the `curl` command, with no prompt.

**Steps**

1. Apply `spikes/settings/S-02-deny-rules.json` as managed settings on the test seat (admin console or V-09 file).
2. In `<spikes>/sample-companion` create the invented files `a/b/.env` (content `EXAMPLE=1`) and `x.pem`
   (content `not a key`).
3. Start a new Local session on `<spikes>/sample-companion`. Type: `Read the file a/b/.env and show it.`
4. Type: `Read x.pem.`
5. Type: `Run curl https://example.com`.

**Expected observation:** each request is denied by policy; no permission prompt appears; the file contents never
show in the session.

**Pass condition:** all three blocked with no prompt. **Fallback:** keep the rules and add the same patterns to the
pre-tool hook's in-run checks (E-POL-02), and report the gap to IT.

| Run | Run by | OS / app version | Observation | Pass? | Evidence |
| --- | --- | --- | --- | --- | --- |
| 1 | | | | | |

## S-03 · PreToolUse on the `Skill` tool (U-01)

**Proves:** whether a PreToolUse hook with matcher `Skill` fires when a skill runs, and whether `tool_input` carries
the skill name. Nice to have; the design does not depend on it (skills check inputs with their preamble).

**Steps**

1. Shared set-up done; delete `~/.tsl-spike/log/`.
2. In a Local session on `<spikes>/sample-companion`, type `/tsl-spike:run demo T-1` and let it finish.
3. Open `~/.tsl-spike/log/hooks.jsonl` and look for lines with `"label":"pre-skill"`.

**Expected observation:** at least one `pre-skill` line whose `stdin.tool_input` names `demo-step` (or
`tsl-spike:demo-step`).

**Pass condition:** the hook fires and the skill name is present. **Fallback:** none needed; the input check stays in
the skill preamble (SDD-05 §5.1).

| Run | Run by | OS / app version | Observation (paste the tool_input keys) | Pass? | Evidence |
| --- | --- | --- | --- | --- | --- |
| 1 | | | | | |

## S-04 · PostToolUse input fields (U-02)

**Proves:** a PostToolUse hook after `Write` receives `tool_input.file_path`, and records the name of the field that
holds the tool result.

**Steps**

1. Delete `~/.tsl-spike/log/`. Start a Local session on `<spikes>/sample-companion`.
2. Type: `Create the file notes/hello.md with the single line: hello`.
3. Open `~/.tsl-spike/log/hooks.jsonl` and find the `"label":"post-write"` line.

**Expected observation:** `stdin.tool_input.file_path` ends with `notes/hello.md`; another top-level key (expected
`tool_response`) holds the result.

**Pass condition:** `tool_input.file_path` present. Record the exact result field name in the table; the TST-01 §2.3
fixtures marked `unverified` are replaced with this shape.

| Run | Run by | OS / app version | Result field name | Pass? | Evidence |
| --- | --- | --- | --- | --- | --- |
| 1 | | | | | |

## S-05 · `Agent` tool input (U-04)

**Proves:** the `tool_input` shape of the `Agent` tool, so a later policy can tell which subagent type is started.

**Steps**

1. Delete `~/.tsl-spike/log/`. Start a Local session on `<spikes>/sample-companion`.
2. Type `/tsl-spike:run demo T-1`. The run loop calls the `review` skill, which forks `tsl-spike:reviewer`.
3. Also type: `Use a subagent to list the files in this folder.`
4. Open `~/.tsl-spike/log/hooks.jsonl` and find `"label":"pre-agent"` lines.

**Expected observation:** `pre-agent` lines whose `tool_input` contains a subagent type field (for example
`subagent_type`) with the agent name.

**Pass condition:** the subagent type is visible. **Fallback:** subagent policy stays with the reviewer's `tools`
list and the managed deny rules only (SDD-05 §4.3).

| Run | Run by | OS / app version | tool_input keys | Pass? | Evidence |
| --- | --- | --- | --- | --- | --- |
| 1 | | | | | |

## S-06 · Hook enforcement in the desktop app (U-03)

**Proves:** with `allowManagedHooksOnly: true` and the plugin force-enabled, the plugin's hooks fire in the desktop
app and a user hook does not.

**Steps**

1. Publish `spikes/` as `<test-org>/<spikes-repo>` (see shared set-up) and put that name into
   `spikes/settings/S-06-managed-hooks-only.json`. Apply it as managed settings on the test seat.
2. Merge `spikes/settings/S-06-user-hook.json` into the user settings file `~/.claude/settings.json`.
3. Quit and restart the desktop app. Delete `~/.tsl-spike/log/`.
4. Start a Local session on `<spikes>/sample-companion`. Type: `Create the file notes/s06.md with the line: s06`.
5. Check `~/.tsl-spike/log/hooks.jsonl` (plugin hooks) and `~/.tsl-spike/log/user-hook.log` (user hook).
6. Repeat steps 3 to 5 with the CLI (`claude` in a terminal in the same folder) and compare.

**Expected observation:** `hooks.jsonl` has `pre-tool` and `post-write` lines; `user-hook.log` does not exist.
Desktop and CLI behave the same.

**Pass condition:** plugin hook fires, user hook does not, in the desktop app. **Fallback:** if the desktop app runs
user hooks, ask IT for MDM delivery and raise it with Anthropic support; CI (`tsl ci-verify`) remains the backstop.

| Run | Run by | OS / app version | Desktop result | CLI result | Pass? | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | | | | | | |

## S-07 · Marketplace pinned to a tag or branch (U-05)

**Proves:** whether managed settings can pin a marketplace source to a git tag or branch, so engineers receive only
reviewed releases.

**Steps**

1. In `<test-org>/<spikes-repo>`, tag the current commit `v0.0.1`. Then change `tsl-spike/.claude-plugin/plugin.json`
   to version `0.0.2`, commit and push to the default branch without a tag.
2. Put the repo name into `spikes/settings/S-07-pinned-source.json` and apply it as managed settings.
3. Quit and restart the app; start a Local session; type `/plugin` and record the installed `tsl-spike` version.
4. If the `ref` key is rejected or ignored, try the other shapes listed in the file (one at a time) and record each.

**Expected observation:** version `0.0.1` (the tag) is installed, not `0.0.2`.

**Pass condition:** only the tagged version installs. **Fallback:** the release channels of OPS-03 §4.2 use one
distribution repository per channel; `main` only receives tagged, CI-passed merges (SDD-05 §3.4).

| Run | Run by | OS / app version | Source shape tried | Installed version | Pass? | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | | | | | | |

## S-08 · `CLAUDE_ENV_FILE` reaches skills and Bash (U-06)

**Proves:** a variable that the SessionStart hook writes to `$CLAUDE_ENV_FILE` is visible both inside a skill's
`` !`...` `` injection and inside Bash tool commands.

**Steps**

1. Delete `~/.tsl-spike/log/`. Start a new Local session on `<spikes>/sample-companion`.
2. Check `~/.tsl-spike/log/hooks.jsonl`: the `session-start` line must show `"env_file_set":true`.
3. Type `/tsl-spike:env-probe`.
4. Read the two values the skill prints: "injection" and "bash".

**Expected observation:** both show the session id (the same value as `stdin.session_id` in the `session-start`
log line).

**Pass condition:** visible in both. **Fallback:** the pre-tool hook binds the run lock to the session on the first
tool call after `tsl state start` (SDD-04 §6.14, SDD-05 §5.5).

| Run | Run by | OS / app version | injection | bash | Pass? | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | | | | | | |

## S-09 · End-to-end loop with the stub `tsl` (SDD-05 §8.1, SDD-02 §7)

**Proves:** the whole run loop works in the desktop app: the command skill's `` !`tsl state start` `` injection,
`tsl next`, invoking the named SDLC skill with its preamble, the post-write hook, the `review` skill forking
`tsl-spike:reviewer`, the reviewer returning JSON, and `tsl decide`. It also measures hook latency. It also confirms
whether a `` !`...` `` preamble needs a matching `allowed-tools` entry (SDD-01 §3.1) and whether the local-path
marketplace form works (DEV-01 §5).

**Steps**

1. Delete `~/.tsl-spike/log/` and `~/.tsl-spike/state`. Start a Local session on `<spikes>/sample-companion`.
2. Type `/tsl-spike:run demo T-1`. Do not help the model; only approve permission prompts.
3. When it stops, check the folder `artifacts/T-1/run_01J0SP1KE0000000000000000S/` for `demo.md`.
4. Open `~/.tsl-spike/log/tsl-calls.jsonl`. Ignoring the extra `hook pre-tool` lines (that hook also fires for every
   Bash call), the calls must appear in this order: `state start`, `next`, `verify ... --inputs`, `hook pre-tool`
   (the Write), `hook post-write`, `review prepare`, `review record`, `decide`, `next`.
5. For latency, read `took_ms` of the `hook pre-tool` and `hook post-write` lines, and compare the `ts_ms` of the
   `pre-tool` hook call with the time the Write appeared.
6. Repeat once with the line `Bash(tsl verify *)` removed from `skills/demo-step/SKILL.md` `allowed-tools`, and
   record whether the preamble still runs.

**Expected observation:** the loop finishes with the stub's "run finished" message; `demo.md` exists; all calls are
in order; the reviewer ran in a fork (its answer appears as one tool result, not in the main conversation).

**Pass condition:** whole loop works; pre-tool ≤ 500 ms; post-write overhead ≤ 1 s with the stub. **Fallback:** if
the model does not keep the loop going, `/truminds:resume` continues the run from `tsl next` (SDD-02 §7); runs stay
valid because every decision is in `tsl`.

| Run | Run by | OS / app version | Loop complete? | pre-tool ms | post-write ms | Preamble without allowed-tools? | Pass? | Evidence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | | | | | | | | |

## S-10 · OTel metric and event names and attributes (SDD-08 §5.3)

**Proves:** the exact OpenTelemetry metric names, event names and attribute keys Claude Code sends, so SDD-08's
`allowlist.yaml` can be filled. Only names and keys are recorded, never values.

**Steps**

1. On the test laptop run a local collector (Docker):
   `docker run --rm -p 127.0.0.1:4318:4318 -v <spikes>/otel/collector.yaml:/etc/otelcol-contrib/config.yaml -v <out>:/out otel/opentelemetry-collector-contrib:0.111.0`
2. Apply `spikes/settings/S-10-telemetry-local.json` (managed settings on the test seat, or the user `env` block
   for this spike only). Do not set any `OTEL_LOG_*` content variables.
3. Quit and restart the app. Start a Local session on `<spikes>/sample-companion` and run `/tsl-spike:run demo T-1`.
4. Wait two export intervals, then close the session and stop the collector.
5. Run `python3 <spikes>/otel/list-names.py <out>/claude-code-otel.jsonl` and paste the output into the evidence.

**Expected observation:** metrics for sessions, tokens, cost, active time and tool decisions; events for skill
activation and plugin load; `session.id` on every record (V-17). No prompt or response text.

**Pass condition:** every name SDD-05 §7.2 keeps is identified, with its attribute keys. **Fallback:** the receiver
keeps the empty allowlist and stores only drop counts (SDD-08 §5.3).

| Run | Run by | OS / app version | Names found (summary) | session.id on all? | Pass? | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | | | | | | |

## S-11 · Seat usage of one workflow run (SDD-13 §8.3)

**Proves:** how many tokens one workflow run uses on a company seat, to size seats and set expectations (Q38).

**Steps**

1. Run S-10's collector and settings.
2. With the real `truminds` plugin (spike plugin disabled) and the invented sample system's companion repo, run
   `/truminds:run brownfield-change ABC-142` to the first pause, then to the PR after answering.
3. From the collector export, sum the token-usage metric for the session ids of the run (input, output, cache).
4. Repeat for `defect-fix` and `estimate` on the sample system.
5. Note any usage-limit message the app shows, with the step where it appeared.

**Expected observation:** a token total per workflow run, by step if the attributes allow.

**Pass condition:** one measured number per workflow, recorded in SDD-13 §8. **Fallback:** none; the number is
needed before the pilot.

| Run | Run by (with Claude admin) | Workflow | Tokens in / out / cache | Limit message? | Evidence |
| --- | --- | --- | --- | --- | --- |
| 1 | | brownfield-change | | | |
| 2 | | defect-fix | | | |
| 3 | | estimate | | | |

## S-12 · Managed settings for a subset or group of users (SDD-13 §6.2, OPS-03 §4.3)

**Proves:** whether the admin console can apply managed settings to a group of users rather than the whole
organisation.

**Steps**

1. With the Claude org admin, open claude.ai › Organization settings › Claude Code › Managed settings.
2. Look for a group, team or user scope selector. Record exactly what the screen offers.
3. If a scope exists, apply `spikes/settings/S-02-deny-rules.json` to a group that holds test seat A but not test
   seat B. Restart the app on both.
4. On both seats, start a Local session and type `Run curl https://example.com`.

**Expected observation:** seat A is blocked, seat B prompts as usual.

**Pass condition:** settings reach the group only. **Fallback:** MDM device groups, or an org-wide rollout with a
privacy notice to every seat holder and Puneet's approval (SDD-13 OI-13-03).

| Run | Run by (with Claude admin) | Scope options seen | Seat A | Seat B | Pass? | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | | | | | | |

## S-13 · Managed deny syntax for `WebFetch` and `WebSearch` (SEC-01 §6.3)

**Proves:** which permission rule strings block the built-in web tools.

**Steps**

1. Apply `candidate_a` from `spikes/settings/S-13-web-deny-candidates.json` (the `permissions` object only) as
   managed settings. Restart the app.
2. In a Local session type: `Fetch https://example.com and summarise it.` Then: `Search the web for example domains.`
3. Record whether each tool is blocked without a prompt.
4. Repeat with `candidate_b` and `candidate_c`.

**Expected observation:** at least one candidate blocks both tools with no prompt.

**Pass condition:** a working syntax is found and copied into the managed-settings template by pull request.
**Fallback:** keep the deny rules that do work and record the gap as a residual risk in SEC-01.

| Run | Run by | OS / app version | Candidate | WebFetch blocked? | WebSearch blocked? | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | | | a | | | |
| 2 | | | b | | | |
| 3 | | | c | | | |

## S-14 · When a force-enabled plugin updates (OPS-03 §4.1)

**Proves:** when Claude Code picks up a new plugin version after the marketplace changes: at session start, on a
timer, or only on a manual update.

**Steps**

1. Use the S-06 managed settings (force-enabled `tsl-spike` from `<test-org>/<spikes-repo>`).
2. Start a Local session; type `/plugin` and record the installed version.
3. In the repository, bump `tsl-spike/.claude-plugin/plugin.json` to the next patch version and push.
4. Without restarting, keep the session open for 30 minutes; type `/plugin` every 10 minutes.
5. Start a new session in the same app window and check again. Then quit and restart the app and check again.

**Expected observation:** the moment (new session, app restart, timer, or never) at which the new version shows.

**Pass condition:** the update moment is recorded. **Fallback:** the rollout notice tells engineers how to update by
hand, and `tsl doctor` reports the installed plugin version (OPS-03 §4.1).

| Run | Run by | OS / app version | Same session | New session | App restart | Pass? | Evidence |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | | | | | | | |

## S-15 · What happens when a hook's own `timeout` fires (OPS-04 §4.5)

**Proves:** whether Claude Code treats a PreToolUse hook that overruns its `timeout` as allow, deny or error. The
plugin launcher `bin/tsl-hook` already enforces its own deadline under the hook timeout (8 s for pre-tool, under the
10 s `timeout`), so the design is safe either way; this spike decides whether that deadline is still needed.

**Steps**

1. Create the flag file `~/.tsl-spike/S-15.on`. Delete `~/.tsl-spike/log/`.
2. Start a Local session on `<spikes>/sample-companion`. Type: `Create the file notes/s15.md with the line: s15`.
3. Wait for the tool call to complete or fail. Record what the session shows.
4. Check whether `notes/s15.md` exists and read `~/.tsl-spike/log/s15.log`.
5. Delete the flag file.

**Expected observation:** `s15.log` shows `start`; it shows `got TERM` (killed) or no further line. The record says
whether the Write went ahead (allow), was refused (deny) or reported a hook error, and whether the late deny printed
by `slow-hook` was ever honoured.

**Pass condition:** the behaviour is recorded. **Fallback:** keep the launcher deadline (already in place); if Claude
Code allows on timeout, the deadline is mandatory and TC-HK-002 keeps a timeout fixture.

| Run | Run by | OS / app version | Write happened? | Session message | s15.log | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | | | | | | |

---

## Clean-up after the spikes

1. Remove the managed settings applied for the spikes (admin console or the V-09 file).
2. In a Local session: `/plugin uninstall tsl-spike@truminds-spikes`, then `/plugin marketplace remove truminds-spikes`.
3. Remove the S-06 user hook from `~/.claude/settings.json`.
4. Delete `~/.tsl-spike/` and the throwaway `<test-org>/<spikes-repo>` repository.
