import { describe, expect, it } from 'vitest';
import { formatCents, formatDateTime, statusLabel } from '../lib/format';
import { orderTotalCents, subtotalCents } from '../lib/price';
import { nextStatuses } from '../lib/status';

describe('format', () => {
  it('formats cents as dollars', () => {
    expect(formatCents(2165)).toBe('$21.65');
    expect(formatCents(0)).toBe('$0.00');
  });

  it('formats a timestamp to the minute', () => {
    expect(formatDateTime('2026-09-12T14:30:00.000Z')).toBe('2026-09-12 14:30');
  });

  it('labels the legacy SHIPPD status as Shipped', () => {
    expect(statusLabel('SHIPPD')).toBe('Shipped');
    expect(statusLabel('PLACED')).toBe('Placed');
  });
});

describe('price (single-line orders)', () => {
  it('adds tax to the subtotal', () => {
    expect(subtotalCents([{ quantity: 2, unitPriceCents: 1000 }])).toBe(2000);
    expect(orderTotalCents([{ quantity: 2, unitPriceCents: 1000 }])).toBe(2165);
  });

  it('is zero with no lines', () => {
    expect(orderTotalCents([])).toBe(0);
  });
});

describe('status', () => {
  it('offers the next step only', () => {
    expect(nextStatuses('PLACED')).toEqual(['PACKED']);
    expect(nextStatuses('SHIPPD')).toEqual(['DELIVERED']);
    expect(nextStatuses('DELIVERED')).toEqual([]);
  });
});
