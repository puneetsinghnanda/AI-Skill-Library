import { Link } from 'react-router-dom';
import { usePodMetrics, usePods } from '../api/queries';
import type { PodCard, PodMetrics } from '../api/types';
import { useView } from '../app/ViewContext';
import { PageTitle } from '../components/Heading';
import { EmptyState, Section, SkeletonGrid } from '../components/States';
import { Badge, StatusBadge } from '../components/StatusBadge';
import { percent } from '../lib/format';
import { podStatus } from '../lib/status';

function passText(m: PodMetrics | undefined): string {
  if (!m) return '…';
  if (m.status === 'no_data') return 'Not enough runs yet';
  return percent(m.first_try_pass) ?? 'No data yet';
}

/** Business track record on a card. Viewer-only callers get it on the card (SDD-10 §6.1); other
 * roles fetch E10 for it. */
function CardPass({ pod }: { pod: PodCard }) {
  const metrics = usePodMetrics(pod.id, 'all', pod.metrics === undefined);
  return <>{passText(pod.metrics ?? metrics.data?.data)}</>;
}

/** Pods (board Pods; SDD-09 §4.9). */
export default function Pods() {
  const { view } = useView();
  const eng = view === 'engineer';
  const pods = usePods({ limit: 100 });
  return (
    <div className="pb-56">
      <section className="band-surface">
        <div className="tm-wrap" style={{ paddingTop: 40, paddingBottom: 32 }}>
          <p className="tm-eyebrow">Pods</p>
          <PageTitle title="Pods">AI-augmented pods</PageTitle>
          <p className="tm-sub">
            A pod is a ready-made delivery team: AI agents for each role, the workflows they run,
            and the people who stay accountable.{' '}
            {eng
              ? 'Engineers see the workflows and skills inside each pod.'
              : 'Sales sees what each pod delivers and where it fits.'}
          </p>
          <div className="grid g-260 mt-24">
            <div className="persona-strip">
              <p className="m-0 small strong" style={{ color: 'var(--tm-primary)' }}>
                Business unit and sales
              </p>
              <p className="body" style={{ margin: '6px 0 0' }}>
                Choose and propose a pod, show its outcomes, request a pilot.
              </p>
            </div>
            <div className="persona-strip">
              <p className="m-0 small strong" style={{ color: 'var(--tm-primary)' }}>
                Engineers and tech leads
              </p>
              <p className="body" style={{ margin: '6px 0 0' }}>
                Run the pod&apos;s workflows in Claude Code; approve its gates.
              </p>
            </div>
            <div className="persona-strip">
              <p className="m-0 small strong" style={{ color: 'var(--tm-primary)' }}>
                Delivery managers and program owners
              </p>
              <p className="body" style={{ margin: '6px 0 0' }}>
                Track the pod&apos;s runs, waiting decisions and quality.
              </p>
            </div>
          </div>
        </div>
      </section>

      <section className="tm-wrap pt-28">
        <Section query={pods} skeleton={<SkeletonGrid count={4} height={300} cls="g-380" />}>
          {(p) =>
            p.data.items.length === 0 ? (
              <EmptyState title="No pods are published yet">
                Pods appear here after the next catalogue release.
              </EmptyState>
            ) : (
              <div className="grid g-380">
                {p.data.items.map((pod) => (
                  <article className="tm-card stack gap-14" style={{ padding: 24 }} key={pod.id}>
                    <div className="row between gap-10">
                      <h2 className="h2-sm">{pod.title}</h2>
                      <StatusBadge status={podStatus(pod.status)} />
                    </div>
                    {pod.summary ? <p className="body text-2 m-0">{pod.summary}</p> : null}
                    <div>
                      <p className="xsmall strong text-2" style={{ margin: '0 0 6px' }}>
                        AI AGENTS IN THE POD
                      </p>
                      <div className="row gap-6">
                        {pod.agents.map((a) => (
                          <Badge key={a}>{a}</Badge>
                        ))}
                      </div>
                    </div>
                    {eng ? (
                      <div className="row gap-6">
                        {(pod.workflows ?? []).map((w) => (
                          <Badge key={w} tone="teal" mono>
                            {w}
                          </Badge>
                        ))}
                        {pod.skill_count !== undefined ? (
                          <Badge tone="retry">
                            {pod.skill_count} {pod.skill_count === 1 ? 'skill' : 'skills'}
                          </Badge>
                        ) : null}
                      </div>
                    ) : (
                      <div className="grid" style={{ gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                        {pod.best_for ? (
                          <div className="inset">
                            <p className="m-0 xsmall text-2">Best for</p>
                            <p className="body strong" style={{ margin: '2px 0 0' }}>
                              {pod.best_for}
                            </p>
                          </div>
                        ) : null}
                        <div className="inset">
                          <p className="m-0 xsmall text-2">First-try pass</p>
                          <p className="body strong" style={{ margin: '2px 0 0' }}>
                            <CardPass pod={pod} />
                          </p>
                        </div>
                      </div>
                    )}
                    {pod.people.filter(Boolean).length ? (
                      <p className="m-0 small text-2">
                        People accountable: {pod.people.filter(Boolean).join(', ')}
                      </p>
                    ) : null}
                    <Link className="tm-btn btn-ghost self-start" to={`/pods/${pod.id}`}>
                      View pod<span className="sr-only">: {pod.title}</span>
                    </Link>
                  </article>
                ))}
              </div>
            )
          }
        </Section>

        <div className="tm-card dashed row between gap-16" style={{ marginTop: 28 }}>
          <div>
            <div className="row gap-8">
              <h2 className="h3">Build your own pod</h2>
              <Badge tone="input">Phase 3</Badge>
            </div>
            <p className="body text-2" style={{ margin: '6px 0 0' }}>
              Assemble agents and workflows into a custom pod for a client. Coming after Release 1
              usage data.
            </p>
          </div>
          <Link className="tm-btn btn-ghost" to="/pods/builder">
            Preview the builder
          </Link>
        </div>
      </section>
    </div>
  );
}
