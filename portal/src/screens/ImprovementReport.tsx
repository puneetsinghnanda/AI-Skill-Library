import { Link, useParams } from 'react-router-dom';
import { useImprovement } from '../api/queries';
import { PageTitle } from '../components/Heading';
import { StatTile } from '../components/StatTile';
import { EmptyState, ErrorState, Skeleton } from '../components/States';
import { Badge, StatusBadge } from '../components/StatusBadge';
import { TableRegion } from '../components/TableRegion';
import { count, decimal, localDate, percent, shortRunId } from '../lib/format';
import { flagStatus } from '../lib/status';

function val(v: number | null | undefined): string {
  if (v === null || v === undefined) return '—';
  return v <= 1 ? (percent(v, 1) ?? '—') : (decimal(v, 2) ?? '—');
}

/**
 * Improvement report (SDD-11 §4.4, §5.4): Insights > Engineering > Skill performance. Visible to the
 * skill owner, eng leads and admins; the server enforces it. Flag status changes stay in
 * `tsl improve plan --flag` (the portal is read-only, SDD-09 §1.3).
 */
export default function ImprovementReport() {
  const { skillId = '' } = useParams();
  const report = useImprovement(skillId);
  return (
    <div className="pb-56">
      <section className="band-surface">
        <div className="tm-wrap stack gap-12" style={{ paddingTop: 28, paddingBottom: 24 }}>
          <Link className="tm-link self-start" to="/insights/engineering/skills">
            ← Skill performance
          </Link>
          <p className="tm-eyebrow">Improvement report</p>
          <PageTitle title={`Improvement report ${skillId}`} className="page-h1 mono">
            {skillId}
          </PageTitle>
        </div>
      </section>
      <section className="tm-wrap pt-24 stack gap-20">
        {report.isPending ? (
          <Skeleton height={300} />
        ) : report.isError ? (
          <ErrorState error={report.error} />
        ) : (
          (() => {
            const r = report.data.data;
            return (
              <>
                <div className="grid g-200">
                  <StatTile
                    label="Version"
                    value={r.header.version}
                    sub={r.header.owner_pseudonym ? `owner ${r.header.owner_pseudonym}` : undefined}
                  />
                  <StatTile
                    label="Window"
                    value={`${r.header.window_days} days`}
                    sub={`ending ${localDate(r.header.window_end) ?? r.header.window_end}`}
                  />
                  <StatTile
                    label="Samples"
                    value={count(r.header.samples.steps)}
                    sub={`steps · ${r.header.samples.first_attempts} first attempts`}
                  />
                  <StatTile
                    label="Signed eval pass rate"
                    value={percent(r.header.eval_pass_rate)}
                  />
                </div>

                <div className="stack gap-8">
                  <h2 className="h2-sm">Flags</h2>
                  {r.flags.length === 0 ? (
                    <p className="body text-2 m-0">No flags for this skill.</p>
                  ) : (
                    <TableRegion label="Flags" minWidth={720}>
                      <thead>
                        <tr>
                          <th scope="col">Signal</th>
                          <th scope="col">Version</th>
                          <th scope="col">Value</th>
                          <th scope="col">Threshold</th>
                          <th scope="col">Sample</th>
                          <th scope="col">Status</th>
                          <th scope="col">Opened</th>
                        </tr>
                      </thead>
                      <tbody>
                        {r.flags.map((f) => (
                          <tr key={f.flag_id}>
                            <td className="mono">{f.signal}</td>
                            <td className="mono">{f.skill_version}</td>
                            <td>{val(f.value)}</td>
                            <td>{val(f.threshold)}</td>
                            <td>{f.sample}</td>
                            <td>
                              <StatusBadge status={flagStatus(f.status)} />
                            </td>
                            <td>{localDate(f.opened_at) ?? '—'}</td>
                          </tr>
                        ))}
                      </tbody>
                    </TableRegion>
                  )}
                  <p className="m-0 xsmall text-2">
                    Start work on a flag with{' '}
                    <code className="mono">tsl improve plan {skillId}</code>, or dismiss it there
                    with a reason.
                  </p>
                </div>

                <div className="stack gap-8">
                  <h2 className="h2-sm">Signals this window</h2>
                  <TableRegion label="Signals this window" minWidth={560}>
                    <thead>
                      <tr>
                        <th scope="col">Signal</th>
                        <th scope="col">Value</th>
                        <th scope="col">Threshold</th>
                        <th scope="col">Sample</th>
                      </tr>
                    </thead>
                    <tbody>
                      {r.signals.map((s) => (
                        <tr key={s.signal}>
                          <td className="mono">{s.signal}</td>
                          <td>{s.enough_data ? val(s.value) : 'Not enough data'}</td>
                          <td>{val(s.threshold)}</td>
                          <td>{s.sample}</td>
                        </tr>
                      ))}
                    </tbody>
                  </TableRegion>
                  {r.not_computed.length ? (
                    <p className="m-0 xsmall text-2">
                      Not computed yet: {r.not_computed.join(', ')}.
                    </p>
                  ) : null}
                </div>

                <div className="stack gap-8">
                  <h2 className="h2-sm">Failure clusters</h2>
                  {r.clusters.length === 0 ? (
                    <EmptyState title="No failed steps in this window" />
                  ) : (
                    r.clusters.map((c) => (
                      <div className="tm-card stack gap-8" key={c.signature}>
                        <div className="row between gap-8">
                          <span className="mono strong">{c.signature}</span>
                          <Badge tone="retry">
                            {c.count} steps{c.share !== null ? ` · ${percent(c.share)}` : ''}
                          </Badge>
                        </div>
                        <p className="m-0 small text-2">
                          Workflows: {c.workflows.join(', ') || '—'} · positions{' '}
                          {c.positions.join(', ') || '—'}
                        </p>
                        <ul className="plain-list row gap-8">
                          {c.references.map((ref) => (
                            <li key={`${ref.run_id}-${ref.step}-${ref.attempt}`} className="small">
                              <Link to={`/runs/${ref.run_id}`} title={ref.run_id}>
                                {shortRunId(ref.run_id)}
                              </Link>{' '}
                              <span className="mono">
                                {ref.system ?? ''} · {ref.step} #{ref.attempt}
                              </span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    ))
                  )}
                </div>

                <div className="grid g-340" style={{ gap: 16 }}>
                  <div className="stack gap-8">
                    <h2 className="h2-sm">Version comparison</h2>
                    <TableRegion label="Version comparison">
                      <thead>
                        <tr>
                          <th scope="col">Signal</th>
                          <th scope="col">Current</th>
                          <th scope="col">Previous</th>
                        </tr>
                      </thead>
                      <tbody>
                        {Object.keys(r.version_comparison.current).map((k) => (
                          <tr key={k}>
                            <td className="mono">{k}</td>
                            <td>{val(r.version_comparison.current[k])}</td>
                            <td>
                              {r.version_comparison.previous
                                ? val(r.version_comparison.previous[k])
                                : '—'}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </TableRegion>
                  </div>
                  <div className="stack gap-8">
                    <h2 className="h2-sm">Improvement history</h2>
                    {r.improvements.length === 0 ? (
                      <p className="body text-2 m-0">No improvements yet.</p>
                    ) : (
                      <TableRegion label="Improvement history">
                        <thead>
                          <tr>
                            <th scope="col">Change</th>
                            <th scope="col">State</th>
                            <th scope="col">Eval before</th>
                            <th scope="col">Eval after</th>
                          </tr>
                        </thead>
                        <tbody>
                          {r.improvements.map((i) => (
                            <tr key={i.improvement_id}>
                              <td className="mono">
                                {i.from_version} → {i.to_version}
                              </td>
                              <td>{i.state}</td>
                              <td>{percent(i.before_pass_rate) ?? '—'}</td>
                              <td>{percent(i.after_pass_rate) ?? '—'}</td>
                            </tr>
                          ))}
                        </tbody>
                      </TableRegion>
                    )}
                  </div>
                </div>
              </>
            );
          })()
        )}
      </section>
    </div>
  );
}
