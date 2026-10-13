/**
 * Own SVG/CSS charts with a table view; no chart library (SDD-09 §3.1, §8): role="img" with an
 * aria-label listing the values, plus a "Show as table" toggle.
 */
import { useId, useState } from 'react';
import type { Outcome } from '../api/types';
import { OUTCOME } from '../lib/status';
import { percent } from '../lib/format';
import { StatusBadge } from './StatusBadge';

export interface Datum {
  label: string;
  longLabel?: string;
  value: number;
}

export function BarChart({
  title,
  data,
  unit = '',
}: {
  title: string;
  data: Datum[];
  unit?: string;
}) {
  const [asTable, setAsTable] = useState(false);
  const id = useId();
  const max = Math.max(1, ...data.map((d) => d.value));
  const aria = `${title}: ${data.map((d) => `${d.longLabel ?? d.label} ${d.value}${unit}`).join(', ')}`;
  return (
    <div className="stack gap-14">
      {asTable ? (
        <div className="tm-scroll" role="region" aria-labelledby={`${id}-cap`} tabIndex={0}>
          <table className="tm-table">
            <caption id={`${id}-cap`} className="sr-only">
              {title}
            </caption>
            <thead>
              <tr>
                <th scope="col">Month</th>
                <th scope="col">Value</th>
              </tr>
            </thead>
            <tbody>
              {data.map((d) => (
                <tr key={d.label}>
                  <td>{d.longLabel ?? d.label}</td>
                  <td>{d.value}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div>
          <div className="chart-bars" role="img" aria-label={aria}>
            {data.map((d) => (
              <div className="chart-col" key={d.label} aria-hidden="true">
                <span className="v">{d.value}</span>
                <div className="bar" style={{ height: `${Math.round((d.value / max) * 170)}px` }} />
              </div>
            ))}
          </div>
          <div className="chart-labels" aria-hidden="true">
            {data.map((d) => (
              <span key={d.label}>{d.label}</span>
            ))}
          </div>
        </div>
      )}
      <button
        type="button"
        className="tm-link self-start"
        onClick={() => setAsTable((v) => !v)}
        aria-pressed={asTable}
      >
        {asTable ? 'Show as chart' : 'Show as table'}
      </button>
    </div>
  );
}

/** Horizontal bars with the value as visible text; the bar itself is decorative. */
export function HBars({
  items,
  fill = 'fill-primary',
  mono = false,
  label,
}: {
  items: Datum[];
  fill?: string;
  mono?: boolean;
  label: string;
}) {
  const max = Math.max(1, ...items.map((d) => d.value));
  return (
    <ul className="plain-list hbars" aria-label={label}>
      {items.map((d) => (
        <li key={d.label} style={{ display: 'contents' }}>
          <span className={mono ? 'mono small' : ''}>{d.label}</span>
          <div className="tm-bar" aria-hidden="true">
            <span className={fill} style={{ width: `${Math.round((d.value / max) * 100)}%` }} />
          </div>
          <span className="n">{d.value}</span>
        </li>
      ))}
    </ul>
  );
}

const OUTCOME_FILL: Record<Outcome, string> = {
  PASS: 'fill-pass',
  'PASS-WITH-FINDINGS': 'fill-find',
  RETRY: 'fill-retry',
  'NEEDS-INPUT': 'fill-input',
  ESCALATE: 'fill-esc',
  ABORT: 'fill-abort',
};

const ORDER: Outcome[] = [
  'PASS',
  'PASS-WITH-FINDINGS',
  'RETRY',
  'NEEDS-INPUT',
  'ESCALATE',
  'ABORT',
];

/** Step-outcome bar (M-14): stacked shares plus a badge with the word for each outcome. */
export function OutcomeBar({ shares }: { shares: Record<Outcome, number | null> }) {
  const parts = ORDER.map((o) => ({ o, v: shares[o] ?? 0 }));
  const aria = `Outcomes: ${parts.map((p) => `${OUTCOME[p.o].word.toLowerCase()} ${percent(p.v)}`).join(', ')}`;
  return (
    <>
      <div className="stacked" role="img" aria-label={aria}>
        {parts.map((p) => (
          <span key={p.o} className={OUTCOME_FILL[p.o]} style={{ width: `${p.v * 100}%` }} />
        ))}
      </div>
      <div className="row gap-8">
        {parts.map((p) => (
          <StatusBadge key={p.o} status={OUTCOME[p.o]} suffix={percent(p.v) ?? '0%'} />
        ))}
      </div>
    </>
  );
}

/** High / Medium / Low band mix bar (M-15). */
export function BandBar({
  mix,
}: {
  mix: { high: number | null; medium: number | null; low: number | null };
}) {
  if (mix.high === null && mix.medium === null && mix.low === null) {
    return <span className="text-2 small">No data yet</span>;
  }
  const aria = `High ${percent(mix.high) ?? '0%'}, Medium ${percent(mix.medium) ?? '0%'}, Low ${percent(mix.low) ?? '0%'}`;
  return (
    <div className="bands" role="img" aria-label={aria}>
      <span className="fill-pass" style={{ width: `${(mix.high ?? 0) * 100}%` }} />
      <span className="fill-find" style={{ width: `${(mix.medium ?? 0) * 100}%` }} />
      <span className="fill-esc" style={{ width: `${(mix.low ?? 0) * 100}%` }} />
    </div>
  );
}
