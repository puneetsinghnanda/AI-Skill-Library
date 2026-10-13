import { createHash } from 'node:crypto';
import { orderTotalCents } from '../../api/src/lib/price';

/**
 * Deterministic seed data for Order Tracker. Everything here is invented:
 * customers are "Test Customer NNN" with custNNN@example.test emails.
 * Same seed and anchor give the same rows (TC-SAM-002).
 */

export const DEFAULT_SEED = 20240611;
export const DEFAULT_ANCHOR = '2026-09-30T12:00:00Z';

export interface SeedCustomer { id: number; code: string; displayName: string; email: string }
export interface SeedProduct { id: number; sku: string; name: string; priceCents: number }
export interface SeedItem { productId: number; quantity: number; unitPriceCents: number }
export interface SeedStatusChange { fromStatus: string | null; toStatus: string; changedAt: string }
export interface SeedOrder {
  id: number;
  customerId: number;
  status: string;
  totalCents: number;
  createdAt: string;
  archivedAt: string | null;
  items: SeedItem[];
  history: SeedStatusChange[];
  shipment: { carrierCode: string; shippedAt: string } | null;
}
export interface SeedEvent { orderId: number; status: string; createdAt: string }
export interface SeedData {
  customers: SeedCustomer[];
  products: SeedProduct[];
  orders: SeedOrder[];
  events: SeedEvent[];
}

const ADJECTIVES = ['Blue', 'Compact', 'Classic', 'Large', 'Small', 'Recycled', 'Steel', 'Bamboo', 'Canvas', 'Glass'];
const NOUNS = ['Notebook', 'Water Bottle', 'Desk Lamp', 'Backpack', 'Mug'];
const CARRIERS = ['CARRIER-A', 'CARRIER-B', 'CARRIER-C'];
const HOUR = 3_600_000;
const DAY = 24 * HOUR;
const MONTHS_OF_ORDERS = 30;
const ORDER_COUNT = 5000;

/** mulberry32: small, fast, deterministic PRNG. */
function rng(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** UTC wall-clock text for a `timestamp` column: "YYYY-MM-DD HH:MM:SS". */
export function dbTimestamp(ms: number): string {
  return new Date(ms).toISOString().slice(0, 19).replace('T', ' ');
}

function pad(n: number, width: number): string {
  return String(n).padStart(width, '0');
}

export function resolveAnchor(value: string | undefined): number {
  if (!value) return Date.parse(DEFAULT_ANCHOR);
  if (value === 'now') return Date.now();
  const ms = Date.parse(value);
  if (Number.isNaN(ms)) throw new Error(`SEED_ANCHOR is not a valid timestamp: ${value}`);
  return ms;
}

export function generateSeed(seed: number = DEFAULT_SEED, anchorMs: number = Date.parse(DEFAULT_ANCHOR)): SeedData {
  const rand = rng(seed);
  const int = (min: number, max: number): number => min + Math.floor(rand() * (max - min + 1));
  const pick = <T>(list: readonly T[]): T => list[Math.floor(rand() * list.length)] as T;

  const customers: SeedCustomer[] = [];
  for (let i = 1; i <= 200; i++) {
    customers.push({
      id: i,
      code: `CUST-${pad(i, 3)}`,
      displayName: `Test Customer ${pad(i, 3)}`,
      email: `cust${pad(i, 3)}@example.test`,
    });
  }

  const products: SeedProduct[] = [];
  for (let i = 1; i <= 50; i++) {
    const adjective = ADJECTIVES[(i - 1) % ADJECTIVES.length] as string;
    const noun = NOUNS[Math.floor((i - 1) / ADJECTIVES.length)] as string;
    products.push({ id: i, sku: `SKU-${pad(i, 4)}`, name: `${adjective} ${noun}`, priceCents: int(199, 9999) });
  }

  const span = MONTHS_OF_ORDERS * 30 * DAY;
  const createdTimes: number[] = [];
  for (let i = 0; i < ORDER_COUNT; i++) createdTimes.push(anchorMs - Math.floor(rand() * span));
  createdTimes.sort((a, b) => a - b);

  const orders: SeedOrder[] = [];
  const events: SeedEvent[] = [];
  const archiveCutoff = anchorMs - 24 * 30 * DAY;

  createdTimes.forEach((created, index) => {
    const id = index + 1;
    const customer = pick(customers);
    const lineCount = int(1, 4);
    const used = new Set<number>();
    const items: SeedItem[] = [];
    while (items.length < lineCount) {
      const product = pick(products);
      if (used.has(product.id)) continue;
      used.add(product.id);
      items.push({ productId: product.id, quantity: int(1, 5), unitPriceCents: product.priceCents });
    }

    const age = anchorMs - created;
    const path: string[] = ['PLACED'];
    if (age > 2 * HOUR) path.push('PACKED');
    if (age > DAY) path.push('SHIPPED');
    if (age > 4 * DAY) path.push('DELIVERED');
    // Orders older than 18 months came from the old export, which wrote SHIPPD.
    if (age > 18 * 30 * DAY && path.length === 4) path.splice(2, 2, 'SHIPPD');

    const history: SeedStatusChange[] = [];
    let at = created;
    path.forEach((status, step) => {
      if (step > 0) at += int(1, 20) * HOUR;
      history.push({ fromStatus: step === 0 ? null : (path[step - 1] as string), toStatus: status, changedAt: dbTimestamp(Math.min(at, anchorMs)) });
    });

    const shipped = history.find((h) => h.toStatus === 'SHIPPED' || h.toStatus === 'SHIPPD');
    const status = path[path.length - 1] as string;
    orders.push({
      id,
      customerId: customer.id,
      status,
      totalCents: orderTotalCents(items),
      createdAt: dbTimestamp(created),
      archivedAt: created < archiveCutoff ? dbTimestamp(anchorMs - DAY) : null,
      items,
      history,
      shipment: shipped ? { carrierCode: pick(CARRIERS), shippedAt: shipped.changedAt } : null,
    });

    // The activity feed only holds the last 24 hours (purge-events job).
    for (const h of history) {
      if (Date.parse(`${h.changedAt.replace(' ', 'T')}Z`) >= anchorMs - DAY) {
        events.push({ orderId: id, status: h.toStatus, createdAt: h.changedAt });
      }
    }
  });

  return { customers, products, orders, events };
}

/** SHA-256 over the canonical JSON of the generated rows; used by the determinism test. */
export function seedHash(data: SeedData): string {
  return createHash('sha256').update(JSON.stringify(data)).digest('hex');
}
