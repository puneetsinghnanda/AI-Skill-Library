export interface DbConfig {
  /** Optional connection string without a password. Otherwise libpq PG* variables apply. */
  connectionString?: string;
  /** File holding the database password (Docker secret). */
  passwordFile?: string;
}

export interface AppConfig {
  host: string;
  port: number;
  db: DbConfig;
  /** Days of order history returned when the caller gives no `from` date. */
  orderHistoryDefaultDays: number;
  pageSize: number;
}

function intEnv(value: string | undefined, fallback: number, name: string): number {
  if (value === undefined || value === '') return fallback;
  const n = Number(value);
  if (!Number.isInteger(n) || n <= 0) throw new Error(`Invalid value for ${name}: expected a positive integer`);
  return n;
}

export function loadConfig(env: NodeJS.ProcessEnv = process.env): AppConfig {
  if (env.NODE_ENV === 'production' && !env.DATABASE_URL && !env.PGHOST) {
    throw new Error('Missing required environment variable: PGHOST (or DATABASE_URL)');
  }
  return {
    host: env.API_HOST ?? '127.0.0.1',
    port: intEnv(env.API_PORT, 3000, 'API_PORT'),
    db: { connectionString: env.DATABASE_URL, passwordFile: env.PGPASSWORD_FILE },
    orderHistoryDefaultDays: intEnv(env.ORDER_HISTORY_DEFAULT_DAYS, 7, 'ORDER_HISTORY_DEFAULT_DAYS'),
    pageSize: 20,
  };
}
