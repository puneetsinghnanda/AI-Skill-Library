import { describe, expect, it } from 'vitest';
import { loadConfig } from '../src/config';
import { parseDay, parseId } from '../src/lib/params';
import { lineTotalCents, orderTotalCents } from '../src/lib/price';
import { canTransition, isOrderStatus, normaliseStatus } from '../src/lib/status';

describe('price', () => {
  it('adds tax and rounds to whole cents', () => {
    expect(lineTotalCents({ quantity: 1, unitPriceCents: 1000 })).toBe(1083);
  });

  it('is zero for an empty order', () => {
    expect(orderTotalCents([])).toBe(0);
  });

  it('totals a single-line order', () => {
    expect(orderTotalCents([{ quantity: 2, unitPriceCents: 1000 }])).toBe(2165);
  });
});

describe('status rules', () => {
  it('follows PLACED -> PACKED -> SHIPPED -> DELIVERED', () => {
    expect(canTransition('PLACED', 'PACKED')).toBe(true);
    expect(canTransition('PACKED', 'SHIPPED')).toBe(true);
    expect(canTransition('SHIPPED', 'DELIVERED')).toBe(true);
    expect(canTransition('DELIVERED', 'PLACED')).toBe(false);
  });

  it('treats the legacy SHIPPD spelling as SHIPPED', () => {
    expect(isOrderStatus('SHIPPD')).toBe(true);
    expect(normaliseStatus('SHIPPD')).toBe('SHIPPED');
    expect(canTransition('PACKED', 'SHIPPD')).toBe(true);
    expect(canTransition('SHIPPD', 'DELIVERED')).toBe(true);
  });
});

describe('params', () => {
  it('accepts YYYY-MM-DD and rejects other forms', () => {
    expect(parseDay('2026-09-01', 'from')).toBe('2026-09-01');
    expect(parseDay(undefined, 'from')).toBeUndefined();
    expect(() => parseDay('2026-9-1', 'from')).toThrow(/YYYY-MM-DD/);
  });

  it('accepts positive integer ids only', () => {
    expect(parseId('12', 'id')).toBe(12);
    expect(() => parseId('0', 'id')).toThrow();
    expect(() => parseId('1e3', 'id')).toThrow();
  });
});

describe('config', () => {
  it('defaults to loopback, port 3000 and 7 days of history', () => {
    expect(loadConfig({})).toMatchObject({ host: '127.0.0.1', port: 3000, orderHistoryDefaultDays: 7, pageSize: 20 });
  });

  it('needs a database location in production', () => {
    expect(() => loadConfig({ NODE_ENV: 'production' })).toThrow(/PGHOST/);
  });
});
