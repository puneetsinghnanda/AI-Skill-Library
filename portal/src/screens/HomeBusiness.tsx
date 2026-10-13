import { useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useBusiness, usePods, useSummary } from '../api/queries';
import { PageTitle, SectionHead } from '../components/Heading';
import { BlockIcon, SearchIcon } from '../components/Icons';
import { StatTile } from '../components/StatTile';
import { Section, SkeletonGrid } from '../components/States';
import { Badge, StatusBadge } from '../components/StatusBadge';
import { pilotHref } from '../config/env';
import { count, humanize, percent } from '../lib/format';
import { OUTCOME, podStatus } from '../lib/status';

const BLOCKS = [
  {
    icon: 'skills' as const,
    title: 'Skills',
    text: 'One small, reusable AI capability, such as requirement review or unit tests. Works for any technology.',
  },
  {
    icon: 'workflows' as const,
    title: 'Workflows',
    text: 'Skills chained in order with human gates, for example requirement, design, code, tests, pull request.',
  },
  {
    icon: 'pods' as const,
    title: 'Pods',
    text: 'Ready-made AI-augmented teams, for example a Solution Architect, a Full-stack developer and a QA agent with their workflows.',
  },
  {
    icon: 'harness' as const,
    title: 'Quality harness',
    text: 'Checks every output against the client system, scores confidence and stops for a person when needed.',
  },
];

/** Home: Business (board HomeBusiness; SDD-09 §4.3). Class A data only. */
export default function HomeBusiness() {
  const navigate = useNavigate();
  const summary = useSummary();
  const business = useBusiness('90d');
  const pods = usePods({ limit: 3, sort: 'featured' });
  const [q, setQ] = useState('');
  const pilot = pilotHref('Request a pilot: AI-augmented pod');

  function search(e: FormEvent) {
    e.preventDefault();
    navigate(q.trim() ? `/skills?q=${encodeURIComponent(q.trim())}` : '/skills');
  }

  return (
    <div>
      <section className="band-primary on-primary">
        <div className="tm-wrap hero-pad row gap-24" style={{ gap: 48 }}>
          <div className="stack gap-20" style={{ flex: '1 1 520px', minWidth: 0 }}>
            <span className="tm-badge b-on-primary self-start">Truminds AI Skill Library</span>
            <PageTitle title="Home" className="hero-h1">
              Reusable AI skills that deliver the whole SDLC, with proof at every step
            </PageTitle>
            <p className="hero-lead">
              Small, technology-independent skills for every role, chained into workflows and
              packaged as AI-augmented pods. Every output is checked against the client&apos;s
              system before a person signs it off.
            </p>
            <div className="row gap-12">
              <Link className="tm-btn btn-accent" to="/how-it-works">
                See how it works
              </Link>
              <Link className="tm-btn btn-light" to="/pods">
                Explore pods
              </Link>
            </div>
          </div>
          <div
            className="tm-card stack gap-10"
            style={{ flex: '1 1 420px', maxWidth: 520, color: 'var(--tm-text)', padding: 24 }}
          >
            <p className="m-0 strong" style={{ fontSize: 16, marginBottom: 4 }}>
              Every artifact is checked before it moves on
            </p>
            <div className="check-row">
              <span className="body strong">Requirement review</span>
              <StatusBadge status={OUTCOME.PASS} suffix="High confidence" />
            </div>
            <div className="check-row">
              <span className="body strong">Design</span>
              <StatusBadge status={OUTCOME['PASS-WITH-FINDINGS']} />
            </div>
            <div className="check-row">
              <span className="body strong">Code and unit tests</span>
              <StatusBadge status={OUTCOME.PASS} />
            </div>
            <div className="check-row">
              <span className="body strong">Security review</span>
              <StatusBadge status={OUTCOME.PASS} />
            </div>
            <div className="check-row">
              <span className="body strong">Pull request</span>
              <StatusBadge status={{ tone: 'input', word: 'Waiting for human review' }} />
            </div>
            <Badge tone="navy" className="self-start">
              Example
            </Badge>
          </div>
        </div>
      </section>

      <section className="tm-wrap pt-48 pb-24" aria-labelledby="impact-h">
        <SectionHead
          id="impact-h"
          eyebrow="Impact"
          title="The library at a glance"
          sub="Aggregates from the Insights service. Sales-safe: no client names, tickets or repositories."
        />
        <div className="grid g-220 mt-24">
          <Section query={summary} skeleton={<SkeletonGrid count={2} />}>
            {(s) => (
              <>
                <StatTile
                  size="xl"
                  label="Skills in production"
                  value={count(s.data.skills_in_production)}
                  sub={`across ${s.data.roles_covered} roles and ${s.data.phases_covered} SDLC phases`}
                />
                <StatTile
                  size="xl"
                  label="Ready-made pods"
                  value={count(s.data.pods_ready)}
                  sub="AI-augmented delivery teams"
                />
              </>
            )}
          </Section>
          <Section query={business} skeleton={<SkeletonGrid count={2} />}>
            {(b) => (
              <>
                <StatTile
                  size="xl"
                  label="First-try pass rate"
                  value={percent(b.data.first_try_pass.value)}
                  tone="pass"
                  sub="outputs passing every quality check first time"
                />
                <StatTile
                  size="xl"
                  label="Pull requests delivered"
                  value={count(b.data.prs_delivered.value)}
                  sub="reviewed and merged by people, last 90 days"
                />
              </>
            )}
          </Section>
        </div>
      </section>

      <section className="tm-wrap pt-48 pb-24">
        <SectionHead
          eyebrow="How it is built"
          title="What is inside the library"
          sub="Four building blocks. Engineers use them in Claude Code; everyone can browse them here."
        />
        <div className="grid g-240 mt-24">
          {BLOCKS.map((b) => (
            <div className="tm-card stack gap-10" key={b.title}>
              <span className="tm-icon">
                <BlockIcon kind={b.icon} />
              </span>
              <h3 className="h3">{b.title}</h3>
              <p className="body text-2 m-0">{b.text}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="tm-wrap pt-48 pb-24">
        <SectionHead
          eyebrow="Explore"
          title="Find skills by role"
          sub="Pick a role to see its skills, or search by task, SDLC phase or domain."
        />
        <form role="search" aria-label="Search skills by task" onSubmit={search} className="mt-24">
          <label className="search-large">
            <SearchIcon size={18} />
            <span className="sr-only">Search skills</span>
            <input
              type="search"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder='Try "threat model", "test plan", "QA", "estimate"'
            />
          </label>
        </form>
        <Section query={summary} skeleton={<SkeletonGrid count={8} height={72} cls="g-260" />}>
          {(s) => (
            <>
              <ul className="plain-list grid g-260 mt-16">
                {s.data.roles.map((r) => (
                  <li key={r.id}>
                    <Link
                      to={`/skills?role=${encodeURIComponent(r.id)}`}
                      className="tm-card role-tile"
                    >
                      <span className="tm-icon navy" aria-hidden="true">
                        {r.code}
                      </span>
                      <span className="stack gap-4">
                        <span className="strong" style={{ fontSize: 15 }}>
                          {r.label}
                        </span>
                        <span className="small text-2">
                          {r.skills_production === 1 ? '1 skill' : `${r.skills_production} skills`}
                          {r.skills_pilot ? ` · ${r.skills_pilot} in pilot` : ''}
                        </span>
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
              {s.data.domains.length > 0 ? (
                <div className="row gap-8 mt-20">
                  <span className="body text-2 strong">Works in any domain:</span>
                  {s.data.domains.map((d) => (
                    <Badge key={d}>{humanize(d)}</Badge>
                  ))}
                </div>
              ) : null}
            </>
          )}
        </Section>
      </section>

      <section className="tm-wrap pt-48 pb-24">
        <SectionHead
          eyebrow="Offerings"
          title="AI-augmented pods"
          sub="Pre-packaged teams you can propose to a client. Each pod lists what it delivers and the human roles that stay accountable."
          aside={
            <Link className="tm-link" to="/pods">
              All pods →
            </Link>
          }
        />
        <Section query={pods} skeleton={<SkeletonGrid count={3} height={200} cls="g-300" />}>
          {(p) =>
            p.data.items.length === 0 ? (
              <p className="body text-2 mt-16">
                No pods are published yet. Check back after the next catalogue release.
              </p>
            ) : (
              <div className="grid g-300 mt-24">
                {p.data.items.map((pod) => (
                  <article className="tm-card stack gap-12" key={pod.id}>
                    <div className="row between gap-8">
                      <h3 className="h3">{pod.title}</h3>
                      <StatusBadge status={podStatus(pod.status)} />
                    </div>
                    {pod.summary ? <p className="body text-2 m-0">{pod.summary}</p> : null}
                    <div className="row gap-6">
                      {pod.agents.map((a) => (
                        <Badge key={a}>{a}</Badge>
                      ))}
                    </div>
                    <Link className="tm-link self-start" to={`/pods/${pod.id}`}>
                      View pod<span className="sr-only">: {pod.title}</span> →
                    </Link>
                  </article>
                ))}
              </div>
            )
          }
        </Section>
      </section>

      <section className="band-soft" style={{ marginTop: 48 }}>
        <div className="tm-wrap row between gap-24" style={{ paddingTop: 48, paddingBottom: 56 }}>
          <SectionHead
            eyebrow="Next step"
            title="Bring an AI-augmented pod to your next engagement"
            sub="Share the capability map with a client, or ask the AI practice to scope a pilot."
          />
          <div className="row gap-12">
            <Link className="tm-btn btn-primary" to="/insights">
              Open capability map
            </Link>
            {pilot ? (
              <a className="tm-btn btn-ghost" href={pilot}>
                Request a pilot
              </a>
            ) : null}
          </div>
        </div>
      </section>
    </div>
  );
}
