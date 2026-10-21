import { useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import {
  useEngHealth,
  useEngRuns,
  useEngSkills,
  useEngUsage,
  useRuns,
  type EngParams,
} from '../api/queries';
import type { RunItem } from '../api/types';
import { canOpenImprovement, useView } from '../app/ViewContext';
import { BandBar, HBars, OutcomeBar } from '../components/Charts';
import { PageTitle } from '../components/Heading';
import { StatTile } from '../components/StatTile';
import { EmptyState, ErrorState, Section, Skeleton, SkeletonGrid } from '../components/States';
import { StatusBadge } from '../components/StatusBadge';
import { Tabs, tabPanelProps } from '../components/Tabs';
import { TableRegion } from '../components/TableRegion';
import { policy } from '../config/policy';
import { ENG_TABS, codeWords, roleList, type EngTab } from '../content/labels';
import {
  compactTokens,
  count,
  daysAgo,
  decimal,
  duration,
  percent,
  relativeTime,
  shortRunId,
  usd,
} from '../lib/format';
import { bandStatus, packStatus, runStatus } from '../lib/status';

const PERIODS = [
  { id: '30d', label: 'Last 30 days' },
  { id: '90d', label: 'Last 90 days' },
] as const;

function engineerName(r: RunItem): string {
  return r.engineer.display_name ?? r.engineer.pseudonym ?? '—';
}

/* ------------------------------------------------------------------ Runs tab */
function RunsTab({ filters, names }: { filters: EngParams; names: boolean }) {
  const stats = useEngRuns(filters);
  const runs = useRuns({
    project: filters.project,
    system: filters.system,
    period: filters.period,
    include: names ? 'names' : undefined,
    limit: 25,
  });
  const items = runs.data?.pages.flatMap((p) => p.data.items) ?? [];
  return (
    <>
      <Section query={stats} skeleton={<SkeletonGrid count={5} />}>
        {(s) => {
          const c = s.data.status_counts;
          return (
            <>
              <div className="grid g-170">
                <StatTile label="Running" value={count(c.running)} />
                <StatTile
                  label="Paused for input"
                  value={count(c.paused_input)}
                  tone={c.paused_input ? 'input' : undefined}
                  sub={
                    s.data.oldest_input_wait_s !== null
                      ? `oldest waiting ${duration(s.data.oldest_input_wait_s)}`
                      : undefined
                  }
                />
                <StatTile
                  label="Waiting for approval"
                  value={count(c.paused_approval)}
                  tone={c.paused_approval ? 'esc' : undefined}
                />
                <StatTile label="Completed" value={count(c.completed)} />
                <StatTile label="Cancelled" value={count(c.cancelled)} />
                <StatTile
                  label="Aborted"
                  value={count(c.aborted)}
                  tone={c.aborted ? 'abort' : undefined}
                  sub={
                    s.data.aborted_by_code.length
                      ? s.data.aborted_by_code.map((a) => `${a.n} ${codeWords(a.code)}`).join(' · ')
                      : undefined
                  }
                />
              </div>
              <div className="tm-card stack gap-10 mt-16">
                <div className="row between gap-8">
                  <h2 className="h3 sm">Step outcomes</h2>
                  <span className="small text-2">
                    {count(s.data.step_outcomes.total)} harness decisions
                  </span>
                </div>
                {s.data.step_outcomes.total === 0 ? (
                  <p className="body text-2 m-0">No data yet.</p>
                ) : (
                  <OutcomeBar shares={s.data.step_outcomes} />
                )}
              </div>
            </>
          );
        }}
      </Section>

      <div className="row between mt-24">
        <h2 className="h2-sm" style={{ fontSize: 18 }}>
          Runs
        </h2>
        <span className="small text-2">Open a run for its steps and records</span>
      </div>
      <div className="mt-12">
        {runs.isPending ? (
          <Skeleton height={260} />
        ) : runs.isError ? (
          <ErrorState error={runs.error} onRetry={() => void runs.refetch()} />
        ) : items.length === 0 ? (
          <EmptyState title="No runs in this view">
            Try a longer period, or another project or system.
          </EmptyState>
        ) : (
          <>
            <TableRegion label="Runs" minWidth={980}>
              <thead>
                <tr>
                  <th scope="col">Run</th>
                  <th scope="col">System</th>
                  <th scope="col">Ticket</th>
                  <th scope="col">Workflow</th>
                  <th scope="col">Step</th>
                  <th scope="col">Status</th>
                  <th scope="col">Lowest band</th>
                  <th scope="col">Engineer</th>
                  <th scope="col">Updated</th>
                </tr>
              </thead>
              <tbody>
                {items.map((r) => {
                  const band = bandStatus(r.lowest_band);
                  return (
                    <tr key={r.run_id}>
                      <td>
                        <Link
                          className="tm-link mono"
                          style={{ fontSize: 13 }}
                          to={`/runs/${r.run_id}`}
                          title={r.run_id}
                        >
                          {shortRunId(r.run_id)}
                        </Link>
                      </td>
                      <td className="mono">{r.system ?? '—'}</td>
                      <td>{r.ticket_ref ?? '—'}</td>
                      <td className="mono" style={{ fontSize: 13 }}>
                        {r.workflow ?? '—'}
                      </td>
                      <td>{r.current_step?.step_id ?? '—'}</td>
                      <td>
                        <StatusBadge status={runStatus(r.status_label)} />
                      </td>
                      <td>{band ? <StatusBadge status={band} /> : '—'}</td>
                      <td
                        className={r.engineer.display_name ? '' : 'mono'}
                        style={{ fontSize: 13 }}
                      >
                        {engineerName(r)}
                      </td>
                      <td>
                        <time
                          dateTime={r.updated_at ?? undefined}
                          title={r.updated_at ?? undefined}
                        >
                          {relativeTime(r.updated_at) ?? '—'}
                        </time>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </TableRegion>
            {runs.hasNextPage ? (
              <button
                type="button"
                className="tm-btn btn-ghost mt-12"
                onClick={() => void runs.fetchNextPage()}
                disabled={runs.isFetchingNextPage}
              >
                {runs.isFetchingNextPage ? 'Loading more runs…' : 'Load more runs'}
              </button>
            ) : null}
          </>
        )}
      </div>
    </>
  );
}

/* ------------------------------------------------------------------ Skill performance tab */
function SkillsTab({ filters }: { filters: EngParams }) {
  const { me } = useView();
  const skills = useEngSkills(filters);
  return (
    <Section query={skills} skeleton={<Skeleton height={320} />}>
      {(s) =>
        s.data.items.length === 0 ? (
          <EmptyState title="No skill steps in this view">
            Try a longer period, or another project or system.
          </EmptyState>
        ) : (
          <>
            <TableRegion label="Skill performance" minWidth={1080}>
              <thead>
                <tr>
                  <th scope="col">Skill</th>
                  <th scope="col">Version</th>
                  <th scope="col">Runs</th>
                  <th scope="col">First-try pass</th>
                  <th scope="col">Bands High / Medium / Low</th>
                  <th scope="col">Retries per step</th>
                  <th scope="col">Human overrides</th>
                  <th scope="col">Top failure cause</th>
                  <th scope="col">Open flags</th>
                </tr>
              </thead>
              <tbody>
                {s.data.items.map((k) => (
                  <tr key={`${k.skill_id}-${k.version}`}>
                    <td className="strong">
                      <Link className="tm-link" to={`/skills/${k.skill_id}`}>
                        {k.skill_id}
                      </Link>
                    </td>
                    <td className="mono" style={{ fontSize: 13 }}>
                      {k.version}
                    </td>
                    <td>{count(k.runs)}</td>
                    <td>
                      {k.first_try_pass === null ? (
                        'No data yet'
                      ) : (
                        <StatusBadge
                          status={{
                            tone: k.below_target ? 'input' : 'pass',
                            word: percent(k.first_try_pass) ?? '',
                          }}
                          suffix={k.below_target ? 'below target' : undefined}
                        />
                      )}
                    </td>
                    <td>
                      <BandBar mix={k.band_mix} />
                    </td>
                    <td>{decimal(k.retries_per_step) ?? '—'}</td>
                    <td>{percent(k.override_rate) ?? '—'}</td>
                    <td style={{ fontSize: 13 }}>
                      {k.top_cause ? `${k.top_cause.label} (${k.top_cause.code})` : '—'}
                    </td>
                    <td>
                      {k.open_flags > 0 && canOpenImprovement(me, k.skill_id) ? (
                        <Link className="tm-link" to={`/insights/skills/${k.skill_id}/improvement`}>
                          {k.open_flags} open
                          <span className="sr-only">
                            {' '}
                            flags: improvement report for {k.skill_id}
                          </span>
                        </Link>
                      ) : (
                        k.open_flags
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </TableRegion>
            <p className="xsmall text-2" style={{ margin: '10px 0 0' }}>
              Bar: green High, blue Medium, orange Low. Skills under{' '}
              {percent(policy.firstTryTarget)} first-try go to the owner&apos;s improvement report.
            </p>
          </>
        )
      }
    </Section>
  );
}

/* ------------------------------------------------------------------ Usage tab */
function UsageTab({ filters }: { filters: EngParams }) {
  const usage = useEngUsage(filters);
  return (
    <Section query={usage} skeleton={<SkeletonGrid count={5} />}>
      {(u) => {
        const d = u.data;
        return (
          <>
            <div className="grid g-200">
              <StatTile label="Active engineers" value={count(d.active_engineers)} />
              <StatTile label="Runs started" value={count(d.runs_started)} />
              <StatTile label="PR merge rate" value={percent(d.pr_merge_rate)} />
              <StatTile
                label="PRs without a run record"
                value={count(d.prs_without_run)}
                tone={d.prs_without_run ? 'input' : undefined}
                sub="code changed outside the plugin"
              />
              <StatTile
                label="PRs with changes requested"
                value={percent(d.changes_requested_share)}
                sub="share of opened PRs"
              />
            </div>
            <div className="tm-card stack gap-12 mt-16">
              <h2 className="h3 sm">Runs by workflow</h2>
              {d.runs_by_workflow.length === 0 ? (
                <p className="body text-2 m-0">No data yet.</p>
              ) : (
                <HBars
                  label="Runs by workflow"
                  mono
                  items={d.runs_by_workflow.map((w) => ({ label: w.workflow_id, value: w.runs }))}
                />
              )}
              <p className="m-0 xsmall text-2">
                Engineers are shown by pseudonym (eng-xxxx). Names are visible only to{' '}
                {roleList(policy.rd1NameRevealRoles)}, and only when they ask for them.
              </p>
            </div>
            <div className="grid g-340 mt-16">
              <div className="stack gap-8">
                <h2 className="h3 sm">Weekly active engineers and runs</h2>
                {d.weekly.length === 0 ? (
                  <p className="body text-2 m-0">No data yet.</p>
                ) : (
                  <TableRegion label="Weekly active engineers and runs started">
                    <thead>
                      <tr>
                        <th scope="col">Week</th>
                        <th scope="col">Active engineers</th>
                        <th scope="col">Runs started</th>
                      </tr>
                    </thead>
                    <tbody>
                      {d.weekly.map((w) => (
                        <tr key={w.week}>
                          <td className="mono">{w.week}</td>
                          <td>{w.active_engineers}</td>
                          <td>{w.runs_started}</td>
                        </tr>
                      ))}
                    </tbody>
                  </TableRegion>
                )}
              </div>
              <div className="stack gap-8">
                <h2 className="h3 sm">Average tokens and cost per run</h2>
                {d.cost_by_workflow.length === 0 ? (
                  <p className="body text-2 m-0">No data yet.</p>
                ) : (
                  <TableRegion label="Average tokens and cost per run, by workflow">
                    <thead>
                      <tr>
                        <th scope="col">Workflow</th>
                        <th scope="col">Avg tokens</th>
                        <th scope="col">Avg cost</th>
                      </tr>
                    </thead>
                    <tbody>
                      {d.cost_by_workflow.map((w) => (
                        <tr key={w.workflow_id}>
                          <td className="mono">{w.workflow_id}</td>
                          <td>{compactTokens(w.avg_tokens)}</td>
                          <td>{usd(w.avg_cost_usd)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </TableRegion>
                )}
              </div>
            </div>
          </>
        );
      }}
    </Section>
  );
}

/* ------------------------------------------------------------------ Health tab */
function HealthTab({ filters }: { filters: EngParams }) {
  const health = useEngHealth(filters);
  return (
    <Section query={health} skeleton={<SkeletonGrid count={3} height={200} cls="g-320" />}>
      {(h) => {
        const d = h.data;
        return (
          <div className="grid g-320" style={{ gap: 16 }}>
            <div className="tm-card stack gap-10">
              <h2 className="h3 sm">Context packs</h2>
              <p className="m-0 small text-2">
                {d.fresh_systems} of {d.packs.length} systems have a fresh pack
              </p>
              {d.packs.length === 0 ? (
                <p className="body text-2 m-0">No systems in this view.</p>
              ) : (
                <ul className="plain-list stack gap-10">
                  {d.packs.map((p) => {
                    const st = packStatus(p.status);
                    const extra =
                      p.status === 'fresh'
                        ? p.days_since_signed !== null
                          ? `signed ${daysAgo(p.days_since_signed)}`
                          : undefined
                        : [
                            p.days_since_signed !== null ? `${p.days_since_signed} days` : null,
                            p.drift_files ? `${p.drift_files} files drift` : null,
                          ]
                            .filter(Boolean)
                            .join(', ') || undefined;
                    return (
                      <li key={p.system} className="row between gap-8">
                        <span className="mono">{p.system}</span>
                        <StatusBadge status={st} suffix={extra} />
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>
            <div className="tm-card stack gap-10">
              <h2 className="h3 sm">CI verification</h2>
              <dl className="kv m-0">
                <dt>PRs verified</dt>
                <dd>{count(d.ci.verified)}</dd>
                <dt>Missing records (E-CI-01)</dt>
                <dd className={d.ci.e_ci_01 ? 'tone-input' : ''}>{count(d.ci.e_ci_01)}</dd>
                <dt>Signature problems (E-CI-02)</dt>
                <dd className={d.ci.e_ci_02 ? 'tone-abort' : ''}>{count(d.ci.e_ci_02)}</dd>
                <dt>Re-check mismatch (E-CI-03)</dt>
                <dd className={d.ci.e_ci_03 ? 'tone-abort' : ''}>{count(d.ci.e_ci_03)}</dd>
              </dl>
            </div>
            <div className="tm-card stack gap-10">
              <h2 className="h3 sm">Telemetry and plugin</h2>
              {d.telemetry === null ? (
                <p className="body text-2 m-0">
                  Shown to tech leads, engineering leads and admins.
                </p>
              ) : (
                <dl className="kv m-0">
                  <dt>Events received today</dt>
                  <dd>{count(d.telemetry.events_today)}</dd>
                  <dt>Devices with queued events</dt>
                  <dd>{count(d.telemetry.devices_with_queue)}</dd>
                  <dt>Engineers on plugin {d.telemetry.plugin_spread.latest ?? 'latest'}</dt>
                  <dd>
                    {d.telemetry.plugin_spread.on_latest} of {d.telemetry.plugin_spread.active}
                  </dd>
                  <dt>Policy blocks by hooks</dt>
                  <dd>{count(d.telemetry.policy_blocks)}</dd>
                </dl>
              )}
            </div>
          </div>
        );
      }}
    </Section>
  );
}

/** Insights: Engineering monitoring (board InsightsEngineer; SDD-09 §4.13). Filters live in the URL. */
export default function InsightsEngineering() {
  const { me } = useView();
  const { tab: rawTab } = useParams();
  const tab: EngTab = (ENG_TABS.find((t) => t.id === rawTab)?.id ?? 'runs') as EngTab;
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const [names, setNames] = useState(false);

  const projects = me.scope.projects;
  const project = params.get('project') ?? '';
  const systemsInView = (project ? projects.filter((p) => p.code === project) : projects).flatMap(
    (p) => p.systems.map((s) => s.code),
  );
  const rawSystem = params.get('system') ?? '';
  const system = systemsInView.includes(rawSystem) ? rawSystem : '';
  const period = params.get('period') === '90d' ? '90d' : '30d';
  const filters: EngParams = {
    project: project || undefined,
    system: system || undefined,
    period,
  };

  function setFilter(key: string, value: string) {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    if (key === 'project') next.delete('system');
    setParams(next, { replace: true });
  }

  function selectTab(id: string) {
    const qs = params.toString();
    navigate(`/insights/engineering/${id}${qs ? `?${qs}` : ''}`);
  }

  return (
    <div className="pb-56">
      <section className="band-surface">
        <div className="tm-wrap stack gap-16" style={{ paddingTop: 32 }}>
          <div className="row between align-end gap-16">
            <div>
              <p className="tm-eyebrow">Insights · Engineering</p>
              <PageTitle title="Monitoring">Monitoring</PageTitle>
              <p className="tm-sub">
                Runs, quality and health from run events, Claude Code telemetry and GitHub. Metadata
                only.
              </p>
            </div>
            <div className="row gap-10">
              <label className="field">
                Project
                <select value={project} onChange={(e) => setFilter('project', e.target.value)}>
                  <option value="">All my projects</option>
                  {projects.map((p) => (
                    <option key={p.code} value={p.code}>
                      {p.code}
                    </option>
                  ))}
                </select>
              </label>
              <label className="field">
                System
                <select value={system} onChange={(e) => setFilter('system', e.target.value)}>
                  <option value="">All systems</option>
                  {systemsInView.map((s) => (
                    <option key={s} value={s}>
                      {s}
                    </option>
                  ))}
                </select>
              </label>
              <label className="field">
                Period
                <select
                  value={period}
                  onChange={(e) =>
                    setFilter('period', e.target.value === '30d' ? '' : e.target.value)
                  }
                >
                  {PERIODS.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.label}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          </div>
          <div className="row between gap-12">
            <Tabs
              label="Monitoring views"
              items={ENG_TABS}
              selected={tab}
              onSelect={selectTab}
              idPrefix="mon"
              flat
            />
            {me.can_reveal_names && tab === 'runs' ? (
              <label className="toggle">
                <input
                  type="checkbox"
                  checked={names}
                  onChange={(e) => setNames(e.target.checked)}
                />
                Show names
                <span className="xsmall text-2">(each reveal is recorded)</span>
              </label>
            ) : null}
          </div>
        </div>
      </section>

      <section className="tm-wrap pt-24" {...tabPanelProps('mon', tab)}>
        {projects.length === 0 ? (
          <EmptyState title="No systems in your scope yet">
            Ask your tech lead to grant you access to a system.
          </EmptyState>
        ) : tab === 'runs' ? (
          <RunsTab filters={filters} names={names} />
        ) : tab === 'skills' ? (
          <SkillsTab filters={filters} />
        ) : tab === 'usage' ? (
          <UsageTab filters={filters} />
        ) : (
          <HealthTab filters={filters} />
        )}
        <p className="xsmall text-2 mt-24">
          Views refresh every 5 minutes. Times are in your local time.
        </p>
      </section>
    </div>
  );
}
