import type {} from './provided';
import { Pool } from 'pg';
import type { GlobalSetupContext } from 'vitest/node';
import { migrate } from '../scripts/migrate';
import { adminQuery, dbUrl, startPg } from './pg-harness';

/** Starts one throwaway PostgreSQL 16 per test run and migrates a template database. */
export default async function setup({ provide }: GlobalSetupContext): Promise<() => Promise<void>> {
  const server = await startPg();
  if (!server) {
    console.warn('[order-tracker] No PostgreSQL 16 found: database tests are skipped. Set PG_BIN or SAMPLE_TEST_DATABASE_URL.');
    provide('pgAdminUrl', '');
    provide('pgTemplateDb', '');
    return async () => undefined;
  }
  const template = `order_tracker_tpl_${process.pid}`;
  await adminQuery(server.adminUrl, `CREATE DATABASE ${template}`);
  const pool = new Pool({ connectionString: dbUrl(server.adminUrl, template) });
  try {
    await migrate(pool);
  } finally {
    await pool.end();
  }
  provide('pgAdminUrl', server.adminUrl);
  provide('pgTemplateDb', template);
  return async () => {
    await adminQuery(server.adminUrl, `DROP DATABASE IF EXISTS ${template}`).catch(() => undefined);
    await server.stop();
  };
}
