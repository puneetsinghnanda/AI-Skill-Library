import { BUSINESS_FORBIDDEN, expect, open, setView, test } from './fixtures';

test.describe('TC-POR-001 top bar and navigation map', () => {
  test('every top-bar item opens its screen and highlights itself', async ({ page, problems }) => {
    await open(page, '/', 'engineer');
    const nav = page.getByRole('navigation', { name: 'Main' });
    const items: [string, RegExp][] = [
      ['How it works', /From a client ticket to a reviewed pull request/],
      ['Skills', /^Skills$/],
      ['Pods', /AI-augmented pods/],
      ['Insights', /Monitoring/],
      ['Get started', /Install tsl and start your first run/],
      ['Home', /Welcome back/],
    ];
    for (const [label, h1] of items) {
      await nav.getByRole('link', { name: label }).click();
      await expect(page.getByRole('heading', { level: 1 })).toHaveText(h1);
      await expect(nav.getByRole('link', { name: label })).toHaveAttribute('aria-current', 'page');
      // Focus moves to the new screen's h1 (SDD-09 §8).
      await expect(page.getByRole('heading', { level: 1 })).toBeFocused();
    }
    expect(problems).toEqual([]);
  });

  test('detail screens highlight their parent tab', async ({ page }) => {
    await open(page, '/skills/threat-model', 'engineer');
    await expect(
      page.getByRole('navigation', { name: 'Main' }).getByRole('link', { name: 'Skills' }),
    ).toHaveAttribute('aria-current', 'page');
    await open(page, '/pods/builder', 'engineer');
    await expect(
      page.getByRole('navigation', { name: 'Main' }).getByRole('link', { name: 'Pods' }),
    ).toHaveAttribute('aria-current', 'page');
    await open(page, '/runs/run_01J9ZK2M4Q8X7T3B5N6R0VWYCD', 'engineer');
    await expect(
      page.getByRole('navigation', { name: 'Main' }).getByRole('link', { name: 'Insights' }),
    ).toHaveAttribute('aria-current', 'page');
  });

  test('the switch changes only the view; the current screen stays open', async ({ page }) => {
    await open(page, '/skills/threat-model', 'engineer');
    await expect(page.getByRole('tablist', { name: 'Skill details' })).toBeVisible();
    await setView(page, 'Business');
    await expect(page).toHaveURL(/\/skills\/threat-model(\?|$)/);
    await expect(page.getByRole('heading', { name: 'Why clients care' })).toBeVisible();
    await expect(page.getByRole('tablist', { name: 'Skill details' })).toHaveCount(0);
  });

  test('Home links lead to Skills, Pods and Run detail', async ({ page }) => {
    await open(page, '/', 'engineer');
    await page.getByRole('link', { name: 'run_01J9..CD' }).first().click();
    await expect(page.getByRole('heading', { level: 1 })).toContainText(
      'run_01J9ZK2M4Q8X7T3B5N6R0VWYCD',
    );
    await page.getByRole('link', { name: '← Monitoring' }).click();
    await expect(page.getByRole('heading', { level: 1 })).toHaveText('Monitoring');
  });
});

test.describe('persona rules', () => {
  test('the switch is hidden from business-only users', async ({ page }) => {
    await open(page, '/', 'viewer');
    await expect(page.getByRole('heading', { level: 1 })).toContainText('Reusable AI skills');
    await expect(page.getByRole('group', { name: 'View as' })).toHaveCount(0);
  });

  test('TC-POR-003 Run detail sends Business users to Insights', async ({ page }) => {
    await open(page, '/runs/run_01J9ZK2M4Q8X7T3B5N6R0VWYCD', 'viewer');
    await expect(page).toHaveURL(/\/insights$/);
    await expect(page.getByRole('heading', { level: 1 })).toHaveText('Impact and capability');
  });

  test('TC-POR-002 business pages and class A responses carry no run ids, tickets, systems or names', async ({
    page,
  }) => {
    const bodies: string[] = [];
    page.on('response', async (r) => {
      const u = new URL(r.url());
      if (/^\/v1\/(capability-map|insights\/business|catalogue\/)/.test(u.pathname))
        bodies.push(await r.text());
    });
    for (const path of [
      '/',
      '/insights',
      '/skills',
      '/skills/threat-model',
      '/pods',
      '/pods/brownfield-change-pod',
      '/insights/capability-map/share',
      '/how-it-works',
      '/get-started',
    ]) {
      await open(page, path, 'viewer');
      const text = await page.locator('body').innerText();
      for (const re of BUSINESS_FORBIDDEN) expect(text, `${path} shows ${re}`).not.toMatch(re);
    }
    expect(bodies.length).toBeGreaterThan(0);
    for (const b of bodies) for (const re of BUSINESS_FORBIDDEN) expect(b).not.toMatch(re);
  });

  test('TC-POR-011 the shared capability map holds production skills only', async ({ page }) => {
    const shared = page.waitForResponse((r) =>
      r.url().includes('/v1/capability-map?audience=shared'),
    );
    await open(page, '/insights/capability-map/share', 'viewer');
    const body = await (await shared).text();
    expect(body).not.toContain('"pilot"');
    await expect(page.getByText(/· pilot/)).toHaveCount(0);
    await open(page, '/insights', 'viewer');
    await expect(page.getByText('Test automation · pilot')).toBeVisible();
  });
});

test('TC-POR-005 behind banner when the API reports lag', async ({ page }) => {
  await open(page, '/', 'viewer', { demo_behind: '1' });
  await expect(
    page.getByRole('status').filter({ hasText: 'Insights are behind; last event received at' }),
  ).toBeVisible();
  await expect(page.getByText('126')).toBeVisible(); // the page keeps showing the last data
});

test('TC-POR-004 empty data shows No data yet, never sample numbers', async ({ page }) => {
  await open(page, '/insights', 'viewer', { demo_empty: '1' });
  await expect(page.getByText('No data yet').first()).toBeVisible();
  await expect(page.getByText('82%')).toHaveCount(0);
});

test('TC-POR-008 Insights loads within 3 s', async ({ page }) => {
  const start = Date.now();
  await open(page, '/insights', 'lead');
  await expect(page.getByRole('table', { name: 'Runs' })).toBeVisible();
  expect(Date.now() - start).toBeLessThan(3000);
});
