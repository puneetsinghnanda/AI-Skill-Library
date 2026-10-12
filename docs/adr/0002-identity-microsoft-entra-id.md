# 0002 · Identity is Microsoft Entra ID

- **Status:** Accepted
- **Date:** 2026-10-12
- **Deciders:** Puneet Singh Nanda
- **Related:** SDD-07, SDD-09, org rule on SSO

## Context
Org rule: use company SSO libraries for all authentication; never roll custom auth. Truminds uses Microsoft Entra ID.

## Decision
`tsl login` uses the OIDC device-code flow; the portal uses authorization code with PKCE (MSAL). The insights service validates Entra-issued tokens. Ed25519 signing keys are registered against the Entra identity at `tsl login`.

## Consequences
No local passwords. App registrations and group-to-role mapping are needed from the Entra admin (TBD by Puneet).
