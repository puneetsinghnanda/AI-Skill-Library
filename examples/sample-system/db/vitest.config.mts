import { defineConfig } from 'vitest/config';

process.env.TZ = 'UTC';

export default defineConfig({
  test: {
    include: ['test/**/*.test.ts'],
    environment: 'node',
    globalSetup: ['testing/global-setup.ts'],
    testTimeout: 60_000,
    hookTimeout: 120_000,
  },
});
