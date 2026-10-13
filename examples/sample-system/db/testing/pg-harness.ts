import { execFileSync } from 'node:child_process';
import { chownSync, existsSync, mkdtempSync, rmSync } from 'node:fs';
import net from 'node:net';
import os from 'node:os';
import path from 'node:path';
import { Client } from 'pg';

/**
 * Throwaway PostgreSQL 16 for tests. Either:
 *  - SAMPLE_TEST_DATABASE_URL points at an existing server (admin database URL), or
 *  - the PostgreSQL 16 binaries (PG_BIN, default /usr/lib/postgresql/16/bin) start a
 *    temporary cluster in a temp directory, on loopback, removed afterwards.
 * Returns null when neither is available; tests then skip with a clear message.
 */
export interface PgServer {
  adminUrl: string;
  stop(): Promise<void>;
}

const PG_BIN = process.env.PG_BIN ?? '/usr/lib/postgresql/16/bin';

function freePort(): Promise<number> {
  return new Promise((resolve, reject) => {
    const srv = net.createServer();
    srv.once('error', reject);
    srv.listen(0, '127.0.0.1', () => {
      const addr = srv.address();
      const port = typeof addr === 'object' && addr ? addr.port : 0;
      srv.close(() => resolve(port));
    });
  });
}

export function dbUrl(adminUrl: string, database: string): string {
  const url = new URL(adminUrl);
  url.pathname = `/${database}`;
  return url.toString();
}

export async function startPg(): Promise<PgServer | null> {
  const external = process.env.SAMPLE_TEST_DATABASE_URL;
  if (external) return { adminUrl: external, stop: async () => undefined };
  if (!existsSync(path.join(PG_BIN, 'initdb'))) return null;

  // initdb refuses to run as root, so a root test run uses the postgres OS account.
  const asRoot = typeof process.getuid === 'function' && process.getuid() === 0;
  const run = (bin: string, args: string[]): void => {
    const cmd = path.join(PG_BIN, bin);
    if (asRoot) execFileSync('runuser', ['-u', 'postgres', '--', cmd, ...args], { stdio: 'ignore' });
    else execFileSync(cmd, args, { stdio: 'ignore' });
  };

  const base = process.env.SAMPLE_PG_TMP ?? (asRoot ? '/tmp' : os.tmpdir());
  const dir = mkdtempSync(path.join(base, 'order-tracker-pg-'));
  if (asRoot) {
    const uid = Number(execFileSync('id', ['-u', 'postgres']).toString().trim());
    const gid = Number(execFileSync('id', ['-g', 'postgres']).toString().trim());
    chownSync(dir, uid, gid);
  }
  const data = path.join(dir, 'data');
  const port = await freePort();
  run('initdb', ['-D', data, '-U', 'order_tracker', '-A', 'trust', '-E', 'UTF8', '--locale=C', '--no-sync']);
  run('pg_ctl', [
    '-D', data, '-l', path.join(dir, 'server.log'), '-w', '-o',
    `-p ${port} -k ${dir} -c listen_addresses=127.0.0.1 -c fsync=off -c full_page_writes=off -c timezone=UTC`,
    'start',
  ]);
  return {
    adminUrl: `postgres://order_tracker@127.0.0.1:${port}/postgres`,
    stop: async () => {
      try {
        run('pg_ctl', ['-D', data, '-m', 'immediate', '-w', 'stop']);
      } finally {
        rmSync(dir, { recursive: true, force: true });
      }
    },
  };
}

export async function adminQuery(adminUrl: string, sql: string): Promise<void> {
  const client = new Client({ connectionString: adminUrl });
  await client.connect();
  try {
    await client.query(sql);
  } finally {
    await client.end();
  }
}
