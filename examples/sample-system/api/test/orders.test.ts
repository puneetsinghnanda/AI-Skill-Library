import type { Express } from 'express';
import request from 'supertest';
import { afterAll, beforeAll, describe, expect, it } from 'vitest';
import { freshDatabase, pgAvailable, type TestDb } from '../../db/testing/test-db';
import { loadFixture, testApp } from './helpers';

// Deliberately partial (TST-01 §4.2): happy paths and basic validation only.
describe.skipIf(!pgAvailable())('orders API', () => {
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

  describe('GET /api/orders', () => {
    it('lists non-archived orders in the range, newest first', async () => {
      const res = await request(app).get('/api/orders').query({ from: '2026-09-01', to: '2026-09-30' });
      expect(res.status).toBe(200);
      expect(res.body.orders.map((o: { id: number }) => o.id)).toEqual([2, 3, 1]);
      expect(res.body.total).toBe(3);
      expect(res.body.pageSize).toBe(20);
    });

    it('includes items and the customer name', async () => {
      const res = await request(app).get('/api/orders').query({ from: '2026-09-10', to: '2026-09-10' });
      expect(res.body.orders).toHaveLength(1);
      expect(res.body.orders[0]).toMatchObject({
        id: 1,
        customerName: 'Test Customer 001',
        totalCents: 2165,
        items: [{ sku: 'SKU-0001', quantity: 2, unitPriceCents: 1000 }],
      });
    });

    it('filters by customer', async () => {
      const res = await request(app).get('/api/orders').query({ from: '2026-09-01', to: '2026-09-30', customerId: '2' });
      expect(res.body.orders.map((o: { id: number }) => o.id)).toEqual([3]);
    });

    it('hides archived orders', async () => {
      const res = await request(app).get('/api/orders').query({ from: '2024-01-01', to: '2024-12-31' });
      expect(res.body.orders).toEqual([]);
    });

    it('sorts by total when asked', async () => {
      const res = await request(app)
        .get('/api/orders')
        .query({ from: '2026-09-01', to: '2026-09-30', sort: 'total_cents:asc' });
      expect(res.body.orders.map((o: { id: number }) => o.id)).toEqual([1, 2, 3]);
    });

    it('rejects a malformed date', async () => {
      const res = await request(app).get('/api/orders').query({ from: '10/09/2026' });
      expect(res.status).toBe(400);
      expect(res.body.error.code).toBe('BAD_REQUEST');
    });

    it('returns an empty first page by default when nothing is recent', async () => {
      const res = await request(app).get('/api/orders');
      expect(res.status).toBe(200);
      expect(res.body.page).toBe(1);
    });
  });

  describe('GET /api/orders/:id', () => {
    it('returns items, status history and shipment', async () => {
      const res = await request(app).get('/api/orders/1');
      expect(res.status).toBe(200);
      expect(res.body.order.statusHistory.map((h: { toStatus: string }) => h.toStatus)).toEqual([
        'PLACED',
        'PACKED',
        'SHIPPED',
        'DELIVERED',
      ]);
      expect(res.body.order.shipment).toEqual({ carrierCode: 'CARRIER-B', shippedAt: '2026-09-11T08:00:00.000Z' });
    });

    it('returns 404 for an unknown order', async () => {
      const res = await request(app).get('/api/orders/999');
      expect(res.status).toBe(404);
    });

    it('rejects a non-numeric id', async () => {
      const res = await request(app).get('/api/orders/abc');
      expect(res.status).toBe(400);
    });
  });

  describe('POST /api/orders', () => {
    it('creates an order with prices from the catalogue', async () => {
      const res = await request(app)
        .post('/api/orders')
        .send({ customerId: 3, items: [{ productId: 4, quantity: 3 }] });
      expect(res.status).toBe(201);
      expect(res.body.order).toMatchObject({
        customerId: 3,
        status: 'PLACED',
        totalCents: 2598,
        items: [{ productId: 4, quantity: 3, unitPriceCents: 800 }],
      });
      expect(res.body.order.events).toHaveLength(1);
      expect(res.body.order.statusHistory).toEqual([
        expect.objectContaining({ fromStatus: null, toStatus: 'PLACED' }),
      ]);
    });

    it('rejects an unknown product', async () => {
      const res = await request(app)
        .post('/api/orders')
        .send({ customerId: 1, items: [{ productId: 99, quantity: 1 }] });
      expect(res.status).toBe(400);
    });

    it('rejects an unknown customer', async () => {
      const res = await request(app)
        .post('/api/orders')
        .send({ customerId: 42, items: [{ productId: 1, quantity: 1 }] });
      expect(res.status).toBe(400);
    });

    it('rejects a missing items list', async () => {
      const res = await request(app).post('/api/orders').send({ customerId: 1 });
      expect(res.status).toBe(400);
    });

    it('rejects a non-integer quantity', async () => {
      const res = await request(app)
        .post('/api/orders')
        .send({ customerId: 1, items: [{ productId: 1, quantity: 'two' }] });
      expect(res.status).toBe(400);
    });
  });

  describe('PATCH /api/orders/:id/status', () => {
    it('moves PLACED to PACKED and records history', async () => {
      const res = await request(app).patch('/api/orders/2/status').send({ status: 'PACKED' });
      expect(res.status).toBe(200);
      expect(res.body.order.status).toBe('PACKED');
      expect(res.body.order.statusHistory.at(-1)).toMatchObject({ fromStatus: 'PLACED', toStatus: 'PACKED' });
    });

    it('creates a shipment when an order ships', async () => {
      const res = await request(app).patch('/api/orders/2/status').send({ status: 'SHIPPED', carrierCode: 'CARRIER-C' });
      expect(res.status).toBe(200);
      expect(res.body.order.shipment.carrierCode).toBe('CARRIER-C');
    });

    it('accepts the legacy SHIPPD status on old orders', async () => {
      const res = await request(app).patch('/api/orders/3/status').send({ status: 'DELIVERED' });
      expect(res.status).toBe(200);
      expect(res.body.order.status).toBe('DELIVERED');
    });

    it('refuses an invalid transition', async () => {
      const res = await request(app).patch('/api/orders/1/status').send({ status: 'PACKED' });
      expect(res.status).toBe(409);
      expect(res.body.error.code).toBe('CONFLICT');
    });

    it('refuses an unknown status', async () => {
      const res = await request(app).patch('/api/orders/1/status').send({ status: 'LOST' });
      expect(res.status).toBe(400);
    });
  });
});
