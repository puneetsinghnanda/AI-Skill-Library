/**
 * Admin screens in demo mode (SDD-09 §4.16): MSW and the test token-cache fixture, invented data.
 * One full admin flow: grant a role, then revoke it from its row in the grant list, through the
 * confirmation dialog.
 */
import { axeSeriousOrCritical, expect, open, test } from './fixtures';

test.describe('admin screens', () => {
  test('an engineer sees no Admin entry and /admin is Not found', async ({ page }) => {
    await open(page, '/', 'engineer');
    await expect(
      page.getByRole('navigation', { name: 'Main' }).getByRole('link', { name: 'Admin' }),
    ).toHaveCount(0);
    await open(page, '/admin/roles', 'engineer');
    await expect(page.getByRole('heading', { level: 1 })).toHaveText('Page not found');
  });

  test('admin grants a role and revokes it from its row after confirming', async ({
    page,
    problems,
  }) => {
    const posts: { url: string; auth: string }[] = [];
    page.on('request', (r) => {
      if (r.method() === 'POST')
        posts.push({ url: r.url(), auth: r.headers()['authorization'] ?? '' });
    });

    await open(page, '/', 'admin');
    await page
      .getByRole('navigation', { name: 'Main' })
      .getByRole('link', { name: 'Admin' })
      .click();
    await expect(page.getByRole('heading', { level: 1 })).toHaveText('Administration');
    await page
      .getByRole('navigation', { name: 'Admin sections' })
      .getByRole('link', { name: 'Role grants' })
      .click();
    await expect(page.getByRole('heading', { level: 1 })).toHaveText('Role grants');
    expect(await axeSeriousOrCritical(page)).toEqual([]);

    const grant = page.getByRole('region', { name: 'Grant a role' });
    await grant.getByLabel('User pseudonym').fill('eng-0b3e');
    await grant.getByLabel('Role').selectOption('engineer');
    await grant.getByLabel('System').fill('SYS-INV');
    await grant.getByRole('button', { name: 'Grant role' }).click();
    const result = grant.getByRole('status');
    await expect(result).toContainText('Engineer granted to eng-0b3e on SYS-INV');
    const text = (await result.textContent()) ?? '';
    const grantId = /Grant id ([0-9a-f-]{36})/.exec(text)?.[1];
    expect(grantId).toBeTruthy();

    // The grant appears in the list; revoke it from its row.
    const list = page.getByRole('region', { name: 'Grant list' });
    const row = list.getByRole('row').filter({ hasText: grantId ?? '' });
    await expect(row).toContainText('Active');
    await row.getByRole('button', { name: 'Revoke grant Engineer for eng-0b3e' }).click();
    const dialog = page.getByRole('alertdialog', { name: 'Revoke this role grant?' });
    await expect(dialog).toBeVisible();
    await expect(dialog.getByRole('button', { name: 'Cancel' })).toBeFocused();
    await dialog.getByLabel('Reason').fill('Granted by mistake');
    expect(await axeSeriousOrCritical(page)).toEqual([]);
    await dialog.getByRole('button', { name: 'Revoke grant' }).click();
    await expect(dialog).toHaveCount(0);
    const card = page.getByRole('region', { name: 'All role grants' });
    await expect(card.getByRole('status')).toContainText(`Grant ${grantId} revoked.`);
    await expect(row).toContainText('Revoked');

    expect(posts.map((p) => new URL(p.url).pathname)).toEqual([
      '/v1/admin/role-grants',
      `/v1/admin/role-grants/${grantId}/revoke`,
    ]);
    // Portal.Write is requested only for the admin actions themselves.
    expect(posts.every((p) => p.auth === 'Bearer tm-fixture.admin.write')).toBe(true);
    expect(problems).toEqual([]);
  });
});
