import { describe, expect, it } from 'vitest';
import {
  compactTokens,
  daysAgo,
  duration,
  humanize,
  initials,
  monthLabel,
  percent,
  relativeTime,
  shortRunId,
} from './format';

describe('format', () => {
  it('shortens run ids as Doc 4 §6.3 shows them', () => {
    expect(shortRunId('run_01J9ZK2M4Q8X7T3B5N6R0VWYCD')).toBe('run_01J9..CD');
    expect(shortRunId('not-a-run')).toBe('not-a-run');
  });

  it('formats fractions as percent and keeps null as null (No data yet)', () => {
    expect(percent(0.82)).toBe('82%');
    expect(percent(0)).toBe('0%');
    expect(percent(null)).toBeNull();
    expect(percent(undefined)).toBeNull();
  });

  it('formats durations and relative times', () => {
    expect(duration(30)).toBe('under a minute');
    expect(duration(300)).toBe('5 min');
    expect(duration(3 * 3600)).toBe('3 h');
    expect(duration(172800)).toBe('2 days');
    const now = new Date('2026-10-13T10:00:00Z');
    expect(relativeTime('2026-10-13T09:55:00Z', now)).toBe('5 min ago');
    expect(relativeTime('2026-10-11T10:00:00Z', now)).toBe('2 days ago');
    expect(relativeTime(null, now)).toBeNull();
    expect(daysAgo(0)).toBe('today');
    expect(daysAgo(5)).toBe('5 days ago');
  });

  it('labels months and humanises codes', () => {
    expect(monthLabel('2026-04')).toEqual({ short: 'Apr', long: 'April 2026' });
    expect(humanize('product_owner')).toBe('Product owner');
    expect(compactTokens(905000)).toBe('905k');
    expect(compactTokens(1_250_000)).toBe('1.25M');
  });

  it('builds user-chip initials from the own name, else the pseudonym', () => {
    expect(initials('Avery Example', 'eng-4f2a')).toBe('AE');
    expect(initials(null, 'eng-4f2a')).toBe('EN');
  });
});
