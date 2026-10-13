import { Link, useParams, useSearchParams } from 'react-router-dom';
import { useSkill, useSkillQuality } from '../api/queries';
import type { SkillDetail as Skill } from '../api/types';
import { canOpenImprovement, useView } from '../app/ViewContext';
import { HBars } from '../components/Charts';
import { CodeChip } from '../components/CodeChip';
import { PageTitle } from '../components/Heading';
import { StatTile } from '../components/StatTile';
import { EmptyState, ErrorState, Section, Skeleton, SkeletonGrid } from '../components/States';
import { Badge, StatusBadge } from '../components/StatusBadge';
import { Tabs, tabPanelProps } from '../components/Tabs';
import { TableRegion } from '../components/TableRegion';
import { env, pilotHref } from '../config/env';
import { runCommand } from '../content/commands';
import { count, humanize, percent } from '../lib/format';
import { skillStatus } from '../lib/status';

const TABS = [
  { id: 'io', label: 'Inputs and outputs' },
  { id: 'quality', label: 'Quality' },
  { id: 'versions', label: 'Versions' },
  { id: 'workflows', label: 'Used in workflows' },
] as const;

function gateText(g: string | null): string {
  return g ? `, after the ${g} gate` : '';
}

function EngineerTabs({ skill }: { skill: Skill }) {
  const { me } = useView();
  const [params, setParams] = useSearchParams();
  const tab = TABS.some((t) => t.id === params.get('tab')) ? (params.get('tab') as string) : 'io';
  const quality = useSkillQuality(skill.id, { period: '90d' }, tab === 'quality');
  const select = (id: string) => {
    const next = new URLSearchParams(params);
    next.set('tab', id);
    setParams(next, { replace: true });
  };
  return (
    <section className="tm-wrap pt-32">
      <Tabs label="Skill details" items={TABS} selected={tab} onSelect={select} idPrefix="skill" />
      <div {...tabPanelProps('skill', tab)}>
        {tab === 'io' ? (
          <div className="grid g-340 pt-20">
            <div className="tm-card stack gap-8">
              <h2 className="h3 sm">Inputs</h2>
              {skill.current.inputs.length === 0 ? (
                <p className="body text-2 m-0">No declared inputs.</p>
              ) : (
                skill.current.inputs.map((i) => (
                  <p className="m-0 body" key={i.name}>
                    <code className="mono">{i.schema ?? i.name}</code>
                    {i.required ? ' · required' : ' · optional'}
                  </p>
                ))
              )}
              {skill.current.context_sections.length ? (
                <p className="m-0 body">
                  <code className="mono">context pack</code> ·{' '}
                  {skill.current.context_sections.join(', ')}
                </p>
              ) : null}
              <p className="m-0 small text-2">
                Size budget:{' '}
                {skill.current.size_budget_tokens
                  ? `${Math.round(skill.current.size_budget_tokens / 1000)}k tokens`
                  : 'not set'}{' '}
                · allowed tools: {skill.current.allowed_tools.join(', ') || 'none'}
              </p>
            </div>
            <div className="tm-card stack gap-8">
              <h2 className="h3 sm">Output</h2>
              {skill.current.outputs.map((o) => (
                <p className="m-0 body" key={o.name}>
                  <code className="mono">{o.schema ?? o.name}</code>
                </p>
              ))}
              <p className="m-0 small text-2">
                Records: .checks.json · .review.json · .verification.json (signed)
              </p>
            </div>
          </div>
        ) : null}

        {tab === 'quality' ? (
          <div className="mt-20">
            <Section query={quality} skeleton={<Skeleton height={180} />}>
              {(qd) => (
                <div className="tm-card stack gap-14">
                  <h2 className="h3 sm">Top reasons a step did not pass first time</h2>
                  {qd.data.causes.length === 0 ? (
                    <p className="body text-2 m-0">
                      No failed first attempts in the last 90 days
                      {qd.data.first_attempts ? '' : ', or no runs yet'}.
                    </p>
                  ) : (
                    <HBars
                      label="Top reasons a step did not pass first time"
                      fill="fill-find"
                      items={qd.data.causes.map((c) => ({
                        label: `${c.label} (${c.code})`,
                        value: c.n,
                      }))}
                    />
                  )}
                  <p className="m-0 xsmall text-2">
                    From verification records (metadata only), {count(qd.data.first_attempts)} first
                    attempts, {qd.data.scope_level === 'org' ? 'all systems' : 'your systems'}.
                    {skill.owner_pseudonym ? ` Owner: ${skill.owner_pseudonym}.` : ''}
                  </p>
                  {canOpenImprovement(me, skill.id) ? (
                    <Link
                      className="tm-link self-start"
                      to={`/insights/skills/${skill.id}/improvement`}
                    >
                      Open improvement report →
                    </Link>
                  ) : null}
                </div>
              )}
            </Section>
          </div>
        ) : null}

        {tab === 'versions' ? (
          <TableRegion label="Versions" className="mt-20">
            <thead>
              <tr>
                <th scope="col">Version</th>
                <th scope="col">Status</th>
                <th scope="col">Eval pass</th>
                <th scope="col">Change</th>
              </tr>
            </thead>
            <tbody>
              {skill.versions.map((v) => (
                <tr key={v.version}>
                  <td className="mono">{v.version}</td>
                  <td>
                    <StatusBadge status={skillStatus(v.status)} />
                  </td>
                  <td>{percent(v.eval_pass_rate) ?? 'No data yet'}</td>
                  <td>{v.changelog ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </TableRegion>
        ) : null}

        {tab === 'workflows' ? (
          skill.workflows.length === 0 ? (
            <div className="mt-20">
              <EmptyState title="Not used in a workflow yet">
                Run it on its own from Claude Code.
              </EmptyState>
            </div>
          ) : (
            <div className="grid g-280 pt-20" style={{ gap: 16 }}>
              {skill.workflows.map((w) => (
                <div className="tm-card" key={w.workflow_id}>
                  <h2 className="h3 sm mono">{w.workflow_id}</h2>
                  <p className="small text-2" style={{ margin: '6px 0 0' }}>
                    Step {w.position} of {w.step_count}
                    {gateText(w.after_gate)}.
                  </p>
                </div>
              ))}
            </div>
          )
        ) : null}
      </div>
    </section>
  );
}

/** Skill detail (board SkillDetail; SDD-09 §4.7). Headline numbers are org-wide (class A). */
export default function SkillDetail() {
  const { skillId = '' } = useParams();
  const { view } = useView();
  const eng = view === 'engineer';
  const skill = useSkill(skillId);

  if (skill.isPending) {
    return (
      <div className="tm-wrap pt-32 stack gap-24">
        <PageTitle title="Skill">Skill</PageTitle>
        <Skeleton height={120} />
        <SkeletonGrid count={4} />
      </div>
    );
  }
  if (skill.isError) {
    return (
      <div className="tm-wrap pt-32 pb-56 stack gap-16">
        <Link className="tm-link self-start" to="/skills">
          ← All skills
        </Link>
        <PageTitle title="Skill">Skill not available</PageTitle>
        <ErrorState error={skill.error} />
      </div>
    );
  }
  const s = skill.data.data;
  const repoTree = `${env.marketplaceRepoUrl}/tree/${s.release_tag ?? 'main'}/plugins/truminds/skills/${s.id}`;
  const firstWf = s.workflows[0]?.workflow_id ?? null;
  const pilot = pilotHref(`Request a pilot: ${s.title}`);
  const why = s.portal.why_clients_care ?? [];
  const receives = s.portal.client_receives ?? [];

  return (
    <div className="pb-56">
      <section className="band-surface">
        <div className="tm-wrap stack gap-14" style={{ paddingTop: 28, paddingBottom: 28 }}>
          <Link className="tm-link self-start no-print" to="/skills">
            ← All skills
          </Link>
          <div className="row between align-start gap-20">
            <div style={{ flex: '1 1 560px', minWidth: 0 }}>
              <div className="row gap-8">
                <Badge>{s.agent_role_label}</Badge>
                <Badge>{humanize(s.phase)} phase</Badge>
                <StatusBadge status={skillStatus(s.status)} />
              </div>
              <PageTitle title={s.title} className="page-h1 mt-12">
                {s.title}
              </PageTitle>
              <p className="tm-sub" style={{ maxWidth: 760 }}>
                {s.summary}
              </p>
            </div>
            {eng ? (
              <div className="tm-card stack gap-10" style={{ flex: '0 1 380px' }}>
                <p className="m-0 small strong text-2">Use it in Claude Code</p>
                <CodeChip code={runCommand(firstWf)} />
                {s.workflows.length ? (
                  <p className="m-0 xsmall text-2">
                    Runs inside {s.workflows.map((w) => w.workflow_id).join(' and ')}
                    {s.workflows[0]?.after_gate
                      ? ` after the ${s.workflows[0].after_gate} gate`
                      : ''}
                    .
                  </p>
                ) : null}
                <div className="row gap-8">
                  <a className="tm-btn btn-ghost" href={repoTree}>
                    SKILL.md on GitHub
                  </a>
                  <Link className="tm-btn btn-primary" to="/get-started">
                    Install plugin
                  </Link>
                </div>
              </div>
            ) : (
              <div className="tm-card stack gap-10" style={{ flex: '0 1 380px' }}>
                <p className="m-0 small strong text-2">Offer it to a client</p>
                {s.pods.length ? (
                  <p className="m-0 body">
                    Included in{' '}
                    {s.pods.map((p, i) => (
                      <span key={p.id}>
                        {i > 0 ? (i === s.pods.length - 1 ? ' and ' : ', ') : ''}
                        the <strong>{p.title}</strong>
                      </span>
                    ))}
                    .
                  </p>
                ) : (
                  <p className="m-0 body">Not part of a ready-made pod yet.</p>
                )}
                <div className="row gap-8 no-print">
                  {s.pods[0] ? (
                    <Link className="tm-btn btn-primary" to={`/pods/${s.pods[0].id}`}>
                      See the pod
                    </Link>
                  ) : null}
                  <button type="button" className="tm-btn btn-ghost" onClick={() => window.print()}>
                    Download one-pager
                  </button>
                  {pilot ? (
                    <a className="tm-btn btn-ghost" href={pilot}>
                      Request a pilot
                    </a>
                  ) : null}
                </div>
              </div>
            )}
          </div>
        </div>
      </section>

      <div className="tm-wrap pt-24 grid g-200">
        <StatTile label="Runs, last 90 days" value={count(s.quality.runs)} />
        <StatTile label="First-try pass" value={percent(s.quality.first_try_pass)} tone="pass" />
        <StatTile label="High confidence" value={percent(s.quality.band_mix.high)} />
        <StatTile
          label="Signed eval pass rate"
          value={percent(s.eval.pass_rate)}
          sub={
            s.eval.pass_rate !== null
              ? `v${s.eval.version} · ${s.eval.cases ?? 0} cases`
              : undefined
          }
        />
      </div>

      {eng ? (
        <EngineerTabs skill={s} />
      ) : (
        <section className="tm-wrap pt-32 grid g-340">
          <div className="tm-card stack gap-10">
            <h2 className="h2-sm">Why clients care</h2>
            {why.length ? (
              <ul className="list">
                {why.map((w) => (
                  <li key={w}>{w}</li>
                ))}
              </ul>
            ) : (
              <p className="body text-2 m-0">The skill owner has not written this yet.</p>
            )}
          </div>
          <div className="tm-card stack gap-10">
            <h2 className="h2-sm">What the client receives</h2>
            {receives.length ? (
              <ul className="list">
                {receives.map((w) => (
                  <li key={w}>{w}</li>
                ))}
              </ul>
            ) : (
              <p className="body text-2 m-0">The skill owner has not written this yet.</p>
            )}
          </div>
        </section>
      )}
    </div>
  );
}
