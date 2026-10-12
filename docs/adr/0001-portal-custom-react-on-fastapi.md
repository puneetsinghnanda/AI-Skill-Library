# 0001 · Portal is a custom React web app on the FastAPI insights service

- **Status:** Accepted
- **Date:** 2026-10-12
- **Deciders:** Puneet Singh Nanda
- **Related:** OQ-15, SDD-09, Doc 4 §2.0

## Context
The portal needs two persona views (Business unit, Engineers) on a private intranet, reading data that the insights service already holds. Backstage was considered as a host.

## Decision
Build a custom React single-page app served on the intranet, calling the FastAPI insights service read API. Backstage is dropped and OQ-15 is closed.

## Consequences
One stack (FastAPI + PostgreSQL 16 + React) to run. No Backstage plugin model. SDD-09 owns the read API and screens.
