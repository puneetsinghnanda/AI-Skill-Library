import type { Express } from 'express';
import type { Pool } from 'pg';
import { createApp } from '../src/app';
import { loadConfig } from '../src/config';

process.env.REQUEST_LOG = 'off';

export function testApp(pool: Pool): Express {
  return createApp(pool, loadConfig({ ORDER_HISTORY_DEFAULT_DAYS: '7' }));
}

/**
 * Small invented fixture: 3 customers, 4 products, 4 orders at fixed mid-day times.
 * Timestamps are UTC wall-clock text for `timestamp` columns.
 */
export async function loadFixture(pool: Pool): Promise<void> {
  await pool.query(`
    INSERT INTO customer (id, code, display_name, email) VALUES
      (1, 'CUST-001', 'Test Customer 001', 'cust001@example.test'),
      (2, 'CUST-002', 'Test Customer 002', 'cust002@example.test'),
      (3, 'CUST-003', 'Test Customer 003', 'cust003@example.test');
    SELECT setval(pg_get_serial_sequence('customer', 'id'), 3);

    INSERT INTO product (id, sku, name, price_cents) VALUES
      (1, 'SKU-0001', 'Blue Notebook', 1000),
      (2, 'SKU-0002', 'Steel Water Bottle', 2500),
      (3, 'SKU-0003', 'Canvas Backpack', 4999),
      (4, 'SKU-0004', 'Glass Mug', 800);
    SELECT setval(pg_get_serial_sequence('product', 'id'), 4);

    INSERT INTO orders (id, customer_id, status, total_cents, created_at, archived_at) VALUES
      (1, 1, 'DELIVERED', 2165, '2026-09-10 10:00:00', NULL),
      (2, 1, 'PLACED',    2706, '2026-09-12 14:30:00', NULL),
      (3, 2, 'SHIPPD',    5411, '2026-09-11 09:15:00', NULL),
      (4, 1, 'DELIVERED', 1083, '2024-01-05 12:00:00', '2026-01-06 02:00:00');
    SELECT setval(pg_get_serial_sequence('orders', 'id'), 4);

    INSERT INTO order_item (order_id, product_id, quantity, unit_price_cents) VALUES
      (1, 1, 2, 1000), (2, 2, 1, 2500), (3, 3, 1, 4999), (4, 1, 1, 1000);

    INSERT INTO order_status_history (order_id, from_status, to_status, changed_at) VALUES
      (1, NULL, 'PLACED', '2026-09-10 10:00:00'),
      (1, 'PLACED', 'PACKED', '2026-09-10 12:00:00'),
      (1, 'PACKED', 'SHIPPED', '2026-09-11 08:00:00'),
      (1, 'SHIPPED', 'DELIVERED', '2026-09-13 16:00:00'),
      (2, NULL, 'PLACED', '2026-09-12 14:30:00'),
      (3, NULL, 'PLACED', '2026-09-11 09:15:00'),
      (3, 'PLACED', 'SHIPPD', '2026-09-12 09:15:00');

    INSERT INTO shipment (order_id, carrier_code, shipped_at) VALUES
      (1, 'CARRIER-B', '2026-09-11 08:00:00'),
      (3, 'CARRIER-A', '2026-09-12 09:15:00');
  `);
}
