import { Link } from 'react-router-dom';
import { useHome, useReleases, useRuns, useSkills } from '../api/queries';
import type { WaitingItem } from '../api/types';
import { useView } from '../app/ViewContext';
import { CodeChip } from '../components/CodeChip';
import { PageTitle } from '../components/Heading';
import { StatTile } from '../components/StatTile';
import { EmptyState, ErrorState, Section, Skeleton, SkeletonGrid } from '../components/States';
import { Badge, StatusBadge } from '../components/StatusBadge';
import { TableRegion } from '../components/TableRegion';
import { env } from '../config/env';
import { RUN_TEMPLATE } from '../content/commands';
import { askRoleLabel, signalLabel } from '../content/labels';
import { browserTimeZone, count, daysAgo, percent, relativeTime, shortRunId } from '../lib/format';
import { packStatus, runStatus } from '../lib/status';

function WaitingCard({ w }: { w: WaitingItem }) {
  if (w.kind === 'question') {
    return (
      <li className="row align-start gap-12 inset" style={{ flexWrap: 'nowrap', padding: 12 }}>
        <StatusBadge status={{ tone: 'input', word: 'Question' }} />
        <div className="stack gap-4" style={{ minWidth: 0 }}>
          <p className="m-0 body strong">
            <Link to={`/runs/${w.run_id}`}>
              {w.item} · {w.ticket_ref ?? shortRunId(w.run_id)}
            </Link>
          </p>
          <p className="m-0 xsmall text-2">
            {w.blocking ? 'Blocking · ' : ''}
            {askRoleLabel(w.ask_role)} decides
            {w.since ? ` · waiting since ${relativeTime(w.since) ?? ''}` : ''}
          </p>
          {w.file_url ? (
            <a className="xsmall" href={w.file_url} rel="noreferrer noopener">
              Open open-questions.md
            </a>
          ) : null}
        </div>
      </li>
    );
  }
  return (
    <li className="row align-start gap-12 inset" style={{ flexWrap: 'nowrap', padding: 12 }}>
      <StatusBadge status={{ tone: 'esc', word: 'Approval' }} />
      <div className="stack gap-4" style={{ minWidth: 0 }}>
        <p className="m-0 body strong">
          <Link to={`/runs/${w.run_id}`}>
            {w.item} · {w.ticket_ref ?? shortRunId(w.run_id)}
          </Link>
        </p>
        <p className="m-0 xsmall text-2">
          {w.reason_code ? `Reason: ${signalLabel(w.reason_code)}` : 'Gate approval'}
          {w.since ? ` · waiting since ${relativeTime(w.since) ?? ''}` : ''}
        </p>
      </div>
    </li>
  );
}

/** Home: Engineer (board HomeEngineer; SDD-09 §4.4). */
export default function HomeEngineer() {
  const { me } = useView();
  const home = useHome(browserTimeZone());
  const runs = useRuns({ owner: 'me', limit: 5 });
  const role = home.data?.data.agent_role ?? me.agent_role ?? null;
  const skills = useSkills({ role: role ?? undefined, limit: 3 }, role !== null);
  const releases = useReleases(1);
  const myRuns = runs.data?.pages[0]?.data.items ?? [];
  const roleLabel = skills.data?.data.items[0]?.agent_role_label ?? null;

  return (
    <div className="pb-56">
      <section className="band-primary on-primary">
        <div className="tm-wrap row between gap-24" style={{ paddingTop: 40, paddingBottom: 40 }}>
          <div style={{ flex: '1 1 520px', minWidth: 0 }}>
            <PageTitle title="Home" className="page-h1">
              Welcome back
            </PageTitle>
            <p className="hero-lead mt-12" style={{ fontSize: 15, maxWidth: 620 }}>
              Your runs, the questions waiting for you and the skills for your role. Runs execute in
              Claude Code on your laptop; this page only shows their status.
            </p>
          </div>
          <div className="stack gap-12" style={{ alignItems: 'flex-end' }}>
            <div className="row gap-10">
              <Link className="tm-btn btn-accent" to="/get-started">
                Install the plugin
              </Link>
              <a className="tm-btn btn-light" href={env.marketplaceRepoUrl}>
                Open GitHub repo
              </a>
            </div>
            <div className="row gap-8">
              <span className="small muted-inverse">Start a run in Claude Code:</span>
              <CodeChip code={RUN_TEMPLATE} onDark />
            </div>
          </div>
        </div>
      </section>

      <div className="tm-wrap pt-32 split">
        <div className="main">
          <Section query={home} skeleton={<SkeletonGrid count={4} />}>
            {(h) => {
              const t = h.data.tiles;
              return (
                <div className="grid g-170">
                  <StatTile label="My active runs" value={count(t.active_runs)} />
                  <StatTile
                    label="Waiting on me"
                    value={count(t.waiting_on_me.total)}
                    tone={t.waiting_on_me.total > 0 ? 'input' : undefined}
                    sub={`${t.waiting_on_me.questions} ${t.waiting_on_me.questions === 1 ? 'question' : 'questions'} · ${t.waiting_on_me.approvals} ${t.waiting_on_me.approvals === 1 ? 'approval' : 'approvals'}`}
                  />
                  <StatTile
                    label="First-try pass"
                    value={percent(t.my_first_try_pass.value)}
                    tone="pass"
                    sub={`my last ${t.my_first_try_pass.n} steps`}
                  />
                  <StatTile label="PRs this month" value={count(t.my_prs_this_month)} />
                </div>
              );
            }}
          </Section>

          <div className="row between">
            <h2 className="h2-sm">My runs</h2>
            <Link className="tm-link" to="/insights">
              All runs →
            </Link>
          </div>
          {runs.isPending ? (
            <Skeleton height={220} />
          ) : runs.isError ? (
            <ErrorState error={runs.error} onRetry={() => void runs.refetch()} />
          ) : myRuns.length === 0 ? (
            <EmptyState title="No runs yet">
              Start one in Claude Code with <span className="mono">{RUN_TEMPLATE}</span>.
            </EmptyState>
          ) : (
            <TableRegion label="My runs" minWidth={760}>
              <thead>
                <tr>
                  <th scope="col">Run</th>
                  <th scope="col">Ticket</th>
                  <th scope="col">Workflow · step</th>
                  <th scope="col">Status</th>
                  <th scope="col">Next action</th>
                </tr>
              </thead>
              <tbody>
                {myRuns.map((r) => (
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
                    <td>{r.ticket_ref ?? '—'}</td>
                    <td>
                      {r.workflow ?? '—'}
                      {r.current_step ? ` · ${r.current_step.step_id}` : ''}
                    </td>
                    <td>
                      <StatusBadge status={runStatus(r.status_label)} />
                    </td>
                    <td>{r.next_action.text}</td>
                  </tr>
                ))}
              </tbody>
            </TableRegion>
          )}

          <div className="row between">
            <h2 className="h2-sm">Skills for your role{roleLabel ? ` · ${roleLabel}` : ''}</h2>
            <Link
              className="tm-link"
              to={role ? `/skills?role=${encodeURIComponent(role)}` : '/skills'}
            >
              All skills →
            </Link>
          </div>
          {role === null ? (
            <EmptyState title="No agent role on your profile">
              Browse all skills, or ask an admin to set your role.
            </EmptyState>
          ) : (
            <Section query={skills} skeleton={<SkeletonGrid count={3} height={140} cls="g-220" />}>
              {(s) =>
                s.data.items.length === 0 ? (
                  <EmptyState title="No skills for your role yet">
                    Browse all skills instead.
                  </EmptyState>
                ) : (
                  <ul className="plain-list grid g-220" style={{ gap: 16 }}>
                    {s.data.items.map((k) => (
                      <li key={k.id}>
                        <Link
                          to={`/skills/${k.id}`}
                          className="tm-card card-link"
                          style={{ gap: 8 }}
                        >
                          <span className="row gap-8">
                            <span className="strong mono" style={{ fontSize: 15 }}>
                              {k.id}
                            </span>
                            <Badge>v{k.current_version}</Badge>
                          </span>
                          <span className="small text-2" style={{ lineHeight: 1.5 }}>
                            {k.summary}
                          </span>
                          <span className="self-start">
                            {k.first_try_pass === null ? (
                              <Badge tone="retry">First-try: no data yet</Badge>
                            ) : (
                              <StatusBadge
                                status={{
                                  tone: k.first_try_pass < 0.8 ? 'input' : 'pass',
                                  word: `${percent(k.first_try_pass)} first-try`,
                                }}
                              />
                            )}
                          </span>
                        </Link>
                      </li>
                    ))}
                  </ul>
                )
              }
            </Section>
          )}
        </div>

        <aside className="side" aria-label="Waiting on me, what's new and my systems">
          <div className="tm-card stack gap-12">
            <h2 className="m-0" style={{ fontSize: 18 }}>
              Waiting on me
            </h2>
            <Section query={home} skeleton={<Skeleton height={120} />}>
              {(h) =>
                h.data.waiting.length === 0 ? (
                  <p className="body text-2 m-0">Nothing is waiting on you.</p>
                ) : (
                  <ul className="plain-list stack gap-12">
                    {h.data.waiting.map((w) => (
                      <WaitingCard key={`${w.kind}-${w.run_id}-${w.item}`} w={w} />
                    ))}
                  </ul>
                )
              }
            </Section>
            <p className="m-0 xsmall text-2">
              Question text stays in the companion repo; open the file to read and answer it.
            </p>
          </div>

          <div className="tm-card stack gap-12">
            <h2 className="m-0" style={{ fontSize: 18 }}>
              What&apos;s new
            </h2>
            <Section query={releases} skeleton={<Skeleton height={120} />}>
              {(r) => {
                const rel = r.data.items[0];
                if (!rel) return <p className="body text-2 m-0">No releases yet.</p>;
                return (
                  <>
                    {rel.notes.map((n, i) => (
                      <div key={`${n.id ?? n.kind}-${i}`}>
                        <p className="m-0 body strong">
                          {n.id ? `${n.id}${n.version ? ` v${n.version}` : ''}` : n.kind}
                        </p>
                        <p className="m-0 xsmall text-2">{n.text}</p>
                      </div>
                    ))}
                    <div>
                      <p className="m-0 body strong">Plugin {rel.plugin_version}</p>
                      <p className="m-0 xsmall text-2">Release {rel.tag}</p>
                    </div>
                  </>
                );
              }}
            </Section>
          </div>

          <div className="tm-card stack gap-10">
            <h2 className="m-0" style={{ fontSize: 18 }}>
              My systems
            </h2>
            <Section query={home} skeleton={<Skeleton height={80} />}>
              {(h) =>
                h.data.systems.length === 0 ? (
                  <p className="body text-2 m-0">You have no systems yet.</p>
                ) : (
                  <ul className="plain-list stack gap-10">
                    {h.data.systems.map((s) => {
                      const st = packStatus(s.pack_status);
                      const extra =
                        s.pack_status === 'fresh'
                          ? s.days_since_signed !== null
                            ? `signed ${daysAgo(s.days_since_signed)}`
                            : undefined
                          : [
                              s.days_since_signed !== null ? `${s.days_since_signed} days` : null,
                              s.drift_files ? `${s.drift_files} files drift` : null,
                            ]
                              .filter(Boolean)
                              .join(', ') || undefined;
                      return (
                        <li key={s.system} className="row gap-8">
                          <span className="mono strong body">{s.system}</span>
                          <StatusBadge
                            status={{ ...st, word: `Context pack ${st.word.toLowerCase()}` }}
                            suffix={extra}
                          />
                        </li>
                      );
                    })}
                  </ul>
                )
              }
            </Section>
            <p className="m-0 xsmall text-2" style={{ lineHeight: 1.5 }}>
              A stale pack caps confidence at Medium. Ask the tech lead to run{' '}
              <code className="mono">tsl context build</code>.
            </p>
          </div>
        </aside>
      </div>
    </div>
  );
}
