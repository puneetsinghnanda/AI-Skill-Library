import { Link, useSearchParams } from 'react-router-dom';
import { useBusiness, useCapabilityMap } from '../api/queries';
import { CapabilityMapTable } from '../components/CapabilityMapTable';
import { BarChart, HBars } from '../components/Charts';
import { PageTitle } from '../components/Heading';
import { StatTile } from '../components/StatTile';
import { EmptyState, Section, Skeleton, SkeletonGrid } from '../components/States';
import { count, monthLabel, percent } from '../lib/format';

const PERIODS = [
  { id: '90d', label: 'Last 90 days' },
  { id: '12m', label: 'Last 12 months' },
  { id: 'all', label: 'All time' },
] as const;

function changeText(change: number | null): { text: string; up: boolean } {
  if (change === null) return { text: 'no previous period to compare', up: false };
  if (change > 0) return { text: `+${change} vs previous period`, up: true };
  if (change < 0) return { text: `${change} vs previous period`, up: false };
  return { text: 'same as previous period', up: false };
}

/** Insights: Business impact (board InsightsBusiness; SDD-09 §4.12). Class A data only. */
export default function InsightsBusiness() {
  const [params, setParams] = useSearchParams();
  const raw = params.get('period');
  const period = PERIODS.some((p) => p.id === raw) ? (raw as string) : '90d';
  const business = useBusiness(period);
  const map = useCapabilityMap('internal');

  return (
    <div className="pb-56">
      <section className="band-surface">
        <div
          className="tm-wrap row between align-end gap-16"
          style={{ paddingTop: 36, paddingBottom: 24 }}
        >
          <div>
            <p className="tm-eyebrow">Insights · Business</p>
            <PageTitle title="Insights">Impact and capability</PageTitle>
            <p className="tm-sub">
              Sales-safe numbers: aggregates only, no client names, tickets or repositories.
            </p>
          </div>
          <div className="row gap-10">
            <label className="field">
              Period
              <select
                value={period}
                onChange={(e) => {
                  const next = new URLSearchParams(params);
                  next.set('period', e.target.value);
                  setParams(next, { replace: true });
                }}
              >
                {PERIODS.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.label}
                  </option>
                ))}
              </select>
            </label>
            <Link className="tm-btn btn-primary" to="/insights/capability-map/share">
              Share capability map
            </Link>
          </div>
        </div>
      </section>

      <section className="tm-wrap pt-24">
        <Section query={business} skeleton={<SkeletonGrid count={5} />}>
          {(b) => {
            const d = b.data;
            const ch = changeText(d.prs_delivered.change);
            const bars = d.prs_by_month.map((m) => ({
              label: monthLabel(m.month).short,
              longLabel: monthLabel(m.month).long,
              value: m.merged,
            }));
            return (
              <>
                <div className="grid g-200">
                  <StatTile
                    label="Pull requests delivered"
                    value={count(d.prs_delivered.value)}
                    sub={<span className={ch.up ? 'tone-pass strong' : ''}>{ch.text}</span>}
                  />
                  <StatTile
                    label="First-try pass rate"
                    value={percent(d.first_try_pass.value)}
                    tone="pass"
                    sub="all steps, all skills"
                  />
                  <StatTile
                    label="Client systems served"
                    value={count(d.systems_served.value)}
                    sub={`across ${d.systems_served.domains} ${d.systems_served.domains === 1 ? 'domain' : 'domains'}`}
                  />
                  <StatTile
                    label="Engineers using the library"
                    value={count(d.engineers_using.value)}
                    sub="ran at least one workflow"
                  />
                  <StatTile
                    label="Active pods"
                    value={count(d.active_pods.value)}
                    sub="on live engagements"
                  />
                </div>
                <div className="row align-start gap-20 mt-20">
                  <div
                    className="tm-card stack gap-14"
                    style={{ flex: '999 1 560px', minWidth: 0 }}
                  >
                    <div>
                      <h2 className="h3">Pull requests delivered per month</h2>
                      <p className="small text-2" style={{ margin: '4px 0 0' }}>
                        Merged by people after passing every check
                      </p>
                    </div>
                    {bars.length === 0 || bars.every((x) => x.value === 0) ? (
                      <p className="stat-value nodata m-0">No data yet</p>
                    ) : (
                      <BarChart title="Pull requests per month" data={bars} />
                    )}
                  </div>
                  <div className="tm-card stack gap-12" style={{ flex: '1 1 320px', minWidth: 0 }}>
                    <h2 className="h3">Most-used pods</h2>
                    {d.most_used_pods.length === 0 ? (
                      <p className="body text-2 m-0">
                        No data yet. Pods show here once they are used on engagements.
                      </p>
                    ) : (
                      <HBars
                        label="Most-used pods, by engagements"
                        fill="fill-accent"
                        items={d.most_used_pods.map((p) => ({
                          label: p.title,
                          value: p.engagements,
                        }))}
                      />
                    )}
                  </div>
                </div>
              </>
            );
          }}
        </Section>
      </section>

      <section className="tm-wrap pt-32">
        <h2 className="tm-h2">Capability map</h2>
        <p className="tm-sub">Production skills by role and SDLC phase. Safe to show clients.</p>
        <div className="mt-16">
          <Section query={map} skeleton={<Skeleton height={360} />}>
            {(m) =>
              m.data.rows.length === 0 ? (
                <EmptyState title="No skills on the map yet">
                  Skills appear after the next catalogue release.
                </EmptyState>
              ) : (
                <CapabilityMapTable map={m.data} />
              )
            }
          </Section>
        </div>
        <p className="xsmall text-2" style={{ margin: '10px 0 0' }}>
          Pilot skills are shown to internal viewers only; the shared map hides them. A check mark
          means the skill has evidence from at least 5 real steps.
        </p>
      </section>
    </div>
  );
}
