import { readFileSync } from 'node:fs';
import { Pool, type PoolClient, type QueryResult, type QueryResultRow } from 'pg';
import type { DbConfig } from './config';

/** Anything that can run a query: the pool or a client inside a transaction. */
export interface Queryable {
  query<R extends QueryResultRow = QueryResultRow>(text: string, values?: unknown[]): Promise<QueryResult<R>>;
}

export interface Database extends Queryable {
  connect(): Promise<PoolClient>;
}

export function createPool(cfg: DbConfig): Pool {
  const password = cfg.passwordFile ? readFileSync(cfg.passwordFile, 'utf8').trim() : undefined;
  return new Pool({ connectionString: cfg.connectionString, password, max: 10 });
}

export async function inTransaction<T>(db: Database, work: (tx: Queryable) => Promise<T>): Promise<T> {
  const client = await db.connect();
  try {
    await client.query('BEGIN');
    const result = await work(client);
    await client.query('COMMIT');
    return result;
  } catch (err) {
    await client.query('ROLLBACK');
    throw err;
  } finally {
    client.release();
  }
}
