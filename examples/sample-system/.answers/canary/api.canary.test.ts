import { readFileSync } from 'node:fs';
import path from 'node:path';
import type { Express } from 'express';
import request from 'supertest';
import { afterAll, beforeAll, describe, expect, it } from 'vitest';
import { createApp } from '../../api/src/app';
import { loadConfig } from '../../api/src/config';
import type { Database } from '../../api/src/db';
import { purgeOrderEvents } from '../../api/src/jobs/purge-events';
import { orderTotalCents as apiTotal } from '../../api/src/lib/price';
import { loadFixture, testApp } from '../../api/test/helpers';
import { freshDatabase, pgAvailable, type TestDb } from '../../db/testing/test-db';
import { orderTotalCents as webTotal } from '../../web/src/lib/price';

const SAMPLE = path.resolve(__dirname, '..', '..');
const ids = (body: { orders: { id: number }[] }) => body.orders.map((o) => o.id);

describe.skipIf(!pgAvailable())('API defect canaries', () => {
  let db: TestDb;
  let app: Express;

  beforeAll(async () => {
    db = await freshDatabase();
    await loadFixture(db.pool);
    app = testApp(db.pool);
  });
  afterAll(async () => {
    await db.drop();
  });

  it('SD-01: an order at 23:59:30 UTC is missing from that day', async () => {
    const { rows } = await db.pool.query<{ id: number }>(
      "INSERT INTO orders (customer_id, status, total_cents, created_at) VALUES (2, 'PLACED', 100, '2026-09-15 23:59:30') RETURNING id",
    );
    const res = await request(app).get('/api/orders').query({ from: '2026-09-15', to: '2026-09-15' });
    expect(res.status).toBe(200);
    expect(ids(res.body)).not.toContain(rows[0]?.id);
  });

  it('SD-02: the sort parameter is executed as SQL', async () => {
    const harmless = await request(app)
      .get('/api/orders')
      .query({ from: '2026-09-01', to: '2026-09-30', sort: 'id, (SELECT 1)' });
    expect(harmless.status).toBe(200);
    const failing = await request(app)
      .get('/api/orders')
      .query({ from: '2026-09-01', to: '2026-09-30', sort: 'id, (SELECT 1 / (SELECT 0))' });
    expect(failing.status).toBe(500);
  });

  it('SD-03: listing N orders runs one items query per order', async () => {
    let queries = 0;
    const counting: Database = {
      query: (text: string, values?: unknown[]) => {
        queries += 1;
        return db.pool.query(text, values);
      },
      connect: () => db.pool.connect(),
    } as Database;
    const res = await request(createApp(counting, loadConfig({})))
      .get('/api/orders')
      .query({ from: '2026-09-01', to: '2026-09-14' });
    expect(res.body.orders).toHaveLength(3);
    expect(queries).toBe(2 + 3);
  });

  it('SD-04: write endpoints need no credentials', async () => {
    const res = await request(app).patch('/api/orders/2/status').send({ status: 'PACKED' });
    expect(res.status).toBe(200);
  });

  it('SD-05: a negative quantity is accepted and gives a negative total', async () => {
    const res = await request(app)
      .post('/api/orders')
      .send({ customerId: 1, items: [{ productId: 1, quantity: -2 }] });
    expect(res.status).toBe(201);
    expect(res.body.order.totalCents).toBeLessThan(0);
  });

  it('SD-10: order events older than 24 hours are purged (requirement OH-3 says 30 days)', async () => {
    const { rows } = await db.pool.query<{ id: string }>(
      "INSERT INTO order_events (order_id, status, created_at) VALUES (1, 'DELIVERED', now() - interval '25 hours') RETURNING id",
    );
    await purgeOrderEvents(db.pool);
    const left = await db.pool.query('SELECT 1 FROM order_events WHERE id = $1', [rows[0]?.id]);
    expect(left.rowCount).toBe(0);
    expect(readFileSync(path.join(SAMPLE, 'docs/REQUIREMENTS.md'), 'utf8')).toContain('last 30 days');
  });
});

describe('static defect canaries', () => {
  it('SD-06: API and web round totals differently', () => {
    const lines = [
      { quantity: 1, unitPriceCents: 6 },
      { quantity: 1, unitPriceCents: 6 },
    ];
    expect(apiTotal(lines)).toBe(12);
    expect(webTotal(lines)).toBe(13);
  });

  it('SD-08: sample CI uses unpinned third-party actions and no dependency cache', () => {
    const ci = readFileSync(path.join(SAMPLE, '.github/workflows/ci.yml'), 'utf8');
    expect(ci).toMatch(/uses: example-org\/[a-z-]+@main/);
    expect(ci).not.toMatch(/cache:/);
  });

  it('SD-09: the canned deployment log has a missing environment variable as root cause', () => {
    const log = readFileSync(path.join(SAMPLE, 'fixtures/logs/deploy-failure-01.log'), 'utf8');
    expect(log).toContain('Missing required environment variable: PGHOST (or DATABASE_URL)');
  });
});
