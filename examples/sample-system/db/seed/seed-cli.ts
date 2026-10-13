import { poolFromEnv } from '../scripts/pool';
import { DEFAULT_SEED, generateSeed, resolveAnchor, seedHash } from './generate';
import { loadSeed } from './load';

async function main(): Promise<void> {
  const seed = process.env.SEED ? Number(process.env.SEED) : DEFAULT_SEED;
  const data = generateSeed(seed, resolveAnchor(process.env.SEED_ANCHOR));
  const pool = poolFromEnv();
  try {
    await loadSeed(pool, data);
  } finally {
    await pool.end();
  }
  console.log(
    `seeded ${data.customers.length} customers, ${data.products.length} products, ` +
      `${data.orders.length} orders, ${data.events.length} events (sha256 ${seedHash(data).slice(0, 12)})`,
  );
}

main().catch((err: unknown) => {
  console.error('seed failed:', err instanceof Error ? err.message : err);
  process.exitCode = 1;
});
