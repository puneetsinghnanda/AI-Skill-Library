import type { Pool, PoolClient } from 'pg';
import type { SeedData } from './generate';

const CHUNK = 500;

async function insertRows(
  client: PoolClient,
  table: string,
  columns: string[],
  rows: unknown[][],
): Promise<void> {
  for (let start = 0; start < rows.length; start += CHUNK) {
    const chunk = rows.slice(start, start + CHUNK);
    const params: unknown[] = [];
    const tuples = chunk.map((row) => {
      const marks = row.map((value) => {
        params.push(value);
        return `$${params.length}`;
      });
      return `(${marks.join(', ')})`;
    });
    await client.query(`INSERT INTO ${table} (${columns.join(', ')}) VALUES ${tuples.join(', ')}`, params);
  }
}

/** Replaces all data with the generated seed, in one transaction. */
export async function loadSeed(pool: Pool, data: SeedData): Promise<void> {
  const client = await pool.connect();
  try {
    await client.query('BEGIN');
    await client.query(
      'TRUNCATE order_events, shipment, order_status_history, order_item, orders, product, customer RESTART IDENTITY CASCADE',
    );
    await insertRows(client, 'customer', ['id', 'code', 'display_name', 'email'],
      data.customers.map((c) => [c.id, c.code, c.displayName, c.email]));
    await insertRows(client, 'product', ['id', 'sku', 'name', 'price_cents'],
      data.products.map((p) => [p.id, p.sku, p.name, p.priceCents]));
    await insertRows(client, 'orders', ['id', 'customer_id', 'status', 'total_cents', 'created_at', 'archived_at'],
      data.orders.map((o) => [o.id, o.customerId, o.status, o.totalCents, o.createdAt, o.archivedAt]));
    await insertRows(client, 'order_item', ['order_id', 'product_id', 'quantity', 'unit_price_cents'],
      data.orders.flatMap((o) => o.items.map((i) => [o.id, i.productId, i.quantity, i.unitPriceCents])));
    await insertRows(client, 'order_status_history', ['order_id', 'from_status', 'to_status', 'changed_at'],
      data.orders.flatMap((o) => o.history.map((h) => [o.id, h.fromStatus, h.toStatus, h.changedAt])));
    await insertRows(client, 'shipment', ['order_id', 'carrier_code', 'shipped_at'],
      data.orders.flatMap((o) => (o.shipment ? [[o.id, o.shipment.carrierCode, o.shipment.shippedAt]] : [])));
    await insertRows(client, 'order_events', ['order_id', 'status', 'created_at'],
      data.events.map((e) => [e.orderId, e.status, e.createdAt]));
    for (const table of ['customer', 'product', 'orders']) {
      await client.query(`SELECT setval(pg_get_serial_sequence('${table}', 'id'), (SELECT max(id) FROM ${table}))`);
    }
    await client.query('COMMIT');
  } catch (err) {
    await client.query('ROLLBACK');
    throw err;
  } finally {
    client.release();
  }
}
