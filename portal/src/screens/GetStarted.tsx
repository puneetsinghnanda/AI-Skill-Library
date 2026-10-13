import { Link } from 'react-router-dom';
import { useReleases } from '../api/queries';
import { useView } from '../app/ViewContext';
import { CodeChip } from '../components/CodeChip';
import { PageTitle } from '../components/Heading';
import { Badge } from '../components/StatusBadge';
import { env } from '../config/env';
import {
  BEFORE_YOU_START,
  BUSINESS_STEPS,
  developmentSeatCommands,
  engineerSteps,
} from '../content/get-started';

/** Get started (board GetStarted; SDD-09 §4.8). Static, plus the current plugin version. */
export default function GetStarted() {
  const { view } = useView();
  const eng = view === 'engineer';
  const releases = useReleases(1);
  const latest = releases.data?.data.items[0] ?? null;
  const steps = engineerSteps(latest?.plugin_version ?? null);
  return (
    <div className="pb-56">
      <section className="band-primary on-primary">
        <div className="tm-wrap row between gap-24" style={{ paddingTop: 48, paddingBottom: 48 }}>
          <div style={{ flex: '1 1 560px', minWidth: 0 }}>
            <p className="tm-eyebrow">Get started</p>
            <PageTitle title="Get started" className="page-h1">
              {eng
                ? 'Install tsl and start your first run'
                : 'Use the library in your next engagement'}
            </PageTitle>
            <p className="hero-lead mt-12" style={{ maxWidth: 720, fontSize: 16 }}>
              {eng
                ? 'Five steps on your company laptop and Claude seat. The Truminds plugin is already installed for you.'
                : 'How sales and business units take AI-augmented delivery to clients.'}
            </p>
          </div>
          <div
            className="tm-card stack gap-10"
            style={{ flex: '0 1 420px', color: 'var(--tm-text)' }}
          >
            <p className="m-0 small strong text-2">Skill Library repository</p>
            <p className="m-0 mono strong" style={{ fontSize: 15, overflowWrap: 'anywhere' }}>
              {env.marketplaceRepoUrl.replace(/^https?:\/\//, '')}
            </p>
            <p className="m-0 small text-2">
              Skills, workflows, pods, the plugin and the tsl tool. Company GitHub sign-in required.
            </p>
            {latest ? (
              <p className="m-0 small">
                Current plugin version <strong className="mono">{latest.plugin_version}</strong>{' '}
                (release <span className="mono">{latest.tag}</span>)
              </p>
            ) : null}
            <a className="tm-btn btn-primary self-start" href={env.marketplaceRepoUrl}>
              Open on GitHub
            </a>
          </div>
        </div>
      </section>

      {eng ? (
        <section className="tm-wrap pt-40 split">
          <div className="main">
            <ol className="plain-list stack gap-14">
              {steps.map((s, i) => (
                <li
                  key={s.title}
                  className="tm-card row align-start gap-16"
                  style={{ flexWrap: 'nowrap' }}
                >
                  <span className="num sm" aria-hidden="true">
                    {i + 1}
                  </span>
                  <div className="stack gap-8" style={{ flex: 1, minWidth: 0 }}>
                    <h2 className="m-0" style={{ fontSize: 17 }}>
                      <span className="sr-only">Step {i + 1}: </span>
                      {s.title}
                    </h2>
                    <p className="body text-2 m-0">{s.desc}</p>
                    {s.commands.map((c) => (
                      <CodeChip key={c} code={c} />
                    ))}
                  </div>
                </li>
              ))}
            </ol>
            <details className="tm-card">
              <summary className="strong" style={{ cursor: 'pointer', minHeight: 24 }}>
                Development seats only: add the marketplace by hand
              </summary>
              <p className="body text-2">
                Company seats get the plugin from managed settings. Only plugin developers on a
                development seat add the marketplace and install the plugin themselves (DEV-01).
              </p>
              <div className="stack gap-8">
                {developmentSeatCommands(env.marketplaceRepoSlug).map((c) => (
                  <CodeChip key={c} code={c} />
                ))}
              </div>
            </details>
          </div>
          <aside className="side" aria-label="Before you start and help">
            <div className="tm-card stack gap-8">
              <h2 className="m-0" style={{ fontSize: 17 }}>
                Before you start
              </h2>
              <ul className="list">
                {BEFORE_YOU_START.map((b) => (
                  <li key={b}>{b}</li>
                ))}
              </ul>
            </div>
            <HelpCard />
          </aside>
        </section>
      ) : (
        <section className="tm-wrap pt-40 stack gap-20">
          <div className="grid g-260" style={{ gap: 20 }}>
            {BUSINESS_STEPS.map((s, i) => (
              <div key={s.title} className="tm-card stack gap-10">
                <Badge tone="teal" className="self-start">
                  Step {i + 1}
                </Badge>
                <h2 className="m-0" style={{ fontSize: 18 }}>
                  {s.title}
                </h2>
                <p className="body text-2 m-0">{s.text}</p>
                {s.link ? (
                  <Link className="tm-link self-start" to={s.link.to}>
                    {s.link.label}
                  </Link>
                ) : null}
              </div>
            ))}
          </div>
          <HelpCard />
        </section>
      )}
    </div>
  );
}

function HelpCard() {
  return (
    <div className="tm-card stack gap-8" id="help">
      <h2 className="m-0" style={{ fontSize: 17 }}>
        Need help?
      </h2>
      <p className="body text-2 m-0">
        Ask in the AI practice channel, or read the troubleshooting guide in the repository README.
      </p>
    </div>
  );
}
