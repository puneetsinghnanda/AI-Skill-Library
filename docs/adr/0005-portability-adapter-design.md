# 0005 · Portability adapter design (not built in Release 1)

- **Status:** Proposed
- **Date:** set when Puneet decides
- **Deciders:** Puneet Singh Nanda (approver)
- **Related:** tracker Q15, Doc 3 §11 and NFR-12, Doc 6 C-03, SDD-01 O-01, SDD-05, PLN-01 §2.2 (Phase 3)

## Context

Release 1 runs only in Claude Code on company Claude seats (C-03, D-10). Tracker Q15 asks that the Release-1 code not close the door to other AI coding tools. What is portable and what is not, from the design as built:

| Part | Portable today? | Why |
| --- | --- | --- |
| Skill content (`SKILL.md`, `skill.yaml`, rubric, evals) | Mostly | Agent Skills standard. One exception: the `` !`tsl verify --inputs` `` preamble is Claude Code syntax (SDD-01 O-01, NFR-12) |
| `tsl` (state, next, verify, decide, sign, pr, ci-verify) | Yes | Plain Python, no model inside; any tool that can run a shell command can call it |
| Schemas, insights service, portal, CI verify | Yes | No model dependency |
| Plugin and marketplace format, `/truminds:*` commands | No | Claude Code packaging (SDD-05 §3–§4) |
| Hooks and their stdin/stdout | No | Claude Code hook events (SDD-05 §5) |
| Reviewer subagent | No | Claude Code subagent with `context: fork` (SDD-05 §4.3) |
| Session telemetry | No | Claude Code OpenTelemetry export (SDD-08 §5) |

## Options considered

| Option | Pros | Cons |
| --- | --- | --- |
| A. Do nothing now | No work | Release-1 code may grow Claude-only assumptions inside `tsl` |
| B. Keep a thin adapter seam now, build adapters later | Small cost; keeps `tsl` tool-neutral | Discipline needed in reviews |
| C. Build a second adapter in Release 1 | Proves portability | Out of scope (C-03); weaker enforcement where a tool lacks hooks |

## Decision (proposed)

Option B. Treat Claude Code as one **adapter** around a tool-neutral core:

1. **Core stays neutral.** `tsl` reads only its own inputs (`tsl hook <event>` already normalises hook stdin; SDD-04 §6.14). New Claude-specific fields are mapped in `tsl/src/tsl/hooks/dispatch.py` and nowhere else.
2. **Adapter contract.** An adapter for another tool must provide: (a) a way to start and resume a run that calls `tsl state` and `tsl next`; (b) a pre-tool check that calls `tsl hook pre-tool` and honours exit 2 as deny; (c) a post-write call to `tsl verify`; (d) a reviewer that writes `review.v1` JSON through `tsl review record`; (e) session start and end calls for the outbox.
3. **Where a tool lacks hooks**, enforcement moves to CI: `tsl ci-verify` stays required on product repos, so a missing record still blocks the merge (E-CI-01).
4. **Skill bodies.** The input-check preamble is the only allowed Claude-only line (SDD-01 O-01); an adapter strips or replaces it.
5. **Telemetry.** Events from `tsl` are tool-neutral. Token and cost metrics come only from tools that export them; the portal shows "not reported" otherwise.

Nothing is built for another tool in Release 1. The design is revisited in Phase 3 (PLN-01 §2.2).

## Consequences

- Code review rule: no Claude-specific field names outside `tsl/src/tsl/hooks/` and `plugins/truminds/`.
- SDD-01 O-01 is resolved by this ADR when accepted.
- An adapter for a named tool needs its own ADR, with that tool's hook and extension facts checked against its current documentation first.
