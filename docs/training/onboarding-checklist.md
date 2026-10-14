# Engineer onboarding checklist

| Field | Value |
| --- | --- |
| Status | Draft for owner review |
| Owner | TBD by Puneet (SDD-13 owner) |
| Approver | Puneet Singh Nanda |
| Source | [SDD-13 §3](../design/SDD-13-onboarding-admin.md#3-engineer-onboarding), §4.1 |

Copy this list into the access request (SDD-13 §3.2) and tick each line. The order matters: a later line depends on the earlier ones.

## 1. Before day one (manager and admins)

| # | Item | Done by | Check |
| --- | --- | --- | --- |
| 1 | Company-managed laptop: macOS, or Windows used natively (not WSL); full-disk encryption on | IT | IT asset record |
| 2 | Company Entra account with MFA | IT | Sign-in works |
| 3 | Entra group `TSL-Engineers` (or `TSL-TechLeads`, `TSL-Business`) | Entra app admin | `tsl login` gives no E-AUTH-08 |
| 4 | Company Claude seat with Claude Code; signed in with the company account, never a personal one | Claude org admin | Desktop app shows the org |
| 5 | GitHub org membership with a working push credential | GitHub org admin | `git ls-remote` on the training companion repo |
| 6 | Grant `engineer@SYS-SMP` for training only | Insights admin | Portal admin view |
| 7 | Network path to the insights service (intranet or VPN) | IT | `tsl doctor` check `service` |

## 2. Day one (engineer)

| # | Item | Reference | Check |
| --- | --- | --- | --- |
| 8 | Install Python 3.12 tooling: `uv`, git 2.40 or later, Docker running | SDD-13 §3.1 P-07 | `tsl doctor` |
| 9 | Download the `tsl` wheel and `SHA256SUMS` from the release; compare the hash **before** installing; `uv tool install` | SDD-13 §3.3 | `tsl --version` equals the plugin version |
| 10 | Open a Local session in the desktop app; type `/truminds:status` | SDD-13 §3.4 | A reply from `tsl`, even "no runs" |
| 11 | In a terminal you opened yourself: `tsl login` | SDD-13 §3.5 | "Logged in as eng-…", key registered |
| 12 | `tsl doctor` | SDD-13 §3.6 | Every check `pass` (warn allowed for `key` near expiry and `outbox`) |
| 13 | Self-study E1 (portal "How it works") | [engineer.md](engineer.md) | — |
| 14 | Hands-on session E3 | [hands-on-session.md](hands-on-session.md) | A signed check record on `SYS-SMP` made with your key |
| 15 | Module E4 (pauses, PR evidence, rules) | [engineer.md](engineer.md) | Attendance |

## 3. After training (tech lead and admins)

| # | Item | Done by | Check |
| --- | --- | --- | --- |
| 16 | Request `engineer@<system>` for client work, only after line 14 is evidenced (proposal OI-13-07) | Tech lead asks, insights admin grants | Portal admin view and GitHub team |
| 17 | Tech leads only: path T1–T2 | [tech-lead.md](tech-lead.md) | Signed approval block and re-signed training pack |
| 18 | Skill authors only: path A1–A2 | [skill-author.md](skill-author.md) | Signed eval result for an existing skill |

## Done criteria

- A new engineer reaches line 15 on a clean macOS and a clean native Windows laptop using only this list and SDD-13 §3 (SDD-13 §12).

## Open items

| Id | Item | Owner |
| --- | --- | --- |
| OI-13-07 | Require training evidence before any grant on a client system | Puneet Singh Nanda |
| OI-13-12 | Docker Desktop licensing on company laptops | TBD by Puneet |
| OI-13-13 | Full-disk encryption mandatory on engineer laptops | TBD by Puneet |
