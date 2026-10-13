import { migrate } from './migrate';
import { poolFromEnv } from './pool';

async function main(): Promise<void> {
  const pool = poolFromEnv();
  try {
    const applied = await migrate(pool);
    console.log(applied.length ? `applied: ${applied.join(', ')}` : 'database is up to date');
  } finally {
    await pool.end();
  }
}

main().catch((err: unknown) => {
  console.error('migration failed:', err instanceof Error ? err.message : err);
  process.exitCode = 1;
});
