# schemas/ — JSON Schemas for every Truminds contract

Every file format, record and telemetry event in the skill library has a JSON Schema here (Doc 5 §1.1, §3; registry §6). They use JSON Schema draft 2020-12. Each schema has a `$id` of `https://schemas.truminds.internal/<file>`, a `title`, a `description` and an `x-owner` that names its owning document. `tsl` bundles these files to validate what it reads and writes (H1, `tsl validate`, `tsl ci-verify`). The insights service uses `event-envelope.v1` and `events/*` to check ingested events (SDD-08 §4.2).

## Layout

```text
schemas/
├─ <name>.v<N>.json                  file and record schemas (59 from registry §6, plus envelope.v1 and event-envelope.v1)
├─ events/<type>.v<N>.json           one closed body schema per event type (registry §5, SDD-08 §4.5)
├─ index.json                        machine-readable list: name, version, file, $id, kind, owner, event_type
├─ fixtures/<name>.v<N>/valid/       ≥ 2 documents (JSON or YAML) that must pass
├─ fixtures/<name>.v<N>/invalid/     ≥ 3 documents that must fail; each has <reason>.expect.json {pointer, keyword}
├─ fixtures/events/<type>.v<N>/      the same, for event bodies
├─ tests/test_schemas.py             contract tests (TC-SCH-001..003)
└─ pyproject.toml                    test-only project (pytest, jsonschema, PyYAML, rfc3339-validator)
```

## How to load (tsl, insights service)

Read `index.json`. Each entry gives the schema id (`review.v1`), `name`, integer `version`, relative `file`, `$id`, `kind` (`file`, `event`, `event-envelope`) and `owner`. Event entries also carry `event_type`. Every schema is self-contained, with all `$defs` inlined and no cross-file `$ref`, so you can load each file on its own. Validate with `format` checks turned on, because `date-time` and `regex` are enforced.

Artifact front matter is validated against its body schema (for example `design.v1`). Each body schema includes the common envelope through `allOf: [{$ref: "#/$defs/envelope"}]`. Body schemas also carry the harness hints that SDD-03 asks for: `x-required-sections` (H2), and where relevant `x-trace`, `x-acceptance-criteria` and `x-claims-required`. Validators ignore these keys; `tsl` reads them.

## Compatibility rule: N and N-1

- Every file carries `schema: <name>.v<N>`. Every event carries `schema_version`.
- **Additive changes keep N.** A new optional field, or a looser enum on a non-signed field, stays at the same N. **Breaking changes bump N**: a removed or renamed field, a new required field, a tighter type or pattern, or a changed meaning. The old file stays here next to the new one.
- **Readers accept N and N-1** (Doc 5 R-09; SDD-04 §10). `tsl` upgrades an N-1 file in memory before it validates. Anything older fails with `E-SCH-01`, and `tsl migrate` is the way forward. The insights service accepts N and N-1 per event type. An unknown version comes back as `E-ING-02` and stays queued in the outbox.
- **Writers emit N only.**
- **Signed records** (`verification.v1`, `approval-signature.v1`, `pack-signature.v1`, `eval-result.v1`, `audit.v1`) are always verified against their stored bytes at their own version. They are never re-serialised after an upgrade.
- When N is bumped, keep the N-1 schema and its fixtures until no supported reader needs it (TST-01 §2.2).

## Run the tests

```bash
cd schemas
uv run --python 3.12 pytest          # 1121 tests
uv run --python 3.12 ruff check tests
```

The tests check four things. First, every schema meta-validates and has `$id`, `title`, `description` and `x-owner`. Second, `index.json` matches the files on disk. Third, every schema that registry §5 and §6 lists exists, and every file is listed in the registry. Fourth, the fixtures behave as expected:

- every valid fixture passes;
- every invalid fixture fails at the JSON pointer and keyword given in its `.expect.json`, so it cannot pass for the wrong reason (TC-SCH-002);
- every event body is closed and every string in it is capped at 200 characters, or limited by a pattern or enum (TC-SCH-003, TM-08).

All fixture data is invented: the sample order-tracking system, `example-org`, `example.test` and pseudonyms such as `eng-4f2a`.

## Traceability

| Source section | Files |
| --- | --- |
| Doc 5 §3.1, SDD-04 §7.2, SDD-12 §4.1 | `tsl-config.v1.json` |
| SDD-04 §4, §6.14, §7.1 | `tsl-output.v1.json`, `session-index.v1.json`, `user-config.v1.json` |
| SDD-12 §4.1 | `tsl-local.v1.json` |
| Doc 5 §3.2, SDD-01 §4, §8, §9, §10, §5 | `skill-metadata.v1.json`, `rubric.v1.json`, `skill-checks.v1.json`, `eval-set.v1.json`, `eval-case.v1.json`, `eval-result.v1.json`, `ticket-snapshot.v1.json` |
| TST-01 §3.1 | `eval-expect.v1.json` |
| Doc 5 §3.6, SDD-01 §12–§13, Doc 3 §7 | `envelope.v1.json` and the 18 artifact body schemas (`intent.v1.json` … `status.v1.json`) |
| Doc 5 §3.3–§3.5, SDD-02 §3, §5.3, §6, §8.2, §11.1 | `workflow.v1.json`, `workflow-lock.v1.json`, `run-state.v1.json`, `run-lock.v1.json`, `next-action.v1.json`, `feedback.v1.json` |
| Doc 4 §3, §4.2, SDD-02 §9 | `open-questions.v1.json`, `approvals.v1.json` |
| SDD-07 §6.4 | `approval-signature.v1.json` |
| Doc 5 §3.7, SDD-03 §2.1, §5.5, §6, §7, §12, §16 | `checks.v1.json`, `review-package.v1.json`, `review.v1.json`, `verification.v1.json`, `tool-log.v1.json`, `audit.v1.json`, `harness-case.v1.json`, `verifier-profile.v1.json` |
| SDD-03 §4.6, SEC-01 §6.5, §7.2–§7.3 | `secrets.v1.json`, `pii.v1.json`, `injection-markers.v1.json` |
| SDD-05 §6.4 | `policy.v2.json` |
| SDD-06 §3.3, §4.1–§4.3 | `context-section.v1.json`, `context-pack.v1.json`, `context-facts.v1.json`, `pack-signature.v1.json` |
| SDD-10 §3 | `pod.v1.json` |
| SDD-11 §6.2 | `improvement.v1.json` |
| LEG-01 §13.1 | `consent-record.v1.json` |
| Doc 5 §5.2, SDD-08 §4.5, registry §5 | `event-envelope.v1.json`, `events/*.v1.json` |

Schemas marked `"x-fields-status": "provisional"` cover formats whose owning doc names the file but does not fix its fields. These are `ticket-snapshot.v1`, `workflow-lock.v1`, `review-package.v1` and 17 of the 18 artifact body schemas; `intent.v1` is fully specified and closed. These schemas type the fields they define but stay open to extra keys. They must be closed when the owning SDD fixes the field list.

## Index

| Schema | Version | Kind | Owner doc | Description |
| --- | --- | --- | --- | --- |
| [`tsl-config.v1`](tsl-config.v1.json) | 1 | file | SDD-04 §7.2 | Per-companion-repo configuration: system codes, product repos, context and change limits, gates, PR and harness settings. Values may only tighten org defaults (E-CFG-01). |
| [`user-config.v1`](user-config.v1.json) | 1 | file | SDD-04 §7.1 | Per-user tsl settings, stored as TOML and validated as the equivalent JSON object. Holds no identity provider or service endpoint values (those ship inside the wheel). |
| [`tsl-output.v1`](tsl-output.v1.json) | 1 | file | SDD-04 §4 | The one JSON object every tsl command (except tsl hook) prints on stdout with --json. Skills read only ok, code, exit, next and data.action. |
| [`session-index.v1`](session-index.v1.json) | 1 | file | SDD-04 §6.14 | ~/.truminds/sessions/<session_id>.json: binds a Claude Code session to the run it holds, so the pre-tool hook has a fast path when no run is bound. |
| [`tsl-local.v1`](tsl-local.v1.json) | 1 | file | SDD-12 §4.1 | Laptop-local, git-ignored map from product repo short name to its clone path. Written by tsl init and tsl doctor. |
| [`skill-metadata.v1`](skill-metadata.v1.json) | 1 | file | SDD-01 §4 | Truminds manifest of one SDLC skill: identity, version, status, owner, inputs, outputs, limits, rubric, checks, evals and permitted tools. |
| [`rubric.v1`](rubric.v1.json) | 1 | file | SDD-01 §8 | Machine-read front matter of a skill's rubric: weighted criteria the reviewer scores 1-5 (signal S3) and severity triggers. Weights must sum to 1.00 (SKL-V07, checked by tsl validate). |
| [`skill-checks.v1`](skill-checks.v1.json) | 1 | file | SDD-01 §9 | Code checks a skill's artifact must pass, selected from the tsl check library with parameters. Accepts the SDD-01 §9 library form (uses) and the SDD-03 §5.3 kind form. |
| [`eval-set.v1`](eval-set.v1.json) | 1 | file | SDD-01 §10 | Header of a skill's eval set: minimum case count and pass rate, and the invented system the fixtures describe. |
| [`eval-case.v1`](eval-case.v1.json) | 1 | file | SDD-01 §10 | One eval case: invented input fixtures and code-checked expectations (outcome set, gate results, JMESPath assertions). provenance and attestation are required by SDD-11 GR-6. |
| [`eval-expect.v1`](eval-expect.v1.json) | 1 | file | TST-01 §3.1 | TST-01 sketch of case expectations: outcome set, band floor, gates that must pass, citations that must appear and invented elements that must not be claimed. SDD-01 owns the final format. |
| [`eval-result.v1`](eval-result.v1.json) | 1 | file | SDD-01 §10 | skills/<skill>/evals/results/<version>.eval-result.json: signed by the skill author's key; binds case results and pass rate to an exact skill version and content hash. |
| [`ticket-snapshot.v1`](ticket-snapshot.v1.json) | 1 | file | SDD-01 §5 | Read-only snapshot of the run's ticket, written by the run loop before the first step and hashed like any artifact so H6 staleness works on it. Field list is provisional until SDD-02 settles who writes it (SDD-01 O-07). |
| [`envelope.v1`](envelope.v1.json) | 1 | file | Doc 5 §3.6 | Common YAML front matter of every artifact <step>.md: identity of the attempt, input hashes, pack SHAs, claims with citations, trace and Known/Assumed/Unknown lists, plus the additive questions, resolves and code blocks (SDD-02 §12). Body schemas add their own keys. |
| [`intent.v1`](intent.v1.json) | 1 | file | SDD-01 §12 | Output of requirement-review: numbered requirements with Known/Assumed/Unknown status, unknowns, questions and glossary checks (SDD-01 §13.2). |
| [`stories.v1`](stories.v1.json) | 1 | file | SDD-01 §12 | Output of story-split: user stories traced to REQ ids with Given/When/Then acceptance criteria. Structured keys beyond the envelope are provisional until SDD-01 §12 fixes them. |
| [`impact.v1`](impact.v1.json) | 1 | file | SDD-01 §12 | Output of impact-analysis: modules, APIs and tables the change touches, each looked up in the generated facts. Structured keys beyond the envelope are provisional until SDD-01 §12 fixes them. |
| [`design.v1`](design.v1.json) | 1 | file | SDD-01 §12 | Output of design: components on existing modules and endpoints marked new, changed or existing. Structured keys beyond the envelope are provisional until SDD-01 §12 fixes them. |
| [`threat-model.v1`](threat-model.v1.json) | 1 | file | SDD-01 §12 | Output of threat-model: STRIDE rows per design component. Structured keys beyond the envelope are provisional until SDD-01 §12 fixes them. |
| [`change.v1`](change.v1.json) | 1 | file | SDD-01 §12 | Output of implement: summary of the code change; code[] binds the artifact to the run branch diff. Structured keys beyond the envelope are provisional until SDD-01 §12 fixes them. |
| [`ut-result.v1`](ut-result.v1.json) | 1 | file | SDD-01 §12 | Output of unit-test: tests run and coverage compared with the base. Structured keys beyond the envelope are provisional until SDD-01 §12 fixes them. |
| [`secure-review.v1`](secure-review.v1.json) | 1 | file | SDD-01 §12 | Output of secure-code-review: SAST and secrets scan results referenced by hash, and findings. Structured keys beyond the envelope are provisional until SDD-01 §12 fixes them. |
| [`test-plan.v1`](test-plan.v1.json) | 1 | file | SDD-01 §12 | Output of test-plan: tests that cover every acceptance criterion. Structured keys beyond the envelope are provisional until SDD-01 §12 fixes them. |
| [`test-result.v1`](test-result.v1.json) | 1 | file | SDD-01 §12 | Output of test-automation: results linked to acceptance criteria. Structured keys beyond the envelope are provisional until SDD-01 §12 fixes them. |
| [`triage.v1`](triage.v1.json) | 1 | file | SDD-01 §12 | Output of defect-triage: candidate components with likelihood and citations. Structured keys beyond the envelope are provisional until SDD-01 §12 fixes them. |
| [`plan.v1`](plan.v1.json) | 1 | file | SDD-01 §12 | Generic plan artifact listed in registry §6; no skill in the Release-1 catalogue produces it yet. Structured keys beyond the envelope are provisional until SDD-01 §12 fixes them. |
| [`pipeline-review.v1`](pipeline-review.v1.json) | 1 | file | SDD-01 §12 | Output of pipeline-review: findings that cite CI jobs and steps. Structured keys beyond the envelope are provisional until SDD-01 §12 fixes them. |
| [`deploy-failure.v1`](deploy-failure.v1.json) | 1 | file | SDD-01 §12 | Output of deployment-failure-analysis: probable cause and findings citing stored log lines. Structured keys beyond the envelope are provisional until SDD-01 §12 fixes them. |
| [`ux-flow.v1`](ux-flow.v1.json) | 1 | file | SDD-01 §12 | Output of ux-flow-review: findings that cite design-tool node ids (node: anchors). Structured keys beyond the envelope are provisional until SDD-01 §12 fixes them. |
| [`a11y.v1`](a11y.v1.json) | 1 | file | SDD-01 §12 | Output of accessibility-review: findings mapped to WCAG 2.1 AA success criteria. Structured keys beyond the envelope are provisional until SDD-01 §12 fixes them. |
| [`estimate.v1`](estimate.v1.json) | 1 | file | SDD-01 §12 | Output of estimate-review: a size per story with cited evidence, else UNSIZED. Structured keys beyond the envelope are provisional until SDD-01 §12 fixes them. |
| [`status.v1`](status.v1.json) | 1 | file | SDD-01 §12 | Output of status-report: run counts per status that must equal the state.json files. Structured keys beyond the envelope are provisional until SDD-01 §12 fixes them. |
| [`workflow.v1`](workflow.v1.json) | 1 | file | SDD-02 §3 | <id>.workflow.yaml in plugins/truminds/workflows/: ordered skill, gate and PR steps with input bindings. Graph rules (ids, cycles, reachability, bindings) are checked by tsl validate (E-WFL-02..05). |
| [`workflow-lock.v1`](workflow-lock.v1.json) | 1 | file | SDD-02 §3.5 | <id>.lock.json written by tsl validate --lock at release: each skill range of the workflow resolved to the exact version present in the plugin. Field list is provisional (SDD-02 names the file but not its fields). |
| [`run-state.v1`](run-state.v1.json) | 1 | file | SDD-02 §5.3 | The run's state: status, pins, pack status, steps with every attempt, gates, questions and PRs. Written only by tsl with optimistic concurrency on rev. |
| [`run-lock.v1`](run-lock.v1.json) | 1 | file | SDD-02 §11.1 | The single lock file per ticket and workflow. Its fixed path makes a second laptop's git push fail (registry §10 row 9). Removed at COMPLETED or by tsl state unlock. |
| [`next-action.v1`](next-action.v1.json) | 1 | file | SDD-02 §6 | The data object of tsl next --json: one action for the run skill loop, with the step, attempt, pinned skill, artifact path, resolved inputs, feedback, answers, budget and progress. |
| [`feedback.v1`](feedback.v1.json) | 1 | file | SDD-02 §8.2 | Written by tsl decide on every RETRY and passed to attempt N+1: failed gates, verified findings, dropped finding ids and the ids the next artifact must resolve. |
| [`open-questions.v1`](open-questions.v1.json) | 1 | file | Doc 4 §3, SDD-02 §9.1 | Front matter of open-questions.md plus the question blocks as tsl parses them. People fill only answer, answered_by and decision; tsl sets status. |
| [`approval-signature.v1`](approval-signature.v1.json) | 1 | file | SDD-07 §6.4 | Signed block that tsl approve appends under a gate entry in approvals.md, between tsl:signature-begin and tsl:signature-end markers. Ed25519 over JCS of the block without signature. |
| [`approvals.v1`](approvals.v1.json) | 1 | file | Doc 4 §4.2, SDD-02 §9.2 | Front matter of approvals.md plus gate entries as tsl parses them; each signed entry carries an approval-signature.v1 block. |
| [`checks.v1`](checks.v1.json) | 1 | file | SDD-03 §6 | Code-check record written by tsl verify: hard gates H1-H7 with codes, soft checks, input hashes, verifier evidence and product changes for code steps. |
| [`review-package.v1`](review-package.v1.json) | 1 | file | SDD-03 §7 | What tsl review prepare hands the reviewer: artifact, rubric, context sections and inputs by path, previous findings, and package_sha256 over the JCS form without that field. Field list is provisional. |
| [`review.v1`](review.v1.json) | 1 | file | SDD-03 §7.3 | Reviewer subagent output as stored by tsl review record: rubric scores, cited findings, claim verdicts and questions. Every citation is an object with ref and an 8-200 character quote. |
| [`verification.v1`](verification.v1.json) | 1 | file | SDD-03 §12.1 | The signed check record written by tsl decide: hashes of the artifact, checks and review, input chain, kept and dropped findings, signals S1-S6, band, outcome and caps. Ed25519 over JCS without signature. |
| [`tool-log.v1`](tool-log.v1.json) | 1 | file | SDD-03 §2.1 | One JSON line per Write, Edit, NotebookEdit, Bash or MCP call seen by the pre-tool and pre-mcp hooks. Append-only; H7 checks it. target never leaves the companion repo. |
| [`audit.v1`](audit.v1.json) | 1 | file | SDD-03 §16.3 | Signed calibration audit of a High-band outcome by a tech lead who is not the run owner: deserved or miss, with a reason code. |
| [`harness-case.v1`](harness-case.v1.json) | 1 | file | SDD-03 §16 | Labels for one harness-accuracy case on the invented sample system: expected gate results, outcome, band, planted defects and fabricated citations. |
| [`verifier-profile.v1`](verifier-profile.v1.json) | 1 | file | SDD-03 §5.5 | Container verifier profile for H3: image pinned by digest and the prepare, build, test, lint, sast, secrets and optional coverage steps. Only prepare may use the network. |
| [`policy.v2`](policy.v2.json) | 2 | file | SDD-05 §6.4 | Run-dependent rules read by the pre-tool and pre-mcp hooks: write scope, Bash patterns in a run and MCP read/write classification. The org file is complete; a system's policy.yaml may only add denies (structurally: it cannot carry allow or read_tools lists). |
| [`context-pack.v1`](context-pack.v1.json) | 1 | file | SDD-06 §4.1 | Pack index written by tsl context build: sources at exact commits, extractors, sections with hashes, anchors and token estimates, redaction counts and effective limits. No timestamps, so it is byte-stable. |
| [`context-section.v1`](context-section.v1.json) | 1 | file | SDD-06 §3.3 | Front matter of each human-curated context/*.md section. Only a human sets status reviewed; tsl context sign requires reviewed. |
| [`context-facts.v1`](context-facts.v1.json) | 1 | file | SDD-06 §4.3 | Common envelope of every generated fact file. Fact ids are stable strings built from the fact itself (SDD-06 §3.4); fact fields beyond id, kind and source vary per extractor. |
| [`pack-signature.v1`](pack-signature.v1.json) | 1 | file | SDD-06 §4.2 | Tech lead's Ed25519 signature over the manifest hash and source commits (tsl context sign). signed_at is for key validity and audit only; freshness never uses it. |
| [`companion-archive.v1`](companion-archive.v1.json) | 1 | file | SDD-12 §8.2 | Admin-signed `ARCHIVE.json` written by `tsl companion archive`: system code, last commit, run and record counts, SHA-256 over the sorted record hashes. |
| [`pod.v1`](pod.v1.json) | 1 | file | SDD-10 §3 | Pod definition: agents built from roles and skills, workflows, people and gates, business view and machine-checkable fit requirements. |
| [`improvement.v1`](improvement.v1.json) | 1 | file | SDD-11 §6.2 | Evidence file written by tsl improve check: the flags addressed, the new failing-first cases, before and after signed eval results, and regressions. signature here is the failure signature string, not a crypto signature. |
| [`consent-record.v1`](consent-record.v1.json) | 1 | file | LEG-01 §13.1 | Fields the insights service keeps about a signed client consent (codes only; the signed document lives in the contract store). Enforced by tsl init, context build and state start (E-CONS-01). |
| [`secrets.v1`](secrets.v1.json) | 1 | file | SDD-03 §4.6 | H4a secret detector rule set shipped in tsl: detect-secrets plugins with limits plus Truminds regex rules (SEC-01 §7.2). Hits report the rule id and line only, never the value. |
| [`pii.v1`](pii.v1.json) | 1 | file | SDD-03 §4.6 | H4b personal-data detector rule set shipped in tsl (SEC-01 §7.3): regex plus checksum validators, reserved ignores and context words. Hits report the rule id and line only. |
| [`injection-markers.v1`](injection-markers.v1.json) | 1 | file | SEC-01 §6 | Case-insensitive phrase list for the SC-INJ-01 soft check. A match lowers S2 and is listed in the PR body; it never blocks a run on its own. |
| [`event-envelope.v1`](event-envelope.v1.json) | 1 | event-envelope | Doc 5 §5.2 | One event inside a POST /v1/events batch. The body is validated separately against schemas/events/<type>.v<schema_version>.json. No user field: the server sets the user from the token. |
| [`session.started.v1`](events/session.started.v1.json) | 1 | event | SDD-08 §4.5 | Sent by the session-start hook. Closed object; every string is length-capped (TM-08). |
| [`session.ended.v1`](events/session.ended.v1.json) | 1 | event | SDD-08 §4.5 | Sent by the session-end hook. Closed object; every string is length-capped (TM-08). |
| [`run.started.v1`](events/run.started.v1.json) | 1 | event | SDD-08 §4.5 | Sent by tsl state start. Closed object; every string is length-capped (TM-08). |
| [`run.status_changed.v1`](events/run.status_changed.v1.json) | 1 | event | SDD-08 §4.5 | Sent by tsl state, decide and pr. reason_code values follow SDD-02 §12, or an error code. Closed object; every string is length-capped (TM-08). |
| [`step.started.v1`](events/step.started.v1.json) | 1 | event | SDD-08 §4.5 | Sent by tsl next when it opens an attempt. Closed object; every string is length-capped (TM-08). |
| [`step.decided.v1`](events/step.decided.v1.json) | 1 | event | SDD-08 §4.5 | Sent by tsl decide. Carries ids, counts and codes only; no findings text. Closed object; every string is length-capped (TM-08). |
| [`step.invalidated.v1`](events/step.invalidated.v1.json) | 1 | event | SDD-08 §4.5 | Sent by tsl next when a step goes STALE (SDD-02 §10.2). Closed object; every string is length-capped (TM-08). |
| [`question.created.v1`](events/question.created.v1.json) | 1 | event | SDD-08 §4.5 | Sent by tsl decide per question. No question text (RD-3 default). Closed object; every string is length-capped (TM-08). |
| [`question.answered.v1`](events/question.answered.v1.json) | 1 | event | SDD-08 §4.5 | Sent by tsl state resume per answered question. Closed object; every string is length-capped (TM-08). |
| [`approval.recorded.v1`](events/approval.recorded.v1.json) | 1 | event | SDD-08 §4.5 | Sent by tsl approve. Closed object; every string is length-capped (TM-08). |
| [`hook.decision.v1`](events/hook.decision.v1.json) | 1 | event | SDD-08 §4.5 | Sent by every hook invocation. Closed object; every string is length-capped (TM-08). |
| [`pr.opened.v1`](events/pr.opened.v1.json) | 1 | event | SDD-08 §4.5 | Sent by tsl pr per product repo. Closed object; every string is length-capped (TM-08). |
| [`ci.verified.v1`](events/ci.verified.v1.json) | 1 | event | SDD-08 §4.5 | Sent by tsl ci-verify with the CI ingest token (the only type that token may send). Closed object; every string is length-capped (TM-08). |
| [`context.signed.v1`](events/context.signed.v1.json) | 1 | event | SDD-08 §4.5 | Sent by tsl context sign. Closed object; every string is length-capped (TM-08). |
| [`context.drift.v1`](events/context.drift.v1.json) | 1 | event | SDD-08 §4.5 | Sent by tsl context build --check. Closed object; every string is length-capped (TM-08). |
| [`eval.recorded.v1`](events/eval.recorded.v1.json) | 1 | event | SDD-08 §4.5 | Sent by tsl eval run. Closed object; every string is length-capped (TM-08). |
| [`security.abort.v1`](events/security.abort.v1.json) | 1 | event | SDD-08 §4.5 | Sent by tsl decide or a hook when a run aborts on E-SEC or E-POL. Closed object; every string is length-capped (TM-08). |
| [`audit.recorded.v1`](events/audit.recorded.v1.json) | 1 | event | SDD-08 §4.5 | Sent after a calibration audit (SDD-03 §16.3); run_id is in the envelope. Closed object; every string is length-capped (TM-08). |
| [`companion.lifecycle.v1`](events/companion.lifecycle.v1.json) | 1 | event | SDD-08 §4.5 | Sent by tsl init and tsl companion archive (SDD-12 §9). Closed object; every string is length-capped (TM-08). |
| [`companion.policy_violation.v1`](events/companion.policy_violation.v1.json) | 1 | event | SDD-08 §4.5 | Sent by companion CI (tsl companion check). Closed object; every string is length-capped (TM-08). |
| [`improvement.proposed.v1`](events/improvement.proposed.v1.json) | 1 | event | SDD-08 §4.5 | Sent by tsl improve pr (SDD-11 §10). Closed object; every string is length-capped (TM-08). |
