import react from '@vitejs/plugin-react';
import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vitest/config';

process.env.TZ = 'UTC';

// Defect canaries (TST-01 §4.3, TC-SAM-003). They PASS while each seeded defect still exists.
export default defineConfig({
  root: fileURLToPath(new URL('.', import.meta.url)),
  plugins: [react()],
  test: {
    include: ['*.canary.test.{ts,tsx}'],
    environment: 'node',
    globalSetup: ['../../db/testing/global-setup.ts'],
    testTimeout: 30_000,
    hookTimeout: 120_000,
  },
});
