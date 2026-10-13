import { afterAll, beforeAll, describe, expect, it } from 'vitest';
import { migrate } from '../scripts/migrate';
import { generateSeed, resolveAnchor, seedHash } from '../seed/generate';
import { loadSeed } from '../seed/load';
import { freshDatabase, pgAvailable, type TestDb } from '../testing/test-db';

describe('seed generator (TC-SAM-002)', () => {
  it('is deterministic for the same seed and anchor', () => {
    expect(seedHash(generateSeed())).toBe(seedHash(generateSeed()));
  });

  it('changes when the seed changes', () => {
    expect(seedHash(generateSeed(1))).not.toBe(seedHash(generateSeed(2)));
  });

  it('produces the TST-01 volumes with invented identities only', () => {
    const data = generateSeed();
    expect(data.customers).toHaveLength(200);
    expect(data.products).toHaveLength(50);
    expect(data.orders).toHaveLength(5000);
    expect(data.customers[0]).toMatchObject({ displayName: 'Test Customer 001', email: 'cust001@example.test' });
    expect(data.customers.every((c) => c.email.endsWith('@example.test'))).toBe(true);
  });

  it('keeps the legacy SHIPPD status on old orders', () => {
    expect(generateSeed().orders.some((o) => o.status === 'SHIPPD')).toBe(true);
  });

  it('rejects an invalid anchor', () => {
    expect(() => resolveAnchor('not-a-date')).toThrow(/SEED_ANCHOR/);
  });
});

describe.skipIf(!pgAvailable())('migrate and seed against PostgreSQL 16 (TC-SAM-001)', () => {
  let db: TestDb;
  beforeAll(async () => {
    db = await freshDatabase();
  });
  afterAll(async () => {
    await db.drop();
  });

  it('re-running migrations is a no-op', async () => {
    expect(await migrate(db.pool)).toEqual([]);
  });

  it('loads the full seed', async () => {
    const data = generateSeed();
    await loadSeed(db.pool, data);
    const { rows } = await db.pool.query<{ n: number }>('SELECT count(*)::int AS n FROM orders');
    expect(rows[0]?.n).toBe(5000);
    const next = await db.pool.query<{ id: number }>(
      "INSERT INTO customer (code, display_name, email) VALUES ('CUST-NEW', 'Test Customer New', 'new@example.test') RETURNING id",
    );
    expect(next.rows[0]?.id).toBe(201);
  });
});
