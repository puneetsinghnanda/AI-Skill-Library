import { badRequest } from './errors';

const DAY = /^\d{4}-\d{2}-\d{2}$/;
const ID = /^[1-9]\d{0,9}$/;

/** A `YYYY-MM-DD` query value, or undefined when absent. */
export function parseDay(value: unknown, name: string): string | undefined {
  if (value === undefined || value === '') return undefined;
  if (typeof value !== 'string' || !DAY.test(value) || Number.isNaN(Date.parse(value))) {
    throw badRequest(`${name} must be a date in YYYY-MM-DD form`);
  }
  return value;
}

/** A positive integer id from a path or query value. */
export function parseId(value: unknown, name: string): number {
  if (typeof value !== 'string' || !ID.test(value)) throw badRequest(`${name} must be a positive integer`);
  return Number(value);
}

export function parseOptionalId(value: unknown, name: string): number | undefined {
  return value === undefined || value === '' ? undefined : parseId(value, name);
}

export function parsePage(value: unknown): number {
  return value === undefined || value === '' ? 1 : parseId(value, 'page');
}
