# 0003 · Repository is the source of truth

- **Status:** Accepted
- **Date:** 2026-10-12
- **Deciders:** Puneet Singh Nanda
- **Related:** GOV-01, all docs

## Context
Design documents were first written as Claude Docs; code was planned for GitHub. Two sources drift.

## Decision
Every document moves to markdown under docs/ in this repository and changes only by pull request. Each Claude Doc gets a 'Moved to repo: <path>' banner and is no longer edited.

## Consequences
Reviews happen on PRs. Cross-links are repo-relative paths.
