# truminds-tsl

`tsl` is the Truminds Skill Library command-line tool (SDD-04). It runs workflows, checks
artifacts, signs records and talks to the insights service. **Code decides; the model
proposes**: `tsl` never calls an LLM or the Claude API, and it runs the same on a laptop and
in CI. It writes only to the companion repo, to product-repo branches through `tsl pr`
(which never merges), to the skill-library repo through `tsl improve pr`, and to the
insights service.

- Python 3.12 only. Package `truminds-tsl`, entry point `tsl = "tsl.cli.app:main"`.
- The version is `src/tsl/__init__.py:__version__` and must equal
  `plugins/truminds/.claude-plugin/plugin.json` `version`. The build fails otherwise.
- The JSON Schemas live once, in `../schemas`. `hatch_build.py` force-includes the files
  listed in `../schemas/index.json` into the wheel at `tsl/schemas/bundled/` (and into the
  sdist at `schemas/`, so a wheel built from the sdist has them too). In a source checkout
  `tsl` reads `../schemas` directly.
- Identity and endpoints (tenant, client id, API scope, service URL) are fixed inside the
  wheel as `tsl/_org.toml`. The copy in git holds placeholders; a release build bakes real
  values from the `TSL_ORG_*` build-time variables in `.env.example`, or copies a complete
  org file named by `TSL_ORG_FILE`. Nothing at run time can change them.
- Identity provider (SDD-07 §1.4): `provider = "entra"` (default, production, MSAL device
  code, `identity/entra.py`) or `provider = "github"` (interim for the test phase, ADR 0006:
  GitHub OAuth device flow, `identity/github.py`). Both sit behind the same interface, so
  `login`, `logout`, `whoami` and `doctor` work the same. The GitHub token is sealed exactly
  like the MSAL cache (AES-256-GCM, key in the OS keychain, `~/.truminds/github-token.bin`).
  Build a GitHub test wheel with
  `TSL_ORG_FILE=../deploy/test-org.github.toml uv build --wheel` (see `deploy/README.md`).

## Set up, run, test

```bash
cd tsl
uv sync --python 3.12                    # venv with runtime + dev dependencies
uv run tsl --help
uv run --python 3.12 pytest -q           # whole suite; no network, no real tenant
uv run ruff check . && uv run ruff format --check .
uv run mypy                              # strict, src/tsl and tests
uv build                                 # sdist + wheel (schemas bundled)
```

Install for daily use: `uv tool install "truminds-tsl @ <release-wheel-URL>"` (SDD-05 §7.1).
Developers use `uv tool install --editable ./tsl`.

### Test approach

- All network goes through fakes injected with a `Runtime` (`tests/helpers.py`): a fake
  Entra identity provider (and a fake `msal` module for `MsalIdentity`), a fake insights
  service (keys, `/v1/me`, systems, signature registry, `POST /v1/events`, improvement
  report), a fake GitHub API and a fake verifier. Keys are generated per test; the key
  store is in memory. No test reaches the network.
- Each test builds a temp "world": a bare-remote companion repo and a product repo on an
  invented order-tracking system, an invented plugin (`tests/fixtures/plugin`), and logged-in
  engineer and tech-lead users. The real `plugins/truminds/skills/requirement-review` skill
  and its eval cases are also used as fixtures (`test_e2e_real_skill.py`,
  `test_commands.py`).
- Hook contracts are golden files: `tests/hooks/fixtures/<event>/<case>.stdin.json` and
  `<case>.expect.json` (exit code, exact stdout, `hook.log` line, `hook.decision` event).
- Docker-dependent tests (`tests/test_docker.py`, marker `docker`) skip when no Docker
  daemon is running.

| Test file | What it covers |
| --- | --- |
| `test_core.py` | Error catalogue vs registry (codes, exits), envelope vs `tsl-output.v1`, version pin, `--version` fast path, E-USE-01, E-REPO-01, E-INT-01 without traceback, log redaction |
| `test_identity.py` | RFC 8785 canonical JSON, Ed25519 sign/verify round trip and tamper detection, accept rule, sealed MSAL cache, keyring backend rule, Entra device code via `msal`, `login`/`logout`/`whoami`/`keys` |
| `test_identity_github.py` | GitHub provider through `httpx.MockTransport`: device flow with `authorization_pending`, `slow_down` (interval raised), `expired_token`, `access_denied`, local deadline, Device Flow disabled; sealed token at rest; rejected token deleted; provider picked from `_org.toml`; `login`/`whoami`/`doctor`/`logout` and re-login after a rejected stored token; the deploy test org file is valid |
| `test_state_lock.py` | Lock protocol: take and push, E-LOCK-01 (local, other laptop, push race), E-LOCK-03, E-LOCK-04; `state show/cancel/unlock/resume/repair/repin`, E-RUN-11, start preconditions |
| `test_citations.py` | Citation grammar, resolution (companion tree, product repo at SHA, read-deny, symbols, keys), quote and element matching, dropped findings and S1 |
| `test_decide_table.py` | Every row of the SDD-03 §11.1 decision table, row order, caps, band boundaries |
| `test_outbox.py` | SQLite outbox: validation, 202/duplicates/rejected, offline, 401 refresh, 413 split, 429/5xx backoff, lease expiry, never-drop, 4-process concurrency; `events flush` |
| `test_commands.py` | `doctor`, `init`, `validate`, `verify`, `review`, `decide`, `approve`, `pr` refusals, no merge API, `context *`, `eval *`, `migrate` |
| `test_improve.py` | `improve plan/case/check/pr` and E-IMP-01…05 |
| `test_companion_harness.py` | `companion check` (E-COMP-01…05), `companion archive` (E-COMP-06, signed ARCHIVE.json), `harness eval` |
| `test_injection.py` | SC-INJ-01: plugin marker file = SEC-01 §6.5, injected artifact and input flagged, clean text passes, code blocks scanned, S2 lowered without a gate failure, `tsl verify` output and PR body (SEC-T-19) |
| `test_docker.py` | Verifier `docker run` flags (no network except prepare, read-only source, limits, non-root, cap-drop), placeholder digest refused; real Docker tests skip without a daemon |
| `test_e2e*.py` | Simulated runs: requirement-review → decide, gates, NEEDS-INPUT/resume, retries, abort, code step → PR → `ci-verify` |
| `hooks/test_hook_contract.py` | `tsl hook <event>` golden stdin/stdout, fail-closed and fail-open, fast path imports |

## Traceability

| SDD section | Module / file |
| --- | --- |
| SDD-04 §2–§4 package, globals, envelope | `cli/app.py`, `cli/commands.py`, `core/envelope.py`, `core/runtime.py` |
| SDD-04 §5, registry §2 error codes | `core/errors.py` |
| SDD-04 §6.1–6.2, SDD-07 §4–§5 login, keys | `services/identity_cmds.py`, `identity/entra.py`, `identity/keys.py`, `identity/keystore.py`, `identity/me.py`, `identity/org.py` |
| SDD-07 §1.4, ADR 0006 GitHub interim provider | `identity/github.py`, `identity/org.py` (`provider`, `github_*`), `core/runtime.py` (`identity()`), `hatch_build.py` (`TSL_ORG_FILE`) |
| SDD-07 §6 canonical JSON, Ed25519 | `identity/signing.py` |
| SDD-07 §7.3 accept rule | `identity/verify.py` |
| SDD-04 §6.3 doctor | `services/doctor.py` |
| SDD-04 §6.4, SDD-12 §5.3 init | `services/init.py` |
| SDD-04 §6.5, SDD-01 §14, SDD-02 §3.5 validate | `services/validate.py`, `orchestrator/workflow.py`, `orchestrator/skills.py` |
| SDD-04 §6.6, SDD-03 §4 H1–H7, §5 checks | `harness/verify.py`, `harness/gates.py`, `harness/skillchecks.py`, `harness/detectors.py`, `harness/verifier.py`, `harness/artifact.py` |
| SDD-04 §6.7, SDD-02 §5, §11–§12 state, locks, resume | `state/service.py`, `state/lock.py`, `state/store.py`, `state/session.py` |
| SDD-04 §6.8, SDD-02 §6–§9 next, retries, gates | `orchestrator/next.py`, `orchestrator/run.py` |
| SDD-04 §6.9, SDD-03 §7 review prepare/record | `review/service.py` |
| SEC-01 §6.2 (L1), §6.5 `SC-INJ-01` soft check; SDD-03 §9 S2 | `harness/injection.py`, `harness/gates.py` (`injection_check`), `harness/verify.py`, `services/pr.py` (PR body) |
| SDD-03 §5.5, SEC-01 §8.4 verifier container flags | `harness/verifier.py` (`docker_command`, `image_digest`) |
| SDD-03 §8 citations | `harness/citations.py` |
| SDD-03 §9–§11 signals S1–S6, bands, decide | `harness/decide.py`, `core/config.py` (`effective_bands`) |
| SDD-04 §6.10, SDD-03 §12 check record, signing | `harness/decide_service.py` |
| SDD-04 §6.11, SDD-07 §6.4 approve | `approvals/service.py`, `approvals/approvals_md.py`, `approvals/questions_md.py` |
| SDD-04 §6.12, SDD-12 §4.2 pr (never merges) | `services/pr.py`, `github/client.py`, `gitops/git.py` |
| SDD-04 §6.13, SDD-03 §13 ci-verify | `ci/verify.py` |
| SDD-04 §6.14, SDD-05 §5 hooks | `hooks/dispatch.py`, `hooks/session.py`, `hooks/pre_tool.py`, `hooks/pre_mcp.py`, `hooks/post_write.py` |
| SDD-04 §6.15, SDD-06 §5–§7 context build, sign, status, draft-prepare, deny-term | `context/build.py`, `context/extractors.py`, `context/freshness.py`, `context/repoview.py` |
| SDD-04 §6.16, SDD-01 §10 eval plan, run, check | `evals/service.py` |
| SDD-04 §6.17, SDD-11 §5–§6 improve plan, case, check, pr | `improve/plan.py`, `improve/service.py` |
| SDD-03 §16 harness eval | `harness/accuracy.py` |
| SDD-04 §6.18, §8, SDD-08 `POST /v1/events` outbox | `telemetry/outbox.py`, `telemetry/emit.py`, `insights/client.py` |
| SDD-04 §6.19 migrate | `services/migrate.py` |
| SDD-12 §6.4, §8.2 companion check, archive | `services/companion.py` |
| SDD-04 §7 config files | `core/config.py`, `core/repo.py`, `core/paths.py` |
| SDD-04 §9 logging | `core/log.py` |
| SDD-04 §10 N/N-1 schemas | `schemas/registry.py`, `schemas/compat.py`, `hatch_build.py` |

## Known limits

- `tsl migrate` lists what it would migrate; no schema has a v2 with an upgrade function yet,
  so a non-dry run refuses (E-USE-01).
- `harness eval` scores gate, citation and decide cases by code. H6 and H7 cannot be measured
  on standalone cases (they need run state); they are reported under `unmeasured`.
  Reviewer cases need a recorded reviewer output and are skipped with `--code-only`.
- `companion archive` signs and tags the archive; setting the GitHub repository to
  archived is left to the admin (no GitHub write API is called).
- The CLI layer is one module (`cli/commands.py`) rather than one module per command group
  as drawn in SDD-04 §2.3; the layering rule (services never import Typer) holds.
