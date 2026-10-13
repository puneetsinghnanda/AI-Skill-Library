import type {} from './provided';
import { randomBytes } from 'node:crypto';
import { Pool } from 'pg';
import { inject } from 'vitest';
import { adminQuery, dbUrl } from './pg-harness';

/** True when the global setup started (or found) a PostgreSQL server. */
export function pgAvailable(): boolean {
  return inject('pgAdminUrl') !== '';
}

export interface TestDb {
  pool: Pool;
  drop(): Promise<void>;
}

/** A fresh, migrated, empty database copied from the template. One per test file. */
export async function freshDatabase(): Promise<TestDb> {
  const adminUrl = inject('pgAdminUrl');
  const template = inject('pgTemplateDb');
  const name = `order_tracker_t_${randomBytes(6).toString('hex')}`;
  for (let attempt = 0; ; attempt++) {
    try {
      await adminQuery(adminUrl, `CREATE DATABASE ${name} TEMPLATE ${template}`);
      break;
    } catch (err) {
      // Two files copying the template at once can collide; retry briefly.
      if (attempt >= 5) throw err;
      await new Promise((r) => setTimeout(r, 200 * (attempt + 1)));
    }
  }
  const pool = new Pool({ connectionString: dbUrl(adminUrl, name), max: 5 });
  return {
    pool,
    drop: async () => {
      await pool.end();
      await adminQuery(adminUrl, `DROP DATABASE IF EXISTS ${name}`);
    },
  };
}
