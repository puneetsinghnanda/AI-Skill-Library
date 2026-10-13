import { axeSeriousOrCritical, expect, open, setView, test, type DemoUser } from './fixtures';

const SCREENS: [string, DemoUser][] = [
  ['/', 'viewer'],
  ['/', 'engineer'],
  ['/how-it-works', 'viewer'],
  ['/how-it-works', 'engineer'],
  ['/skills', 'viewer'],
  ['/skills', 'engineer'],
  ['/skills/threat-model', 'viewer'],
  ['/skills/threat-model', 'engineer'],
  ['/get-started', 'viewer'],
  ['/get-started', 'engineer'],
  ['/pods', 'viewer'],
  ['/pods', 'engineer'],
  ['/pods/brownfield-change-pod', 'viewer'],
  ['/pods/brownfield-change-pod', 'engineer'],
  ['/pods/builder', 'viewer'],
  ['/pods/brownfield-change-pod/one-pager', 'viewer'],
  ['/insights', 'viewer'],
  ['/insights', 'lead'],
  ['/insights/engineering/skills', 'lead'],
  ['/insights/engineering/usage', 'lead'],
  ['/insights/engineering/health', 'lead'],
  ['/insights/capability-map/share', 'viewer'],
  ['/insights/skills/design/improvement', 'lead'],
  ['/runs/run_01J9ZK2M4Q8X7T3B5N6R0VWYCD', 'engineer'],
];

test.describe('TC-POR-006 axe: zero serious or critical issues on every screen, both views', () => {
  for (const [path, user] of SCREENS) {
    test(`${path} as ${user}`, async ({ page, problems }) => {
      await open(page, path, user);
      expect(await axeSeriousOrCritical(page)).toEqual([]);
      expect(problems).toEqual([]);
    });
  }

  test('Business view of an engineer, Home and Skills', async ({ page }) => {
    await open(page, '/', 'lead');
    await setView(page, 'Business');
    await expect(page.getByRole('heading', { level: 1 })).toContainText('Reusable AI skills');
    expect(await axeSeriousOrCritical(page)).toEqual([]);
  });
});

test.describe('keyboard', () => {
  test('skip link moves to main', async ({ page }) => {
    await open(page, '/', 'viewer');
    await page.keyboard.press('Tab');
    const skip = page.getByRole('link', { name: 'Skip to main content' });
    await expect(skip).toBeFocused();
    await page.keyboard.press('Enter');
    await expect(page.locator('#main')).toBeFocused();
  });

  test('Skills role chips and Skill detail tabs work from the keyboard', async ({ page }) => {
    await open(page, '/skills', 'engineer');
    const chip = page
      .getByRole('group', { name: 'Filter by role' })
      .getByRole('button', { name: 'Security' });
    await chip.focus();
    await page.keyboard.press('Enter');
    await expect(chip).toHaveAttribute('aria-pressed', 'true');
    await expect(page).toHaveURL(/role=security/);
    await page
      .getByRole('link', { name: /Threat model/ })
      .first()
      .focus();
    await page.keyboard.press('Enter');
    await expect(page.getByRole('heading', { level: 1 })).toHaveText('Threat model');
    const tab = page.getByRole('tab', { name: 'Inputs and outputs' });
    await tab.focus();
    await page.keyboard.press('ArrowRight');
    await expect(page.getByRole('tab', { name: 'Quality' })).toBeFocused();
    await expect(page.getByRole('tab', { name: 'Quality' })).toHaveAttribute(
      'aria-selected',
      'true',
    );
    await expect(page.getByText('Top reasons a step did not pass first time')).toBeVisible();
  });

  test('Run detail: View switches the check record panel', async ({ page }) => {
    await open(page, '/runs/run_01J9ZK2M4Q8X7T3B5N6R0VWYCD', 'engineer');
    const view = page.getByRole('button', { name: /View check record for story-split/ });
    await view.focus();
    await page.keyboard.press('Enter');
    await expect(page.getByRole('heading', { name: 'Check record · story-split' })).toBeVisible();
  });

  test('focus ring is visible on links', async ({ page }) => {
    await open(page, '/', 'viewer');
    const link = page.getByRole('link', { name: 'See how it works' });
    await link.focus();
    const outline = await link.evaluate(
      (el) => getComputedStyle(el).outlineStyle + ' ' + getComputedStyle(el).outlineWidth,
    );
    expect(outline).toContain('solid');
    expect(outline).toContain('2px');
  });
});

test.describe('reflow at 320 CSS px (WCAG 1.4.10)', () => {
  test.use({ viewport: { width: 320, height: 720 } });
  for (const [path, user] of [
    ['/', 'viewer'],
    ['/skills', 'viewer'],
    ['/insights', 'viewer'],
    ['/insights', 'lead'],
    ['/runs/run_01J9ZK2M4Q8X7T3B5N6R0VWYCD', 'engineer'],
  ] as [string, DemoUser][]) {
    test(`${path} as ${user} has no page-level horizontal scroll`, async ({ page }) => {
      await open(page, path, user);
      const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
      );
      expect(overflow).toBeLessThanOrEqual(0);
    });
  }
});
