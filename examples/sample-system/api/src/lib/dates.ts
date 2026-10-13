const DAY_MS = 24 * 60 * 60 * 1000;

/** The moment `days` days before `now`. */
export function daysAgo(days: number, now: Date = new Date()): Date {
  return new Date(now.getTime() - days * DAY_MS);
}

/** ISO text for a Date read from a `timestamp` column (or null). */
export function toIso(value: Date | null): string | null {
  return value ? value.toISOString() : null;
}
