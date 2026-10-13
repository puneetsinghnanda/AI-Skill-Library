import type { Queryable } from '../db';
import { toIso } from '../lib/dates';
import type { CustomerSummary } from '../types';

export async function customerExists(db: Queryable, id: number): Promise<boolean> {
  const { rows } = await db.query('SELECT 1 FROM customer WHERE id = $1', [id]);
  return rows.length > 0;
}

export async function findCustomerSummary(db: Queryable, id: number): Promise<CustomerSummary | null> {
  const { rows } = await db.query<{
    id: number;
    code: string;
    display_name: string;
    email: string;
    order_count: number;
    total_spent_cents: string;
    last_order_at: Date | null;
  }>(
    `SELECT c.id, c.code, c.display_name, c.email,
            count(o.id)::int AS order_count,
            coalesce(sum(o.total_cents), 0) AS total_spent_cents,
            max(o.created_at) AS last_order_at
       FROM customer c
       LEFT JOIN orders o ON o.customer_id = c.id AND o.archived_at IS NULL
      WHERE c.id = $1
      GROUP BY c.id`,
    [id],
  );
  const row = rows[0];
  if (!row) return null;
  return {
    id: row.id,
    code: row.code,
    displayName: row.display_name,
    email: row.email,
    orderCount: row.order_count,
    totalSpentCents: Number(row.total_spent_cents),
    lastOrderAt: toIso(row.last_order_at),
  };
}
