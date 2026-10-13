import type { Queryable } from '../db';
import type { OrderStatus } from '../lib/status';

/** Adds a row to the order activity feed (shown as "Recent activity"). */
export async function insertOrderEvent(db: Queryable, orderId: number, status: OrderStatus): Promise<void> {
  await db.query('INSERT INTO order_events (order_id, status) VALUES ($1, $2)', [orderId, status]);
}
