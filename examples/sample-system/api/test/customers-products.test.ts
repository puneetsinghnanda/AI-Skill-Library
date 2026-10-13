import type { Express } from 'express';
import request from 'supertest';
import { afterAll, beforeAll, describe, expect, it } from 'vitest';
import { freshDatabase, pgAvailable, type TestDb } from '../../db/testing/test-db';
import { archiveOrders } from '../src/jobs/archive-orders';
import { loadFixture, testApp } from './helpers';

describe.skipIf(!pgAvailable())('customers, products and the archive job', () => {
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

  it('GET /api/customers/:id returns a summary of non-archived orders', async () => {
    const res = await request(app).get('/api/customers/1');
    expect(res.status).toBe(200);
    expect(res.body.customer).toEqual({
      id: 1,
      code: 'CUST-001',
      displayName: 'Test Customer 001',
      email: 'cust001@example.test',
      orderCount: 2,
      totalSpentCents: 4871,
      lastOrderAt: '2026-09-12T14:30:00.000Z',
    });
  });

  it('GET /api/customers/:id returns 404 for an unknown customer', async () => {
    const res = await request(app).get('/api/customers/404');
    expect(res.status).toBe(404);
  });

  it('GET /api/products lists the catalogue by SKU', async () => {
    const res = await request(app).get('/api/products');
    expect(res.status).toBe(200);
    expect(res.body.products.map((p: { sku: string }) => p.sku)).toEqual(['SKU-0001', 'SKU-0002', 'SKU-0003', 'SKU-0004']);
  });

  it('archive job hides orders older than 24 months and leaves recent ones', async () => {
    await db.pool.query(
      "INSERT INTO orders (customer_id, status, total_cents, created_at) VALUES (3, 'DELIVERED', 100, now() - interval '25 months')",
    );
    expect(await archiveOrders(db.pool)).toBe(1);
    const { rows } = await db.pool.query<{ n: number }>('SELECT count(*)::int AS n FROM orders WHERE archived_at IS NULL');
    expect(rows[0]?.n).toBe(3);
  });
});
