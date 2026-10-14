/// <reference types="vitest" />
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import react from '@vitejs/plugin-react';
import { defineConfig, type Plugin } from 'vite';

// One CSP for every place the built SPA is served (SDD-09 §10): nginx.conf, the edge, and
// `vite preview` (so the e2e suite runs under the same policy as production).
export const CSP = [
  "default-src 'self'",
  "script-src 'self'",
  "style-src 'self'",
  "img-src 'self' data:",
  "font-src 'self'",
  "connect-src 'self' https://login.microsoftonline.com",
  'frame-src https://login.microsoftonline.com',
  "frame-ancestors 'none'",
  "base-uri 'self'",
  "form-action 'self'",
].join('; ');

const SECURITY_HEADERS = {
  'Content-Security-Policy': CSP,
  'X-Content-Type-Options': 'nosniff',
  'Referrer-Policy': 'no-referrer',
  'Permissions-Policy': 'camera=(), microphone=(), geolocation=()',
};

// Demo mode only: serve and emit the MSW service worker. Production builds never contain it
// (scripts/check-bundle.mjs fails the build if they do).
function mswWorker(): Plugin {
  const require = createRequire(import.meta.url);
  const workerPath = require.resolve('msw/mockServiceWorker.js');
  return {
    name: 'truminds-demo-msw-worker',
    configureServer(server) {
      server.middlewares.use('/mockServiceWorker.js', (_req, res) => {
        res.setHeader('Content-Type', 'text/javascript');
        res.end(readFileSync(workerPath));
      });
    },
    generateBundle() {
      this.emitFile({
        type: 'asset',
        fileName: 'mockServiceWorker.js',
        source: readFileSync(workerPath),
      });
    },
  };
}

export default defineConfig(({ mode }) => ({
  plugins: [react(), ...(mode === 'demo' ? [mswWorker()] : [])],
  server: {
    port: 5173,
    strictPort: true,
    // /auth/github/* and /auth/logout: GitHub sign-in on the insights service (ADR 0006).
    proxy: {
      '/v1': 'http://localhost:8000',
      '/auth/github': 'http://localhost:8000',
      '/auth/logout': 'http://localhost:8000',
    },
  },
  preview: {
    port: 4173,
    headers: SECURITY_HEADERS,
  },
  build: {
    target: 'es2020',
    sourcemap: false,
    assetsInlineLimit: 0,
    chunkSizeWarningLimit: 600,
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
    css: false,
    testTimeout: 15000,
    coverage: { provider: 'v8', include: ['src/**'], exclude: ['src/api/schema.d.ts'] },
  },
}));
