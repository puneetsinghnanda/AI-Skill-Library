import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useRun } from '../api/queries';
import type { CheckRecord, RunDetail as Run, RunStep, SignalValue } from '../api/types';
import { useView } from '../app/ViewContext';
import { CodeChip } from '../components/CodeChip';
import { PageTitle } from '../components/Heading';
import { EmptyState, ErrorState, Skeleton } from '../components/States';
import { Badge, StatusBadge } from '../components/StatusBadge';
import { TableRegion } from '../components/TableRegion';
import { askRoleLabel, SIGNAL_LABELS, signalLabel } from '../content/labels';
import { compactTokens, duration, localTime, usd } from '../lib/format';
import {
  bandStatus,
  ciStatus,
  outcomeStatus,
  packStatus,
  prStatus,
  runStatus,
} from '../lib/status';

function signalText(code: string, v: SignalValue | undefined): string {
  if (v === undefined || v === null) return '—';
  if (typeof v === 'object') {
    const lines = v.lines ?? 0;
    const files = v.files ?? 0;
    const base = lines === 0 && files === 0 ? 'no code change' : `${lines} lines, ${files} files`;
    return v.sensitive ? `${base}, sensitive paths` : base;
  }
  if (typeof v === 'number' && code === 'S1') return v.toFixed(2);
  return String(v);
}

function lastRecord(step: RunStep): CheckRecord | null {
  for (let i = step.attempts.length - 1; i >= 0; i--) {
    const r = step.attempts[i]?.record;
    if (r) return r;
  }
  return null;
}

function RecordPanel({ step }: { step: RunStep | undefined }) {
  if (!step) {
    return (
      <div className="tm-card stack gap-10">
        <h2 className="h3 sm">Check record</h2>
        <p className="body text-2 m-0">No step has a check record yet.</p>
      </div>
    );
  }
  const rec = lastRecord(step);
  const st = outcomeStatus(step.outcome, step.attempt_count);
  return (
    <div className="tm-card stack gap-10" aria-live="polite">
      <h2 className="h3 sm">Check record · {step.step_id}</h2>
      {rec ? (
        <>
          <p className="m-0 small text-2">
            Decided by {rec.decided_by ?? 'tsl'} · signed{' '}
            {rec.key_id ? <span className="mono">{rec.key_id}</span> : 'key unknown'} · {st.word}
          </p>
          <dl className="kv m-0">
            {Object.keys(SIGNAL_LABELS).map((code) => (
              <div key={code} style={{ display: 'contents' }}>
                <dt>{signalLabel(code)}</dt>
                <dd>{signalText(code, rec.signals?.[code])}</dd>
              </div>
            ))}
          </dl>
          <p className="m-0 xsmall text-2">
            {rec.gate_failures.length
              ? `Hard gates failed: ${rec.gate_failures.join(', ')}. `
              : 'Hard gates passed. '}
            {rec.caps.length ? `Caps: ${rec.caps.join(', ')}. ` : ''}
            Findings: {rec.findings.blocker ?? 0} blocker, {rec.findings.major ?? 0} major,{' '}
            {rec.findings.minor ?? 0} minor.
          </p>
          {rec.reasons.length ? (
            <p className="m-0 xsmall text-2">
              Reasons: {rec.reasons.map((r) => `${r.label} (${r.code})`).join(', ')}
            </p>
          ) : null}
          <p className="m-0 xsmall text-2">
            Findings dropped by code (no valid citation):{' '}
            {rec.findings_dropped.length ? rec.findings_dropped.join(', ') : 'none'}
            {rec.ci_verified === null
              ? ''
              : rec.ci_verified
                ? ' · CI re-check passed'
                : ' · CI re-check failed'}
          </p>
        </>
      ) : (
        <p className="body text-2 m-0">This step has no check record yet.</p>
      )}
    </div>
  );
}

function RunBody({ d }: { d: Run }) {
  const r = d.run;
  const withRecords = d.steps.filter((s) => lastRecord(s) !== null);
  const [selected, setSelected] = useState<string | null>(
    withRecords[withRecords.length - 1]?.step_id ?? null,
  );
  const sel = d.steps.find((s) => s.step_id === selected);
  const engineer = r.engineer.display_name ?? r.engineer.pseudonym ?? 'unknown';
  const pack = packStatus(d.pack.status);
  const actionAmber = r.next_action.kind === 'answer_questions' || r.next_action.kind === 'approve';

  return (
    <>
      <section className="band-surface">
        <div className="tm-wrap stack gap-12" style={{ paddingTop: 28, paddingBottom: 24 }}>
          <Link className="tm-link self-start" to="/insights">
            ← Monitoring
          </Link>
          <div className="row between align-start gap-16">
            <div style={{ minWidth: 0 }}>
              <div className="row gap-10">
                <PageTitle title={`Run ${r.run_id}`} className="m-0 mono">
                  <span style={{ fontSize: 26, overflowWrap: 'anywhere' }}>{r.run_id}</span>
                </PageTitle>
                <StatusBadge status={runStatus(r.status_label)} />
              </div>
              <p className="body text-2" style={{ margin: '8px 0 0' }}>
                {[
                  r.ticket_ref,
                  r.workflow
                    ? `${r.workflow}${r.workflow_version ? ` ${r.workflow_version}` : ''}`
                    : null,
                  r.system ? `system ${r.system}` : null,
                  `engineer ${engineer}`,
                  `context pack ${pack.word.toLowerCase()}${d.pack.signed_by ? ` (signed by ${d.pack.signed_by})` : ''}`,
                ]
                  .filter(Boolean)
                  .join(' · ')}
              </p>
              {r.is_partial ? (
                <p className="small" style={{ margin: '6px 0 0' }}>
                  <Badge tone="input">Some events have not arrived yet</Badge>
                </p>
              ) : null}
            </div>
            <div className="row gap-10">
              <CodeChip code={r.run_id} />
              <a
                className="tm-btn btn-ghost"
                href={d.links.companion_runs_url}
                rel="noreferrer noopener"
              >
                Companion repo
              </a>
            </div>
          </div>
        </div>
      </section>

      <div className="tm-wrap pt-24 split">
        <div className="main" style={{ gap: 20 }}>
          <div className={`tm-card row between gap-16 ${actionAmber ? 'amber' : ''}`.trim()}>
            <div>
              <p
                className="m-0 strong"
                style={{ fontSize: 15, color: actionAmber ? 'var(--tm-input-ink)' : undefined }}
              >
                Next action
              </p>
              <p className="body" style={{ margin: '4px 0 0' }}>
                {r.next_action.text}
              </p>
            </div>
            {r.next_action.command ? <CodeChip code={r.next_action.command} /> : null}
          </div>

          <TableRegion label="Steps of this run" minWidth={760}>
            <thead>
              <tr>
                <th scope="col">#</th>
                <th scope="col">Step</th>
                <th scope="col">Skill</th>
                <th scope="col">Outcome</th>
                <th scope="col">Confidence</th>
                <th scope="col">Attempts</th>
                <th scope="col">Record</th>
              </tr>
            </thead>
            <tbody>
              {d.steps.map((s, i) => {
                const band = bandStatus(s.band);
                const has = lastRecord(s) !== null;
                return (
                  <tr key={s.step_id} className={s.step_id === selected ? 'selected' : undefined}>
                    <td>{s.seq ?? i + 1}</td>
                    <td className="strong">{s.step_id}</td>
                    <td className="mono" style={{ fontSize: 13 }}>
                      {s.kind === 'gate' ? 'human gate' : (s.skill_id ?? '—')}
                      {s.skill_version ? ` ${s.skill_version}` : ''}
                    </td>
                    <td>
                      <StatusBadge status={outcomeStatus(s.outcome, s.attempt_count)} />
                    </td>
                    <td>{band ? <StatusBadge status={band} /> : '—'}</td>
                    <td>{s.attempt_count || '—'}</td>
                    <td>
                      {has ? (
                        <button
                          type="button"
                          className="tm-link"
                          aria-pressed={s.step_id === selected}
                          onClick={() => setSelected(s.step_id)}
                        >
                          View<span className="sr-only"> check record for {s.step_id}</span>
                        </button>
                      ) : null}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </TableRegion>

          {d.approvals.length ? (
            <TableRegion label="Approvals" minWidth={640}>
              <thead>
                <tr>
                  <th scope="col">Gate</th>
                  <th scope="col">Reason</th>
                  <th scope="col">Requested</th>
                  <th scope="col">Decision</th>
                  <th scope="col">Approver</th>
                  <th scope="col">Recorded</th>
                </tr>
              </thead>
              <tbody>
                {d.approvals.map((a) => (
                  <tr key={a.gate}>
                    <td className="mono">{a.gate}</td>
                    <td>{a.reason_code ? signalLabel(a.reason_code) : '—'}</td>
                    <td>{localTime(a.requested_at) ?? '—'}</td>
                    <td>
                      {a.decision ? <StatusBadge status={outcomeStatus(a.decision)} /> : 'Waiting'}
                    </td>
                    <td className={a.approver?.display_name ? '' : 'mono'}>
                      {a.approver ? (a.approver.display_name ?? a.approver.pseudonym) : '—'}
                    </td>
                    <td>{localTime(a.recorded_at) ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </TableRegion>
          ) : null}

          <div className="grid g-320" style={{ gap: 16 }}>
            <div className="tm-card stack gap-10">
              <h2 className="h3 sm">Pull requests</h2>
              {d.pull_requests.length === 0 ? (
                <p className="body text-2 m-0">
                  No pull request yet. It opens at the end of the run.
                </p>
              ) : (
                <ul className="plain-list stack gap-8">
                  {d.pull_requests.map((p) => (
                    <li key={`${p.repo}-${p.number}`} className="row between gap-8">
                      <a href={p.url} rel="noreferrer noopener">
                        {p.repo} #{p.number}
                      </a>
                      <span className="row gap-6">
                        <StatusBadge status={prStatus(p.state, p.draft)} />
                        <StatusBadge status={ciStatus(p.ci_result)} />
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <div className="tm-card stack gap-10">
              <h2 className="h3 sm">Tokens and cost</h2>
              {d.usage ? (
                <dl className="kv m-0">
                  <dt>Tokens in</dt>
                  <dd>{compactTokens(d.usage.tokens_in)}</dd>
                  <dt>Tokens out</dt>
                  <dd>{compactTokens(d.usage.tokens_out)}</dd>
                  <dt>Cost</dt>
                  <dd>{usd(d.usage.cost_usd)}</dd>
                </dl>
              ) : (
                <p className="body text-2 m-0">No data yet.</p>
              )}
            </div>
          </div>
        </div>

        <aside className="side" aria-label="Check record and open questions" style={{ gap: 16 }}>
          <RecordPanel step={sel} />
          {d.questions.length === 0 ? (
            <div className="tm-card">
              <h2 className="h3 sm">Open questions</h2>
              <p className="body text-2" style={{ margin: '8px 0 0' }}>
                No questions in this run.
              </p>
            </div>
          ) : (
            d.questions.map((q) => (
              <div className="tm-card stack gap-8" key={q.question_id}>
                <h2 className="h3 sm">{q.answered_at ? 'Answered question' : 'Open question'}</h2>
                <StatusBadge
                  className="self-start"
                  status={{ tone: q.answered_at ? 'pass' : 'input', word: q.question_id }}
                  suffix={`${q.blocking ? 'blocking' : 'non-blocking'} · ${askRoleLabel(q.ask_role).toLowerCase()}`}
                />
                <p className="m-0 small text-2">
                  {q.step_id ? `Asked at step ${q.step_id}` : 'Asked during the run'}
                  {q.age_s !== null
                    ? ` · ${q.answered_at ? 'answered after' : 'open for'} ${duration(q.age_s)}`
                    : ''}
                </p>
                {q.evidence_ref ? (
                  <p className="m-0 xsmall text-2">
                    Evidence: <span className="mono">{q.evidence_ref}</span>
                  </p>
                ) : null}
                <a className="tm-link self-start" href={q.file_url} rel="noreferrer noopener">
                  Read and answer in open-questions.md
                </a>
                <p className="m-0 xsmall text-2">The question text stays in the companion repo.</p>
              </div>
            ))
          )}
        </aside>
      </div>
    </>
  );
}

/** Run detail (board RunDetail; SDD-09 §4.14). Engineer view only; Business is redirected. */
export default function RunDetail() {
  const { runId = '' } = useParams();
  const { me } = useView();
  const [names, setNames] = useState(false);
  const run = useRun(runId, names);
  if (run.isPending) {
    return (
      <div className="tm-wrap pt-32 stack gap-24">
        <PageTitle title="Run">Run</PageTitle>
        <Skeleton height={300} />
      </div>
    );
  }
  if (run.isError) {
    return (
      <div className="tm-wrap pt-32 pb-56 stack gap-16">
        <Link className="tm-link self-start" to="/insights">
          ← Monitoring
        </Link>
        <PageTitle title="Run">Run not available</PageTitle>
        <ErrorState error={run.error} />
      </div>
    );
  }
  return (
    <div className="pb-56">
      <RunBody d={run.data.data} key={runId} />
      {me.can_reveal_names ? (
        <div className="tm-wrap pt-20">
          <label className="toggle">
            <input type="checkbox" checked={names} onChange={(e) => setNames(e.target.checked)} />
            Show names
            <span className="xsmall text-2">(each reveal is recorded)</span>
          </label>
        </div>
      ) : null}
      {run.data.data.steps.length === 0 ? (
        <div className="tm-wrap pt-20">
          <EmptyState title="No steps yet">
            The run has started; its steps appear as events arrive.
          </EmptyState>
        </div>
      ) : null}
    </div>
  );
}
