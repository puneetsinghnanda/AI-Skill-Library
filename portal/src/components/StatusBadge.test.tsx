import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import type { Outcome, StatusLabel } from '../api/types';
import {
  OUTCOME,
  bandStatus,
  outcomeStatus,
  packStatus,
  podStatus,
  runStatus,
  skillStatus,
} from '../lib/status';
import { StatTile } from './StatTile';
import { StatusBadge } from './StatusBadge';

describe('StatusBadge (TC-POR-007: a word, never colour alone)', () => {
  const words = [
    ...(Object.keys(OUTCOME) as Outcome[]).map((o) => OUTCOME[o]),
    ...(
      [
        'Running',
        'Needs input',
        'Needs approval',
        'Completed',
        'Aborted',
        'Unknown',
      ] as StatusLabel[]
    ).map(runStatus),
    skillStatus('production'),
    skillStatus('pilot'),
    skillStatus('draft'),
    skillStatus('deprecated'),
    podStatus('production'),
    bandStatus('high')!,
    bandStatus('medium')!,
    bandStatus('low')!,
    packStatus('fresh'),
    packStatus('stale'),
    outcomeStatus(null),
    outcomeStatus('approved'),
  ];

  it.each(words.map((w) => [w.word, w]))(
    '"%s" renders its word and a decorative icon',
    (_w, status) => {
      const { container } = render(<StatusBadge status={status} />);
      const badge = container.querySelector('.tm-badge');
      expect(badge).not.toBeNull();
      expect(badge?.textContent?.trim()).toBe(status.word);
      const svg = badge?.querySelector('svg');
      expect(svg).not.toBeNull();
      expect(svg?.getAttribute('aria-hidden')).toBe('true');
    },
  );

  it('maps Doc 4 status colours to the right tones', () => {
    expect(OUTCOME.PASS.tone).toBe('pass');
    expect(OUTCOME['PASS-WITH-FINDINGS'].tone).toBe('find');
    expect(OUTCOME.RETRY.tone).toBe('retry');
    expect(OUTCOME['NEEDS-INPUT'].tone).toBe('input');
    expect(OUTCOME.ESCALATE.tone).toBe('esc');
    expect(OUTCOME.ABORT.tone).toBe('abort');
    expect(outcomeStatus('PASS', 2).word).toBe('Retry, then pass');
  });
});

describe('StatTile (TC-POR-004: "No data yet", never sample numbers)', () => {
  it('shows No data yet for a null value', () => {
    render(<StatTile label="First-try pass rate" value={null} />);
    expect(screen.getByText('No data yet')).toBeInTheDocument();
  });

  it('shows Not enough data for low volume', () => {
    render(<StatTile label="Pass" value={null} reason="low_volume" />);
    expect(screen.getByText('Not enough data')).toBeInTheDocument();
  });

  it('shows the formatted value otherwise', () => {
    render(<StatTile label="Runs" value="64" />);
    expect(screen.getByText('64')).toBeInTheDocument();
    expect(screen.queryByText('No data yet')).toBeNull();
  });
});
