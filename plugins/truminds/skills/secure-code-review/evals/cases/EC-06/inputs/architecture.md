---
schema: context-section.v1
section: architecture
owner: tl-7a1c
origin: human
status: reviewed
verified_at:
  sample-library: c6d3dfacc5f0a0c8a4581668a0f54ca0976d4928
---
# Architecture {#architecture}

## Components {#components}
The web app calls the api over HTTP. The api owns the loans, members and items tables.
Sources: context/generated/module-map.json#module:sample-library:api/src/loans

## Overdue job {#overdue-job}
A nightly job in api/src/loans marks loans past their due date as overdue.
Sources: context/generated/module-map.json#module:sample-library:api/src/loans

## Authentication {#authentication}
Members sign in with a library card number and a PIN. A member can act only on their own loans.
Sources: sample-library:api/src/auth/member.js#L12
