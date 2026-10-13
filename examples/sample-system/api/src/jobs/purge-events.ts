/**
 * Nightly purge of the order activity feed ("Recent activity" on the order page).
 * Order events are kept for 24 hours. Status history (order_status_history)
 * is a separate table and is not touched here.
 */
import type { Queryable } from '../db';

export const EVENT_RETENTION = '24 hours';

export async function purgeOrderEvents(db: Queryable): Promise<number> {
  const res = await db.query(
    'DELETE FROM order_events WHERE created_at < now() - $1::interval',
    [EVENT_RETENTION],
  );
  return res.rowCount ?? 0;
}
