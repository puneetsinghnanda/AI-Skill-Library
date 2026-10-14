# 0006 · Interim GitHub sign-in for the test phase

- **Status:** Accepted
- **Date:** recorded by the merge commit of this ADR
- **Deciders:** Puneet Singh Nanda (decider and approver)
- **Related:** [ADR 0002](0002-identity-microsoft-entra-id.md) (Entra ID, unchanged), [SDD-07 §1.4](../design/SDD-07-identity-signing.md#14-identity-providers), [SDD-08 §9.1](../design/SDD-08-telemetry-insights.md#91-authentication-summary), [SDD-09 §3.4.1](../design/SDD-09-web-portal.md#341-sign-in-with-github-test-phase-only), [TST-02](../testing/TST-02-team-validation-plan.md), [deploy/README.md](../../deploy/README.md), registry §2, §4, §4.1

## Context

- ADR 0002 makes Microsoft Entra ID the only identity provider: device code for `tsl login`, authorization code + PKCE for the portal, app roles from the token.
- The three Entra app registrations (`truminds-insights-api`, `truminds-tsl`, `truminds-portal`) and their app roles are requested from IT and will take days.
- The test phase with six testers (TST-02) must start now. Without a working sign-in nothing can be tested end to end: no `tsl login`, no key registration, no signed decisions, no portal.

**Org rule flagged.** The organisation rule "use company SSO for all authentication" (SDD-07 §1.3, C-05) is not met by GitHub sign-in. This ADR is a deliberate, time-boxed deviation for the **test environment only**. Production uses Entra; nothing here changes the Entra path.

## Options considered

| Option | Pros | Cons |
| --- | --- | --- |
| Wait for the Entra registrations | No deviation | Test phase blocked for days |
| A local test tenant or hand-made JWT issuer | Same code path as production | A home-made identity provider is custom auth (forbidden); a personal tenant is not company SSO either |
| Password login or a bypass flag for testers | Fast | Forbidden: custom auth and a back door |
| **GitHub OAuth (device flow for `tsl`, code flow for the portal), chosen by configuration** | Standard OAuth with established libraries (`httpx`, Starlette signed session); every tester already has a GitHub account; Entra code stays intact; switch back by configuration | Not company SSO; GitHub tokens carry no app roles or scopes; a GitHub outage blocks sign-in |

## Decision

Add GitHub as an **interim** identity provider behind configuration. Default stays `entra`.

- `tsl`: `provider = "github"` in the build-time `_org.toml` (made with `TSL_ORG_FILE`) selects `identity/github.py`, the OAuth device flow with `scope=read:user`. The token is sealed like the MSAL cache.
- Insights service: `IDENTITY_PROVIDER=github` validates a bearer token with `GET /user` (cached five minutes by SHA-256 of the token). The user is `github:<numeric id>`. Roles come only from `role_grants` (admin screens); app roles are derived from the grants.
- First admin: `BOOTSTRAP_ADMIN_GITHUB_LOGINS`, visible, logged at startup and audited per grant. Puneet then adds the six testers through the existing portal admin screens.
- Portal: backend-for-frontend sign-in (`/auth/github/login`, `/auth/github/callback`, `POST /auth/logout`); the token is encrypted inside a signed HttpOnly session cookie; cookie writes need `X-Requested-With: truminds-portal` and a same-origin `Origin`.
- Guard rails: the service refuses `IDENTITY_PROVIDER=github` when `ENV=prod`; `ENVIRONMENT=test` shows a TEST ENVIRONMENT banner. There is no password login, no bypass flag and no hidden endpoint: every new route is in the OpenAPI file and registry §4.

## Exit criterion

Switch to Entra when IT delivers the three app registrations and their app roles:

1. Set `IDENTITY_PROVIDER=entra` and the `ENTRA_*` settings; rebuild `tsl` from the `TSL_ORG_*` variables (provider `entra`); rebuild the portal without `VITE_IDENTITY_PROVIDER=github`.
2. Discard the test environment and its database (GitHub users are separate rows and are not migrated).
3. Revoke the GitHub OAuth App's client secret and delete the app.
4. Mark this ADR "Superseded by ADR 0002 (restored)" in the ADR index.

## Consequences

- Scope and client pairing cannot be expressed with GitHub tokens; it is mapped by credential and route instead (SDD-07 §1.4). This is weaker than Entra's `azp` + `scp` check and is acceptable only for the test phase.
- A `tsl` wheel built for GitHub cannot talk to an Entra service and the reverse; testers reinstall `tsl` at the switch.
- With a plain `http://` test URL, tokens and the session cookie cross the network unencrypted and the cookie cannot be `Secure`. Use HTTPS on the test host when possible.
- Documents updated: SDD-07 §1.4 and §9, SDD-08 §9.1, SDD-09 §3.4.1, registry §2, §4, §4.1, TST-02 Phase C, the traceability matrix.
