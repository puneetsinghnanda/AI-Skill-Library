import { existsSync } from 'node:fs';
import { chromium, defineConfig, devices } from '@playwright/test';

// The sandbox pre-installs Chromium under PLAYWRIGHT_BROWSERS_PATH; never run `playwright install`
// here. If the pinned Playwright expects another build, fall back to the pre-installed binary.
const FALLBACK = '/opt/pw-browsers/chromium';
const executablePath =
  existsSync(chromium.executablePath()) || !existsSync(FALLBACK) ? undefined : FALLBACK;

const PORT = 4173;

// Release runs add Firefox and WebKit (OPS-03 §3, TST-01 §6): PW_EXTRA_BROWSERS="firefox webkit".
const EXTRA_DEVICES: Record<string, string> = {
  firefox: 'Desktop Firefox',
  webkit: 'Desktop Safari',
};
const extraProjects = (process.env.PW_EXTRA_BROWSERS ?? '')
  .split(/[\s,]+/)
  .filter((name) => name in EXTRA_DEVICES)
  .map((name) => ({ name, use: { ...devices[EXTRA_DEVICES[name]] } }));

export default defineConfig({
  testDir: './e2e',
  outputDir: './test-results',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: [['list']],
  timeout: 30_000,
  use: {
    baseURL: `http://localhost:${PORT}`,
    trace: 'retain-on-failure',
    serviceWorkers: 'allow',
    ...(executablePath ? { launchOptions: { executablePath } } : {}),
  },
  projects: [
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        ...(executablePath ? { launchOptions: { executablePath } } : {}),
      },
    },
    ...extraProjects,
  ],
  // e2e runs against the explicit demo build (MSW mocks + test token-cache fixture), served by
  // `vite preview` with the production CSP headers.
  webServer: {
    command: 'npm run demo',
    url: `http://localhost:${PORT}`,
    reuseExistingServer: !process.env.CI,
    timeout: 180_000,
    stdout: 'ignore',
    stderr: 'pipe',
  },
});
