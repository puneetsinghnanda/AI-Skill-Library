/**
 * Formatters (SDD-09 §3.2 lib/format.ts). The SPA never computes a metric; it only formats one
 * (SDD-09 §1.3). Times show in the viewer's local time with ISO in a tooltip (Doc 4 §6.3).
 */

/** `run_01J9ZK2M4Q8X7T3B5N6R0VWYCD` -> `run_01J9..CD` (Doc 4 §6.3). */
export function shortRunId(id: string): string {
  const m = /^run_(.{4}).*(.{2})$/.exec(id);
  return m ? `run_${m[1]}..${m[2]}` : id;
}

/** Fraction 0-1 -> "82%". Null -> null so the caller shows "No data yet". */
export function percent(v: number | null | undefined, digits = 0): string | null {
  if (v === null || v === undefined || Number.isNaN(v)) return null;
  return `${(v * 100).toFixed(digits)}%`;
}

const nf = new Intl.NumberFormat('en-US');

export function count(v: number | null | undefined): string | null {
  if (v === null || v === undefined || Number.isNaN(v)) return null;
  return nf.format(v);
}

export function decimal(v: number | null | undefined, digits = 1): string | null {
  if (v === null || v === undefined || Number.isNaN(v)) return null;
  return v.toFixed(digits);
}

export function usd(v: number | null | undefined): string | null {
  if (v === null || v === undefined || Number.isNaN(v)) return null;
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(v);
}

export function compactTokens(v: number | null | undefined): string | null {
  if (v === null || v === undefined) return null;
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(2)}M`;
  if (v >= 1_000) return `${Math.round(v / 1_000)}k`;
  return String(v);
}

/** Local date and time, e.g. "13 Oct 2026, 09:30". */
export function localTime(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return d.toLocaleString(undefined, {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function localDate(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return d.toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' });
}

/** Seconds -> "2 days", "3 h", "5 min", "under a minute". */
export function duration(seconds: number | null | undefined): string | null {
  if (seconds === null || seconds === undefined || seconds < 0) return null;
  const min = Math.floor(seconds / 60);
  if (min < 1) return 'under a minute';
  if (min < 60) return `${min} min`;
  const h = Math.floor(min / 60);
  if (h < 24) return `${h} h`;
  const d = Math.floor(h / 24);
  return d === 1 ? '1 day' : `${d} days`;
}

/** "5 min ago", "3 h ago", "2 days ago". */
export function relativeTime(
  iso: string | null | undefined,
  now: Date = new Date(),
): string | null {
  if (!iso) return null;
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return null;
  const s = Math.max(0, Math.round((now.getTime() - t) / 1000));
  const d = duration(s);
  if (d === 'under a minute') return 'just now';
  return d ? `${d} ago` : null;
}

export function daysAgo(days: number | null | undefined): string | null {
  if (days === null || days === undefined) return null;
  if (days === 0) return 'today';
  return days === 1 ? '1 day ago' : `${days} days ago`;
}

/** "2026-04" -> "Apr" and "April 2026". */
export function monthLabel(month: string): { short: string; long: string } {
  const [y, m] = month.split('-').map(Number);
  if (!y || !m) return { short: month, long: month };
  const d = new Date(Date.UTC(y, m - 1, 1));
  return {
    short: d.toLocaleString('en-US', { month: 'short', timeZone: 'UTC' }),
    long: d.toLocaleString('en-US', { month: 'long', year: 'numeric', timeZone: 'UTC' }),
  };
}

/** "product_owner" -> "Product owner"; "solution-architect" -> "Solution architect". */
export function humanize(v: string | null | undefined): string {
  if (!v) return '';
  const s = v.replace(/[_-]+/g, ' ').trim();
  return s.charAt(0).toUpperCase() + s.slice(1);
}

/** Initials for the user chip from the viewer's own name, else the pseudonym ("eng-4f2a" -> "EN"). */
export function initials(displayName: string | null | undefined, pseudonym: string): string {
  if (displayName && displayName.trim()) {
    const parts = displayName.trim().split(/\s+/);
    const a = parts[0]?.[0] ?? '';
    const b = parts.length > 1 ? (parts[parts.length - 1]?.[0] ?? '') : (parts[0]?.[1] ?? '');
    return (a + b).toUpperCase();
  }
  return (
    pseudonym
      .replace(/[^a-z]/gi, '')
      .slice(0, 2)
      .toUpperCase() || '?'
  );
}

export function browserTimeZone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
  } catch {
    return 'UTC';
  }
}
