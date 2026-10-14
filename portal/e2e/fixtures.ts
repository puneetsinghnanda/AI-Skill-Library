import AxeBuilder from '@axe-core/playwright';
import { expect, test as base, type Page } from '@playwright/test';

export type DemoUser = 'viewer' | 'engineer' | 'lead' | 'admin';

/** Opens a demo page as a demo user. The demo uses MSW and the test token-cache fixture. */
export async function open(
  page: Page,
  path: string,
  user: DemoUser,
  extra: Record<string, string> = {},
) {
  const url = new URL(path, 'http://localhost');
  url.searchParams.set('demo_user', user);
  for (const [k, v] of Object.entries(extra)) url.searchParams.set(k, v);
  await page.goto(`${url.pathname}${url.search}`);
  await expect(page.getByRole('heading', { level: 1 }).first()).toBeVisible({ timeout: 15_000 });
  await page.waitForFunction(
    () => document.querySelectorAll('[aria-busy="true"]').length === 0,
    null,
    {
      timeout: 15_000,
    },
  );
}

/** Sets the view through the real persona switch (only shown to users who hold both roles). */
export async function setView(page: Page, view: 'Business' | 'Engineer') {
  const group = page.getByRole('group', { name: 'View as' });
  await group.getByRole('button', { name: view }).click();
  await expect(group.getByRole('button', { name: view })).toHaveAttribute('aria-pressed', 'true');
}

export async function axeSeriousOrCritical(page: Page) {
  const results = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'])
    .analyze();
  return results.violations.filter((v) => v.impact === 'serious' || v.impact === 'critical');
}

/** Collects CSP violations and page errors; the demo is served with the production CSP. */
export const test = base.extend<{ problems: string[] }>({
  problems: async ({ page }, use) => {
    const problems: string[] = [];
    page.on('console', (m) => {
      if (m.type() === 'error' && /Content Security Policy|Refused to/i.test(m.text()))
        problems.push(m.text());
    });
    page.on('pageerror', (e) => problems.push(`pageerror: ${e.message}`));
    await use(problems);
  },
});

export { expect };

export const BUSINESS_FORBIDDEN: RegExp[] = [
  /run_[0-9A-HJKMNP-TV-Z]{4}/,
  /\beng-[0-9a-f]{4}\b/,
  /\bSYS-[A-Z0-9]+/,
  /\bPRJ-[A-Z0-9]+/,
  /\bCL-[A-Z0-9]+/,
  /\b(ORD|TKT|INV)-\d+\b/,
  /Avery Example|Jordan Sample|Casey Placeholder|Riley Fixture|Morgan Demo/,
];
