import { loadConfig } from '../config';
import { createPool } from '../db';
import { archiveOrders } from './archive-orders';
import { purgeOrderEvents } from './purge-events';

const JOBS: Record<string, (db: ReturnType<typeof createPool>) => Promise<number>> = {
  'archive-orders': archiveOrders,
  'purge-events': purgeOrderEvents,
};

async function main(name: string | undefined): Promise<void> {
  const job = name ? JOBS[name] : undefined;
  if (!job) {
    console.error(`usage: run-job <${Object.keys(JOBS).join('|')}>`);
    process.exitCode = 2;
    return;
  }
  const pool = createPool(loadConfig().db);
  try {
    console.log(`[job] ${name}: ${await job(pool)} row(s)`);
  } finally {
    await pool.end();
  }
}

main(process.argv[2]).catch((err: unknown) => {
  console.error('[job] failed:', err instanceof Error ? err.message : err);
  process.exitCode = 1;
});
