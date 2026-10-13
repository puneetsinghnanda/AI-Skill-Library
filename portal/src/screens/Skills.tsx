import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useSkills, useSummary } from '../api/queries';
import { useView } from '../app/ViewContext';
import { FilterChips } from '../components/FilterChips';
import { PageTitle } from '../components/Heading';
import { SearchIcon } from '../components/Icons';
import { EmptyState, Section, SkeletonGrid } from '../components/States';
import { Badge, StatusBadge } from '../components/StatusBadge';
import { env } from '../config/env';
import { humanize, percent } from '../lib/format';
import { skillStatus } from '../lib/status';

/** Skills (board Skills; SDD-09 §4.6). Search is debounced 250 ms and kept in the URL. */
export default function Skills() {
  const { view } = useView();
  const eng = view === 'engineer';
  const [params, setParams] = useSearchParams();
  const urlQ = params.get('q') ?? '';
  const role = params.get('role') ?? '';
  const [text, setText] = useState(urlQ);

  useEffect(() => setText(urlQ), [urlQ]);
  useEffect(() => {
    const h = window.setTimeout(() => {
      if (text.trim() === urlQ) return;
      const next = new URLSearchParams(params);
      if (text.trim()) next.set('q', text.trim());
      else next.delete('q');
      setParams(next, { replace: true });
    }, 250);
    return () => window.clearTimeout(h);
  }, [text, urlQ, params, setParams]);

  const summary = useSummary();
  const skills = useSkills({
    q: urlQ || undefined,
    role: role || undefined,
    // Business view asks for the client-facing statuses only; engineers get the server default,
    // which adds drafts for engineer-family roles (SDD-01 §7).
    status: eng ? undefined : 'pilot,production',
    period: '90d',
    limit: 100,
  });
  const roleOptions = [
    { id: '', label: 'All roles' },
    ...(summary.data?.data.roles ?? []).map((r) => ({ id: r.id, label: r.label })),
  ];

  function pickRole(id: string) {
    const next = new URLSearchParams(params);
    if (id) next.set('role', id);
    else next.delete('role');
    setParams(next, { replace: true });
  }

  const items = skills.data?.data.items ?? [];
  return (
    <div className="pb-56">
      <section className="band-surface">
        <div className="tm-wrap stack gap-20" style={{ paddingTop: 40, paddingBottom: 28 }}>
          <div className="row between align-end gap-12">
            <div>
              <p className="tm-eyebrow">Catalogue</p>
              <PageTitle title="Skills">Skills</PageTitle>
              <p className="tm-sub">
                {eng
                  ? 'Every skill your workflows can call, with version, quality and install details.'
                  : 'What each AI skill delivers, by role and SDLC phase. Production skills can be offered to clients.'}
              </p>
            </div>
            {eng ? (
              <a className="tm-btn btn-ghost" href={env.marketplaceRepoUrl}>
                View source on GitHub
              </a>
            ) : null}
          </div>
          <form
            role="search"
            aria-label="Search the skill catalogue"
            onSubmit={(e) => e.preventDefault()}
          >
            <label className="search-large on-page">
              <SearchIcon size={18} />
              <span className="sr-only">Search skills</span>
              <input
                type="search"
                value={text}
                maxLength={60}
                onChange={(e) => setText(e.target.value)}
                placeholder='Search by task, role, phase or output, e.g. "threat", "test", "estimate"'
              />
            </label>
          </form>
          <FilterChips
            label="Filter by role"
            options={roleOptions}
            value={role}
            onChange={pickRole}
          />
        </div>
      </section>

      <section className="tm-wrap pt-24">
        <p className="body text-2" style={{ margin: '0 0 16px' }} aria-live="polite">
          <strong style={{ color: 'var(--tm-text)' }}>
            {skills.isPending ? '…' : items.length}
          </strong>{' '}
          skills · {eng ? 'production, pilot and draft' : 'production and pilot'}
        </p>
        <Section query={skills} skeleton={<SkeletonGrid count={6} height={190} cls="g-290" />}>
          {() =>
            items.length === 0 ? (
              <EmptyState title="No skills match">
                Try another word, or clear the role filter.
              </EmptyState>
            ) : (
              <ul className="plain-list grid g-290">
                {items.map((s) => (
                  <li key={s.id}>
                    <Link
                      to={`/skills/${s.id}`}
                      className="tm-card card-link"
                      style={{ minHeight: 190, height: '100%' }}
                    >
                      <span className="row between gap-8" style={{ width: '100%' }}>
                        <span
                          className="xsmall strong text-2"
                          style={{ textTransform: 'uppercase', letterSpacing: '0.05em' }}
                        >
                          {s.agent_role_label}
                        </span>
                        <StatusBadge status={skillStatus(s.status)} />
                      </span>
                      <span className="strong" style={{ fontSize: 17 }}>
                        {s.title}
                      </span>
                      <span className="body text-2">{s.summary}</span>
                      <span className="row gap-6" style={{ marginTop: 'auto' }}>
                        <Badge>{humanize(s.phase)}</Badge>
                        {eng ? (
                          <>
                            <Badge tone="teal" mono>
                              {s.id} v{s.current_version}
                            </Badge>
                            {s.first_try_pass === null ? (
                              <Badge tone="retry">First-try: no data yet</Badge>
                            ) : (
                              <StatusBadge
                                status={{
                                  tone: s.first_try_pass < 0.8 ? 'input' : 'pass',
                                  word: `${percent(s.first_try_pass)} first-try`,
                                }}
                              />
                            )}
                          </>
                        ) : s.outputs.length ? (
                          <Badge tone="teal">Output: {s.outputs.join(', ')}</Badge>
                        ) : null}
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            )
          }
        </Section>
      </section>
    </div>
  );
}
