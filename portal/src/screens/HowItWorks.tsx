import { useView } from '../app/ViewContext';
import { CodeChip } from '../components/CodeChip';
import { PageTitle, SectionHead } from '../components/Heading';
import { Badge, StatusBadge } from '../components/StatusBadge';
import { FLOW, OUTCOMES, STEPS, WHERE } from '../content/how-it-works';
import { OUTCOME } from '../lib/status';

/** How it works (board HowItWorks; SDD-09 §4.5). Static content; no data API besides /v1/me. */
export default function HowItWorks() {
  const { view } = useView();
  const eng = view === 'engineer';
  return (
    <div className="pb-56">
      <section className="band-primary on-primary">
        <div className="tm-wrap stack gap-24" style={{ paddingTop: 56, paddingBottom: 56 }}>
          <div>
            <p className="tm-eyebrow">How it works</p>
            <PageTitle title="How it works" className="page-h1 hero-h1-md">
              From a client ticket to a reviewed pull request
            </PageTitle>
            <p className="hero-lead mt-12" style={{ maxWidth: 820, fontSize: 17 }}>
              AI does the work one step at a time, every step is checked, and people make the
              decisions.
            </p>
          </div>
          <ol aria-label="The flow at a glance" className="flow-strip">
            {FLOW.map((f) => (
              <li key={f.title} className={f.highlight ? 'hl' : ''}>
                <p className="t">{f.title}</p>
                <p className="d">{f.hint}</p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section className="tm-wrap pt-48">
        <SectionHead
          eyebrow="The flow"
          title="Seven steps, end to end"
          sub={`The same flow for greenfield and brownfield work, in any domain. ${
            eng
              ? 'Showing the commands each step uses.'
              : 'Showing what each step means for the client.'
          }`}
        />
        <ol className="plain-list stack gap-14 mt-24">
          {STEPS.map((s, i) => (
            <li key={s.title} className="tm-card row align-start gap-20">
              <span className={`num ${i === 3 ? 'accent' : ''}`} aria-hidden="true">
                {i + 1}
              </span>
              <div style={{ flex: '1 1 520px', minWidth: 0 }}>
                <div className="row gap-10">
                  <h3 className="h3">
                    <span className="sr-only">Step {i + 1}: </span>
                    {s.title}
                  </h3>
                  <Badge>{s.who}</Badge>
                </div>
                <p className="body text-2" style={{ margin: '8px 0 0' }}>
                  {s.desc}
                </p>
              </div>
              <div className="stack gap-6" style={{ flex: '0 1 380px', minWidth: 0 }}>
                <span className="xsmall strong text-2">
                  {eng ? 'You run or see' : 'For the client'}
                </span>
                {eng ? (
                  s.commands.map((c) => <CodeChip key={c} code={c} />)
                ) : (
                  <span className="body inset" style={{ background: 'var(--tm-primary-soft)' }}>
                    {s.client}
                  </span>
                )}
              </div>
            </li>
          ))}
        </ol>
      </section>

      <section className="tm-wrap pt-48">
        <SectionHead
          eyebrow="Quality"
          title="What the harness can decide after each step"
          sub="Code makes the decision, not the AI. Confidence (High, Medium, Low) decides how much needs a person."
        />
        <div className="grid g-190 mt-20">
          {OUTCOMES.map((o) => (
            <div className="tm-card" key={o.outcome}>
              <StatusBadge status={OUTCOME[o.outcome]} />
              <p className="small text-2" style={{ margin: '8px 0 0' }}>
                {o.text}
              </p>
            </div>
          ))}
        </div>
      </section>

      <section className="tm-wrap pt-48">
        <SectionHead
          eyebrow="Trust"
          title="Where things live"
          sub="Clear boundaries keep client code safe."
        />
        <div className="grid g-280 mt-20">
          {WHERE.map((w) => (
            <div className="tm-card stack gap-8" key={w.title}>
              <h3 className="h3">{w.title}</h3>
              <p className="body text-2 m-0">{w.text}</p>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
