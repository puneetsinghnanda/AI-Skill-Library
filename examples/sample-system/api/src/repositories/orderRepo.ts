import type { Queryable } from '../db';
import { toIso } from '../lib/dates';
import type { OrderStatus } from '../lib/status';
import type {
  NewOrderLine,
  OrderDetail,
  OrderEvent,
  OrderItem,
  OrderListFilter,
  OrderPage,
  OrderSummary,
  StatusChange,
} from '../types';

interface OrderRow {
  id: number;
  customer_id: number;
  customer_name: string;
  status: OrderStatus;
  total_cents: number;
  created_at: Date;
}

interface ItemRow {
  product_id: number;
  sku: string;
  name: string;
  quantity: number;
  unit_price_cents: number;
}

function toSummary(row: OrderRow, items: OrderItem[]): OrderSummary {
  return {
    id: row.id,
    customerId: row.customer_id,
    customerName: row.customer_name,
    status: row.status,
    totalCents: row.total_cents,
    createdAt: row.created_at.toISOString(),
    items,
  };
}

export async function listItems(db: Queryable, orderId: number): Promise<OrderItem[]> {
  const { rows } = await db.query<ItemRow>(
    `SELECT i.product_id, p.sku, p.name, i.quantity, i.unit_price_cents
       FROM order_item i JOIN product p ON p.id = i.product_id
      WHERE i.order_id = $1
      ORDER BY p.sku`,
    [orderId],
  );
  return rows.map((r) => ({
    productId: r.product_id,
    sku: r.sku,
    name: r.name,
    quantity: r.quantity,
    unitPriceCents: r.unit_price_cents,
  }));
}

/** Order history: one page of non-archived orders in the date range. */
export async function listOrders(db: Queryable, filter: OrderListFilter): Promise<OrderPage> {
  const params: unknown[] = [filter.from, filter.to];
  const where = ['o.archived_at IS NULL', 'o.created_at >= $1', 'o.created_at <= $2'];
  if (filter.customerId !== undefined) {
    params.push(filter.customerId);
    where.push(`o.customer_id = $${params.length}`);
  }
  const whereSql = where.join(' AND ');
  const count = await db.query<{ total: number }>(
    `SELECT count(*)::int AS total FROM orders o WHERE ${whereSql}`,
    params,
  );

  const orderBy = filter.sort ?? 'created_at DESC, o.id DESC';
  params.push(filter.pageSize, (filter.page - 1) * filter.pageSize);
  const { rows } = await db.query<OrderRow>(
    `SELECT o.id, o.customer_id, c.display_name AS customer_name, o.status, o.total_cents, o.created_at
       FROM orders o JOIN customer c ON c.id = o.customer_id
      WHERE ${whereSql}
      ORDER BY o.` + orderBy + `
      LIMIT $${params.length - 1} OFFSET $${params.length}`,
    params,
  );

  const orders: OrderSummary[] = [];
  for (const row of rows) {
    const items = await listItems(db, row.id);
    orders.push(toSummary(row, items));
  }
  return { orders, total: count.rows[0]?.total ?? 0 };
}

export async function findOrder(db: Queryable, id: number): Promise<OrderDetail | null> {
  const { rows } = await db.query<OrderRow>(
    `SELECT o.id, o.customer_id, c.display_name AS customer_name, o.status, o.total_cents, o.created_at
       FROM orders o JOIN customer c ON c.id = o.customer_id
      WHERE o.id = $1`,
    [id],
  );
  const row = rows[0];
  if (!row) return null;

  const history = await db.query<{ from_status: OrderStatus | null; to_status: OrderStatus; changed_at: Date }>(
    'SELECT from_status, to_status, changed_at FROM order_status_history WHERE order_id = $1 ORDER BY changed_at, to_status',
    [id],
  );
  const events = await db.query<{ id: string; status: OrderStatus; created_at: Date }>(
    'SELECT id, status, created_at FROM order_events WHERE order_id = $1 ORDER BY created_at DESC, id DESC',
    [id],
  );
  const shipment = await db.query<{ carrier_code: string; shipped_at: Date }>(
    'SELECT carrier_code, shipped_at FROM shipment WHERE order_id = $1',
    [id],
  );

  const statusHistory: StatusChange[] = history.rows.map((h) => ({
    fromStatus: h.from_status,
    toStatus: h.to_status,
    changedAt: h.changed_at.toISOString(),
  }));
  const orderEvents: OrderEvent[] = events.rows.map((e) => ({
    id: Number(e.id),
    status: e.status,
    createdAt: e.created_at.toISOString(),
  }));
  const ship = shipment.rows[0];
  return {
    ...toSummary(row, await listItems(db, id)),
    statusHistory,
    events: orderEvents,
    shipment: ship ? { carrierCode: ship.carrier_code, shippedAt: toIso(ship.shipped_at) as string } : null,
  };
}

export async function insertOrder(
  db: Queryable,
  customerId: number,
  totalCents: number,
  lines: (NewOrderLine & { unitPriceCents: number })[],
): Promise<number> {
  const { rows } = await db.query<{ id: number }>(
    "INSERT INTO orders (customer_id, status, total_cents) VALUES ($1, 'PLACED', $2) RETURNING id",
    [customerId, totalCents],
  );
  const id = (rows[0] as { id: number }).id;
  for (const line of lines) {
    await db.query(
      'INSERT INTO order_item (order_id, product_id, quantity, unit_price_cents) VALUES ($1, $2, $3, $4)',
      [id, line.productId, line.quantity, line.unitPriceCents],
    );
  }
  return id;
}

/** Current status, with the row locked for the rest of the transaction. */
export async function lockOrderStatus(db: Queryable, id: number): Promise<OrderStatus | null> {
  const { rows } = await db.query<{ status: OrderStatus }>('SELECT status FROM orders WHERE id = $1 FOR UPDATE', [id]);
  return rows[0]?.status ?? null;
}

export async function updateStatus(db: Queryable, id: number, status: OrderStatus): Promise<void> {
  await db.query('UPDATE orders SET status = $2 WHERE id = $1', [id, status]);
}

export async function insertStatusChange(
  db: Queryable,
  id: number,
  fromStatus: OrderStatus | null,
  toStatus: OrderStatus,
): Promise<void> {
  await db.query(
    'INSERT INTO order_status_history (order_id, from_status, to_status) VALUES ($1, $2, $3)',
    [id, fromStatus, toStatus],
  );
}

export async function insertShipment(db: Queryable, id: number, carrierCode: string): Promise<void> {
  await db.query('INSERT INTO shipment (order_id, carrier_code) VALUES ($1, $2)', [id, carrierCode]);
}
