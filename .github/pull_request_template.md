## What and why
<!-- one paragraph; link the tracker question (Q), open question (OQ), SDD section or issue -->

## Checklist
- [ ] PR title follows Conventional Commits (DEV-01 §2.4); breaking changes marked with `!`
- [ ] Tests added or updated; `required` CI job green (TST-01 §6)
- [ ] Coverage not lower than the targets (TST-01 §8)
- [ ] ruff, mypy, eslint, prettier clean (`make lint`)
- [ ] Schemas changed? Fixtures updated; version bumped if breaking (Doc 3 §9.2)
- [ ] New or changed error code? Added to the registry §2 and Doc 4 §5.2 in this PR
- [ ] New or changed event type? Added to Doc 5 §5.3 / SDD-08 and `schemas/events/` in this PR
- [ ] Skill or workflow changed? `tsl validate` passes; new signed eval record; version bumped (R-10)
- [ ] Plugin or `tsl` version changed? Both equal (SDD-05 §7.1)
- [ ] Docs updated where behaviour changed; deviation from Doc 3 or Doc 5 has an ADR; `docs/planning/traceability.md` updated if a deliverable changed status
- [ ] No client names, customer data, client code or credentials anywhere, including fixtures, evals and screenshots (C-09)
- [ ] No secrets in code or config; nothing read from `.env` committed
- [ ] No writes to Jira, Confluence or client systems added without an approval step (R-14)
- [ ] Auth uses company SSO libraries only (MSAL / Entra ID); no bypass flags or hidden endpoints
- [ ] Any rule conflict found is flagged in this PR description, not worked around (R-17)
