---
schema: stories.v1
run_id: run_01JB2C3D4E5F6G7H8J9KMNPQRS
step: split
attempt: 1
skill: story-split@1.0.0
inputs:
- path: artifacts/ABC-541/run_01JB2C3D4E5F6G7H8J9KMNPQRS/req.md
  sha256: 893d16a4607f9e0626c2bc4e9488938414d3e4fdc5e7added9a1762b86fc42bc
pack_sha:
  sample-support: dd7451d071e14a98e94dcda356497ae4e43bbed0
claims: []
trace:
- REQ-1
- REQ-2
- REQ-3
known:
- S-1
- S-2
- S-3
assumed: []
unknown: []
stories:
- id: S-1
  title: Timer stops on first reply
  trace:
  - REQ-1
  acceptance_criteria:
  - id: AC1
    text: Given a reply, when it is saved, then the timer stops
- id: S-2
  title: Breach flag
  trace:
  - REQ-2
  acceptance_criteria:
  - id: AC1
    text: Given 2 hours without reply, when the queue opens, then a flag shows
- id: S-3
  title: Monthly p95
  trace:
  - REQ-3
  acceptance_criteria:
  - id: AC1
    text: Given a month, when the report runs, then p95 first response shows
---
# Stories: ABC-541

## Stories
- S-1 Timer stops on first reply (traces REQ-1)
- S-2 Breach flag (traces REQ-2)
- S-3 Monthly p95 (traces REQ-3)

## Known
- All stories trace to known requirements.

## Assumed
- None.

## Unknown
- None.
