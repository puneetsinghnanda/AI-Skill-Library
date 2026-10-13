/**
 * Nightly job: archive orders older than 24 months.
 * Archived orders keep their rows but are hidden from order history.
 */
import type { Queryable } from '../db';

export const ARCHIVE_AFTER = '24 months';

export async function archiveOrders(db: Queryable): Promise<number> {
  const res = await db.query(
    'UPDATE orders SET archived_at = now() WHERE archived_at IS NULL AND created_at < now() - $1::interval',
    [ARCHIVE_AFTER],
  );
  return res.rowCount ?? 0;
}
