import { readFileSync } from 'node:fs';
import { Pool } from 'pg';

/**
 * Pool for the db scripts. Uses DATABASE_URL or the libpq PG* variables.
 * The password is read from PGPASSWORD_FILE so it never sits in an env file.
 */
export function poolFromEnv(env: NodeJS.ProcessEnv = process.env): Pool {
  const password = env.PGPASSWORD_FILE ? readFileSync(env.PGPASSWORD_FILE, 'utf8').trim() : undefined;
  return new Pool({ connectionString: env.DATABASE_URL, password, max: 4 });
}
