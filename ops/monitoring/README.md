# Monitoring as code (OPS-02)

These files define the alert rules, SLI recording rules, dashboards and synthetic checks for the insights service and the portal. They are tool-neutral: rules use Prometheus rule format and dashboards use Grafana JSON. The scraper, alert router, pager and prober products follow the hosting choice (OPS-01, OQ-02).

| File | Content | OPS-02 |
| --- | --- | --- |
| `alerts.yaml` | AL-01..AL-26 (27 rules: AL-26 has a fast and a slow burn rule), each with severity, dashboard and runbook anchor | §7 |
| `alerts.test.yaml` | promtool unit tests: a firing and a quiet case for every alert (58 cases) | §11, §12 |
| `recording.yaml` | SLI recording rules (SLO-1, SLO-2, SLO-5, SLO-6), burn-rate ratios and the working-hours gate | §3.2 |
| `dashboards/DSH-1.json` … `DSH-6.json` | Service overview, Ingest pipeline, Read API and portal, Database, Fleet and outbox, Security signals | §9 |
| `synthetic/probe.yaml` | SY-1..SY-5 as blackbox_exporter modules | §4.3 |
| `scrape.yaml` | Scrape jobs for api (9100), worker (9101), node, synthetic | §2, §4.1 |
| `tests/test_monitoring.py` | Ids match the registry, every metric exists in `app/obs/metrics.py` or is a known external series, dashboards present, promtool | §12 |

Ids follow the registry, which wins over older spellings:

- Alerts are `AL-nn`, renamed from `A-nn` by registry §10 #29.
- Dashboards are `DSH-n`, renamed from `D-n` by registry §10 #33.
- SLOs are `SLO-n`.

Alert names are `<id>_<Name>`, for example `AL-08_ProjectionLagCritical`. Alert text holds counts and durations only.

## Check

```bash
promtool check rules recording.yaml alerts.yaml
promtool test rules alerts.test.yaml            # about 2 minutes (AL-22 needs 8 days of series)
promtool check config scrape.yaml
blackbox_exporter --config.check --config.file=synthetic/probe.yaml
# from the repository root, with the insights venv:
PROMTOOL=$(which promtool) PROMTOOL_UNIT=1 services/insights/.venv/bin/python -m pytest ops/monitoring/tests
```

## Settings to confirm (OPS-02 §15)

- **Working hours** for P2 paging and AL-09 are TBD by Puneet. `recording.yaml` → `ops:working_hours` holds the placeholder, Monday–Friday 09:00–18:00 UTC.
- **AL-13 and AL-14** read `node_filesystem_*` for the encrypted pgdata volume under option H1. Under H3, swap in the provider's storage metric.
- **SY-4** stays off until a monitoring identity with a `viewer` grant exists.
- **DSH-5 "plugin and tsl versions"** is a placeholder text panel, because OPS-02 §5.2 defines no metric for it.
- **Runbook links** point to `docs/operations/OPS-04-failure-runbook.md#al-nn`, as OPS-02 §13 requires. OPS-04 §4.13 holds one anchor per alert; `test_runbook_anchors_exist_in_ops_04` keeps them in step.
