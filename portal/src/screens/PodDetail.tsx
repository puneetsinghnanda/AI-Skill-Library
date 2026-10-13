import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { usePod, usePodFit, usePodMetrics, usePodRuns } from '../api/queries';
import type { PodDetail as Pod, PodMetrics } from '../api/types';
import { useView } from '../app/ViewContext';
import { CodeChip } from '../components/CodeChip';
import { PageTitle } from '../components/Heading';
import { BlockIcon } from '../components/Icons';
import { EmptyState, ErrorState, Section, Skeleton } from '../components/States';
import { Badge, StatusBadge } from '../components/StatusBadge';
import { TableRegion } from '../components/TableRegion';
import { WorkflowStrip } from '../components/WorkflowStrip';
import { pilotHref } from '../config/env';
import { runCommand } from '../content/commands';
import { POD_KIND } from '../content/labels';
import { percent, shortRunId } from '../lib/format';
import { fitStatus, podStatus, runStatus } from '../lib/status';

function TrackRecord({ m }: { m: PodMetrics }) {
  if (m.status === 'no_data') {
    return (
      <>
        <p className="stat-value nodata m-0">No data yet</p>
        <p className="m-0 small text-2">A track record appears after 5 completed runs.</p>
      </>
    );
  }
  return (
    <>
      <p className="m-0 tone-pass" style={{ fontSize: 32, fontWeight: 700 }}>
        {percent(m.first_try_pass) ?? 'No data yet'}
      </p>
      <p className="m-0 small text-2">
        first-try pass across {m.systems_served} {m.systems_served === 1 ? 'system' : 'systems'} ·{' '}
        {m.prs_merged} PRs merged
      </p>
    </>
  );
}

function FitCheck({ pod }: { pod: Pod }) {
  const { me } = useView();
  const systems = me.scope.projects.flatMap((p) => p.systems.map((s) => s.code));
  const [system, setSystem] = useState('');
  const fit = usePodFit(pod.id, system);
  return (
    <div className="tm-card stack gap-12 mt-16">
      <h3 className="h3 sm">Fit check for a system</h3>
      <label className="field">
        System
        <select value={system} onChange={(e) => setSystem(e.target.value)}>
          <option value="">Choose a system</option>
          {systems.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </label>
      {system === '' ? (
        <p className="body text-2 m-0">Pick one of your systems to check what this pod needs.</p>
      ) : (
        <Section query={fit} skeleton={<Skeleton height={80} />}>
          {(f) =>
            f.data.checks.length === 0 ? (
              <p className="body text-2 m-0">This pod declares no requirements.</p>
            ) : (
              <ul className="plain-list stack gap-8">
                {f.data.checks.map((c) => (
                  <li key={c.key} className="row between gap-8 inset">
                    <span className="body">
                      <span className="mono">{c.key}</span> · {c.detail}
                    </span>
                    <StatusBadge status={fitStatus(c.status)} />
                  </li>
                ))}
              </ul>
            )
          }
        </Section>
      )}
    </div>
  );
}

/** Pod detail (board PodDetail; SDD-09 §4.10). */
export default function PodDetail() {
  const { podId = '' } = useParams();
  const { view } = useView();
  const eng = view === 'engineer';
  const pod = usePod(podId);
  const metrics = usePodMetrics(podId, 'all', !eng);
  const runs = usePodRuns(podId, { status: 'open' }, eng);

  if (pod.isPending) {
    return (
      <div className="tm-wrap pt-32 stack gap-24">
        <PageTitle title="Pod">Pod</PageTitle>
        <Skeleton height={200} />
      </div>
    );
  }
  if (pod.isError) {
    return (
      <div className="tm-wrap pt-32 pb-56 stack gap-16">
        <Link className="tm-link self-start" to="/pods">
          ← All pods
        </Link>
        <PageTitle title="Pod">Pod not available</PageTitle>
        <ErrorState error={pod.error} />
      </div>
    );
  }
  const p = pod.data.data;
  const workflow = p.workflows?.[0] ?? null;
  const pilot = pilotHref(`Request a pilot: ${p.title}`);

  return (
    <div className="pb-56">
      <section className="band-primary on-primary">
        <div className="tm-wrap stack gap-14" style={{ paddingTop: 32, paddingBottom: 44 }}>
          <Link className="tm-link self-start" to="/pods">
            ← All pods
          </Link>
          <div className="row between align-end gap-20">
            <div style={{ flex: '1 1 560px', minWidth: 0 }}>
              <div className="row gap-8">
                <span className="tm-badge b-on-primary">{POD_KIND[p.kind] ?? p.kind}</span>
                <StatusBadge status={podStatus(p.status)} />
              </div>
              <PageTitle title={p.title} className="page-h1 mt-12">
                {p.title}
              </PageTitle>
              {p.summary ? (
                <p className="hero-lead mt-12" style={{ fontSize: 16, maxWidth: 760 }}>
                  {p.summary}
                </p>
              ) : null}
            </div>
            <div className="row gap-10">
              {eng ? (
                <CodeChip code={runCommand(workflow)} onDark />
              ) : (
                <>
                  <Link className="tm-btn btn-light" to={`/pods/${p.id}/one-pager`}>
                    Download one-pager
                  </Link>
                  {pilot ? (
                    <a className="tm-btn btn-accent" href={pilot}>
                      Request a pilot
                    </a>
                  ) : null}
                </>
              )}
            </div>
          </div>
        </div>
      </section>

      <section className="tm-wrap pt-32">
        <h2 className="h2-md">Who is in the pod</h2>
        <div className="grid g-280 mt-16">
          {p.agents.map((a) => (
            <div className="tm-card stack gap-10" key={a.key}>
              <div className="row gap-12" style={{ flexWrap: 'nowrap' }}>
                <span className="tm-icon navy" aria-hidden="true">
                  {a.code}
                </span>
                <div>
                  <h3 className="m-0" style={{ fontSize: 16 }}>
                    {a.display_name}
                  </h3>
                  <p className="m-0 xsmall text-2">AI · runs in Claude Code</p>
                </div>
              </div>
              {a.job ? <p className="body text-2 m-0">{a.job}</p> : null}
              {eng && a.skills?.length ? (
                <div className="row gap-6">
                  {a.skills.map((s) => (
                    <Badge key={s} tone="teal" mono>
                      {s}
                    </Badge>
                  ))}
                </div>
              ) : null}
            </div>
          ))}
          <div className="tm-card soft stack gap-10">
            <div className="row gap-12" style={{ flexWrap: 'nowrap' }}>
              <span className="tm-icon white">
                <BlockIcon kind="person" />
              </span>
              <div>
                <h3 className="m-0" style={{ fontSize: 16 }}>
                  People accountable
                </h3>
                <p className="m-0 xsmall text-2">Make every decision</p>
              </div>
            </div>
            {p.people_accountable.length ? (
              <ul className="list" style={{ color: 'var(--tm-text)' }}>
                {p.people_accountable.map((x) => (
                  <li key={x.role ?? x.decides.join()}>
                    {x.role}
                    {x.decides.length ? `: ${x.decides.join(', ')}` : ''}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="body m-0">Not listed yet.</p>
            )}
          </div>
        </div>
      </section>

      <section className="tm-wrap pt-36">
        <h2 className="h2-md">How the pod works</h2>
        <p className="tm-sub">
          {workflow ? `The ${workflow} workflow. ` : ''}Dashed amber boxes are human gates; every
          other box is checked by the harness.
        </p>
        {p.flow.length ? (
          <WorkflowStrip flow={p.flow} showIds={eng} />
        ) : (
          <p className="body text-2">The workflow for this pod is not published yet.</p>
        )}
      </section>

      {eng ? (
        <section className="tm-wrap pt-36">
          <h2 className="h2-md">Active runs of this pod</h2>
          <div className="mt-16">
            <Section query={runs} skeleton={<Skeleton height={160} />}>
              {(r) =>
                r.data.items.length === 0 ? (
                  <EmptyState title="No active runs of this pod in your systems">
                    Start one in Claude Code with the command above.
                  </EmptyState>
                ) : (
                  <TableRegion label="Active runs of this pod" minWidth={720}>
                    <thead>
                      <tr>
                        <th scope="col">Run</th>
                        <th scope="col">System</th>
                        <th scope="col">Ticket</th>
                        <th scope="col">Step</th>
                        <th scope="col">Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {r.data.items.map((x) => (
                        <tr key={x.run_id}>
                          <td>
                            <Link
                              className="tm-link mono"
                              style={{ fontSize: 13 }}
                              to={`/runs/${x.run_id}`}
                              title={x.run_id}
                            >
                              {shortRunId(x.run_id)}
                            </Link>
                          </td>
                          <td className="mono">{x.system ?? '—'}</td>
                          <td>{x.ticket_ref ?? '—'}</td>
                          <td>
                            {x.current_step
                              ? `${x.current_step.step_id}${
                                  x.current_step.position && x.current_step.step_count
                                    ? ` (${x.current_step.position} of ${x.current_step.step_count})`
                                    : ''
                                }`
                              : '—'}
                          </td>
                          <td>
                            <StatusBadge status={runStatus(x.status_label)} />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </TableRegion>
                )
              }
            </Section>
          </div>
          <FitCheck pod={p} />
        </section>
      ) : (
        <section className="tm-wrap pt-36 grid g-320">
          <div className="tm-card stack gap-10">
            <h2 className="h3">What the client gets</h2>
            {p.client_gets.length ? (
              <ul className="list">
                {p.client_gets.map((x) => (
                  <li key={x}>{x}</li>
                ))}
              </ul>
            ) : (
              <p className="body text-2 m-0">Not written yet.</p>
            )}
          </div>
          <div className="tm-card stack gap-10">
            <h2 className="h3">Good fit when</h2>
            {p.good_fit.length ? (
              <ul className="list">
                {p.good_fit.map((x) => (
                  <li key={x}>{x}</li>
                ))}
              </ul>
            ) : (
              <p className="body text-2 m-0">Not written yet.</p>
            )}
            {p.not_a_fit.length ? (
              <>
                <h3 className="m-0 small strong">Not a fit when</h3>
                <ul className="list">
                  {p.not_a_fit.map((x) => (
                    <li key={x}>{x}</li>
                  ))}
                </ul>
              </>
            ) : null}
          </div>
          <div className="tm-card stack gap-10">
            <h2 className="h3">Track record</h2>
            <Section query={metrics} skeleton={<Skeleton height={80} />}>
              {(m) => <TrackRecord m={m.data} />}
            </Section>
          </div>
        </section>
      )}
    </div>
  );
}
