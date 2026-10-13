# Companion repo example: SYS-SMP (Order Tracker)

A skeleton of the companion repo `cl-int-sys-smp-companion` for the sample system, laid out
per SDD-12 §3.1 and SDD-06 §3. Codes only, never names: client `CL-INT`, project `PRJ-SMP`,
system `SYS-SMP`. The org `example-org` stands in for `<companion-org>` (OQ-10 open).

| Path | What it is | Owning doc |
| --- | --- | --- |
| `tsl.yaml` | `tsl-config.v1`: system codes, the `sample-system` product repo, context and change limits, gates | SDD-04 §7.2, SDD-12 §4.1 |
| `CODEOWNERS`, `.gitignore`, `.gitattributes` | Template files: tech leads own config and context; `.tsl/` never committed; LF line endings for stable hashes | SDD-12 §3.1 |
| `context/*.md` | The seven judgement sections in `context-section.v1` form, status `drafted`, anchors `{#id}` and `Sources:` lines | SDD-06 §3.2, §3.3 |

Not committed here, because only `tsl` writes them: `context/generated/*.json`
(`tsl context build`), `context/manifest.json` (`tsl context build`) and
`context/pack.signature.json` (`tsl context sign`, tech lead only). `artifacts/` and `runs/`
appear when workflows run. `.tsl/local.yaml` maps `sample-system` to a local clone and is
never committed.

`context/data-model.md#data-retention` is the SDD-06 §10 worked-example block: "Order events are
deleted after 24 hours", citing `sample-system:api/src/jobs/purge-events.ts#L12`.

## Validate

From the repository root:

```bash
uv run --project tsl tsl validate examples/sample-system/companion-example/tsl.yaml
```

Every `Sources:` line cites a real line of the sample system as committed. Sections stay
`drafted` until a tech lead reviews them and sets `verified_at` to the commit they checked.
Nothing in this folder may cite or summarise `../.answers/`.
