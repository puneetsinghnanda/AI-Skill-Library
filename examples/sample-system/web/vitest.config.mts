import react from '@vitejs/plugin-react';
import { defineConfig } from 'vitest/config';

process.env.TZ = 'UTC';

export default defineConfig({
  plugins: [react()],
  test: {
    include: ['src/__tests__/**/*.test.{ts,tsx}'],
    environment: 'jsdom',
    setupFiles: ['src/__tests__/setup.ts'],
  },
});
