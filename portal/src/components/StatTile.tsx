import type { ReactNode } from 'react';

export type TileTone = 'pass' | 'input' | 'esc' | 'abort' | undefined;

/**
 * Stat tile: label, value, sub-line. A null value shows "No data yet" (SDD-08 §10.4; Doc 4 §2.0.5,
 * C-09) or "Not enough data" for low volume. Value colour only for status meaning.
 */
export function StatTile({
  label,
  value,
  sub,
  tone,
  size = 'md',
  reason,
}: {
  label: string;
  value: string | null | undefined;
  sub?: ReactNode;
  tone?: TileTone;
  size?: 'md' | 'lg' | 'xl';
  reason?: 'no_data' | 'low_volume';
}) {
  const empty = value === null || value === undefined;
  const sizeClass = size === 'xl' ? 'lg' : size === 'lg' ? '' : 'md';
  return (
    <div className="tm-card stat">
      <p className="stat-label">{label}</p>
      {empty ? (
        <p className="stat-value nodata">
          {reason === 'low_volume' ? 'Not enough data' : 'No data yet'}
        </p>
      ) : (
        <p className={`stat-value ${sizeClass} ${tone ? `tone-${tone}` : ''}`.trim()}>{value}</p>
      )}
      {sub ? <p className="stat-sub">{sub}</p> : null}
    </div>
  );
}
