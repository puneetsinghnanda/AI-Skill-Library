import { defineConfig } from 'vitest/config';

// Server-local time is part of the system's behaviour; pin it so test runs agree.
process.env.TZ = 'UTC';

export default defineConfig({
  test: {
    include: ['test/**/*.test.ts'],
    environment: 'node',
    globalSetup: ['../db/testing/global-setup.ts'],
    testTimeout: 30_000,
    hookTimeout: 120_000,
  },
});
