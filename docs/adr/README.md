# Architecture Decision Records

One file per decision: `NNNN-short-title.md`, numbered in order, never renumbered. Status moves Proposed → Accepted or Rejected → (Superseded by NNNN). Puneet approves every ADR. Process: [GOV-01](../governance/GOV-01-adr-and-change-process.md).

| ADR | Decision | Status |
| --- | --- | --- |
| [0001](0001-portal-custom-react-on-fastapi.md) | Portal is a custom React web app on the FastAPI insights service; Backstage dropped (closes OQ-15) | Accepted |
| [0002](0002-identity-microsoft-entra-id.md) | Identity is Microsoft Entra ID: device-code for `tsl login`, auth code + PKCE for the portal | Accepted |
| [0003](0003-repo-is-source-of-truth.md) | This repository is the source of truth for all documents and code | Accepted |
| [0004](0004-sample-system-react-node.md) | Sample brownfield system is React + Node.js with PostgreSQL | Proposed (tentative) |
| [0005](0005-portability-adapter-design.md) | Portability adapter design: Claude Code is one adapter around a tool-neutral `tsl` core; nothing built for other tools in Release 1 (tracker Q15) | Proposed |
