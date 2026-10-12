# Web UI prototype

High-fidelity interactive prototype of the intranet portal, two personas (Business unit, Engineers), 15 screens. Built as a Design canvas (`*.dc.html` + `canvas.json` + `brand.css`). Brand tokens in `brand.css` are placeholders to swap for the official Truminds brand.

Hosted copy (view only): https://claude.ai/artifact/7y1Mw9PAieVcAisJroQkbn

| Screen | File |
| --- | --- |
| Shell and router | Main.dc.html, Nav.dc.html |
| Home (Business / Engineer) | HomeBusiness.dc.html, HomeEngineer.dc.html |
| How it works | HowItWorks.dc.html |
| Skills / Skill detail | Skills.dc.html, SkillDetail.dc.html |
| Get started | GetStarted.dc.html |
| Pods / Pod detail / Pod builder (Phase 3 preview) | Pods.dc.html, PodDetail.dc.html, PodBuilder.dc.html |
| Insights (Business / Engineer) | InsightsBusiness.dc.html, InsightsEngineer.dc.html |
| Run detail | RunDetail.dc.html |
| Persona map | PersonaMap.dc.html |

The files reference `support.js`, the canvas runtime that the hosted copy supplies. To view locally, open the hosted copy; the production portal is built in `portal/` (SDD-09) from these screens. All data shown is illustrative.
