/** Admin screens (SDD-09 §4.16, SDD-13 §7.2): visibility, validation, confirmations, write scope. */
import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { axe } from 'vitest-axe';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { adminAudit } from '../../mocks/admin';
import type { DemoUserId } from '../../mocks/fixtures';
import { server } from '../../test/server';
import { findH1, renderApp } from '../../test/renderApp';

const NON_ADMINS: DemoUserId[] = ['viewer', 'engineer', 'lead'];
const ADMIN_PATHS = ['/admin', '/admin/clients', '/admin/projects', '/admin/roles', '/admin/users'];
const AXE = { rules: { 'color-contrast': { enabled: false } } };

/** Records method, path and bearer token of every request the portal sends. */
let calls: { method: string; path: string; auth: string }[] = [];
const record = ({ request }: { request: Request }) => {
  calls.push({
    method: request.method,
    path: new URL(request.url).pathname,
    auth: request.headers.get('authorization') ?? '',
  });
};
beforeEach(() => {
  calls = [];
  server.events.on('request:start', record);
});
afterEach(() => {
  server.events.removeListener('request:start', record);
});

function mainNav() {
  return screen.getByRole('navigation', { name: 'Main' });
}

describe('visibility (admin app role only)', () => {
  it.each(NON_ADMINS)('%s never sees the Admin nav entry', async (user) => {
    renderApp('/', { user });
    await findH1();
    expect(within(mainNav()).queryByRole('link', { name: 'Admin' })).toBeNull();
  });

  it.each(NON_ADMINS.flatMap((u) => ADMIN_PATHS.map((p) => [u, p] as const)))(
    '%s opening %s gets Not found and no admin form',
    async (user, path) => {
      renderApp(path, { user });
      await findH1('Page not found');
      expect(screen.queryByRole('navigation', { name: 'Admin sections' })).toBeNull();
      expect(screen.queryByRole('form')).toBeNull();
      expect(
        screen.queryByRole('button', { name: /Grant role|Create client|Deactivate/ }),
      ).toBeNull();
      expect(calls.some((c) => c.method !== 'GET')).toBe(false);
    },
  );

  it('an admin sees the nav entry, and it opens the overview as the active tab', async () => {
    const user = userEvent.setup();
    renderApp('/', { user: 'admin' });
    await findH1();
    await user.click(within(mainNav()).getByRole('link', { name: 'Admin' }));
    await findH1('Administration');
    expect(within(mainNav()).getByRole('link', { name: 'Admin' })).toHaveAttribute(
      'aria-current',
      'page',
    );
    const sections = screen.getByRole('navigation', { name: 'Admin sections' });
    expect(within(sections).getByRole('link', { name: 'Overview' })).toHaveAttribute(
      'aria-current',
      'page',
    );
  });

  it('reading pages never asks for the Portal.Write scope', async () => {
    renderApp('/admin/roles', { user: 'admin' });
    await findH1('Role grants');
    await waitFor(() => expect(calls.length).toBeGreaterThan(0));
    expect(calls.every((c) => c.method === 'GET' && !c.auth.endsWith('.write'))).toBe(true);
  });
});

describe('forms validate before anything is sent', () => {
  it('Create client shows field errors, marks fields invalid and focuses the first', async () => {
    const user = userEvent.setup();
    renderApp('/admin/clients', { user: 'admin' });
    await findH1('Clients and consent');
    const card = screen.getByRole('region', { name: 'Create a client' });
    await user.type(within(card).getByLabelText('Client code'), 'acme');
    await user.click(within(card).getByRole('button', { name: 'Create client' }));
    const code = within(card).getByLabelText('Client code');
    expect(code).toHaveAttribute('aria-invalid', 'true');
    expect(code).toHaveAccessibleDescription(/Enter a client code/);
    expect(within(card).getByLabelText('Display name')).toHaveAttribute('aria-invalid', 'true');
    await waitFor(() => expect(code).toHaveFocus());
    expect(calls.some((c) => c.method === 'POST')).toBe(false);
  });

  it('Record consent needs a reference and at least one scope', async () => {
    const user = userEvent.setup();
    renderApp('/admin/clients', { user: 'admin' });
    await findH1('Clients and consent');
    const card = screen.getByRole('region', { name: 'Record consent' });
    await user.type(within(card).getByLabelText('Client code'), 'CL-DEMO');
    await user.click(within(card).getByRole('button', { name: 'Record consent' }));
    expect(within(card).getByText(/Enter the consent reference/)).toBeInTheDocument();
    expect(within(card).getByText(/Choose at least one thing/)).toBeInTheDocument();
    expect(calls.some((c) => c.method === 'POST')).toBe(false);
  });

  it('Grant role offers only the scopes the role allows and refuses a self-grant', async () => {
    const user = userEvent.setup();
    renderApp('/admin/roles', { user: 'admin' });
    await findH1('Role grants');
    const card = screen.getByRole('region', { name: 'Grant a role' });
    await user.selectOptions(within(card).getByLabelText('Role'), 'eng_lead');
    const applies = within(card).getByLabelText('Applies to');
    expect(
      within(applies)
        .getAllByRole('option')
        .map((o) => o.textContent),
    ).toEqual(['Choose…', 'Whole organisation', 'Client', 'Project']);
    await user.selectOptions(within(card).getByLabelText('Role'), 'engineer');
    expect(within(card).getByLabelText('Applies to')).toHaveValue('system');
    await user.type(within(card).getByLabelText('User pseudonym'), 'eng-5d3e');
    await user.type(within(card).getByLabelText('System'), 'SYS-ORD');
    await user.click(within(card).getByRole('button', { name: 'Grant role' }));
    expect(within(card).getByText('You cannot grant a role to yourself.')).toBeInTheDocument();
    expect(calls.some((c) => c.method === 'POST')).toBe(false);
  });

  it('Create system checks each product repo row', async () => {
    const user = userEvent.setup();
    renderApp('/admin/projects', { user: 'admin' });
    await findH1('Projects and systems');
    const card = screen.getByRole('region', { name: 'Create a system' });
    await user.type(within(card).getByLabelText('Project code'), 'PRJ-07');
    await user.type(within(card).getByLabelText('System code'), 'SYS-NEW');
    await user.type(within(card).getByLabelText('Domain'), 'digital');
    await user.type(within(card).getByLabelText('Companion repo'), 'acme-org/sys-new-companion');
    await user.click(within(card).getByRole('button', { name: 'Add a product repo' }));
    await user.type(within(card).getByLabelText('Repo 1 name'), 'Bad Name');
    await user.click(within(card).getByRole('button', { name: 'Create system' }));
    expect(within(card).getByLabelText('Repo 1 name')).toHaveAttribute('aria-invalid', 'true');
    expect(calls.some((c) => c.method === 'POST')).toBe(false);
  });
});

describe('actions', () => {
  it('Create project sends a Portal.Write token and shows the result', async () => {
    const user = userEvent.setup();
    renderApp('/admin/projects', { user: 'admin' });
    await findH1('Projects and systems');
    const card = screen.getByRole('region', { name: 'Create a project' });
    await user.type(within(card).getByLabelText('Client code'), 'CL-DEMO');
    await user.type(within(card).getByLabelText('Project code'), 'PRJ-NEW');
    await user.click(within(card).getByRole('button', { name: 'Create project' }));
    expect(await within(card).findByRole('status')).toHaveTextContent(
      'Project PRJ-NEW created under CL-DEMO.',
    );
    const post = calls.find((c) => c.method === 'POST');
    expect(post).toMatchObject({
      path: '/v1/admin/projects',
      auth: 'Bearer tm-fixture.admin.write',
    });
    expect(adminAudit()).toContainEqual({ action: 'project_create', target: 'PRJ-NEW' });
  });

  it('a server refusal shows the code, the words and the request id', async () => {
    const user = userEvent.setup();
    renderApp('/admin/roles', { user: 'admin' });
    await findH1('Role grants');
    const card = screen.getByRole('region', { name: 'Grant a role' });
    await user.type(within(card).getByLabelText('User pseudonym'), 'eng-2c4b');
    await user.selectOptions(within(card).getByLabelText('Role'), 'engineer');
    await user.type(within(card).getByLabelText('System'), 'SYS-ORD');
    await user.click(within(card).getByRole('button', { name: 'Grant role' }));
    const alert = await within(card).findByRole('alert');
    expect(alert).toHaveTextContent('The service did not accept these values.');
    expect(alert).toHaveTextContent(/app roles do not allow engineer/);
    expect(alert).toHaveTextContent('E-API-01');
    expect(alert).toHaveTextContent(/Request id [0-9a-f-]{36}/);
  });
});

describe('destructive actions ask for confirmation', () => {
  it('Deactivate: the dialog appears, Cancel sends nothing, Confirm deactivates', async () => {
    const user = userEvent.setup();
    renderApp('/admin/users', { user: 'admin' });
    await findH1('Users and keys');
    const card = screen.getByRole('region', { name: 'Deactivate a user' });
    await user.type(within(card).getByLabelText('User pseudonym'), 'eng-91c0');
    await user.type(within(card).getByLabelText('Reason'), 'Left the company');
    await user.click(within(card).getByRole('button', { name: 'Deactivate user…' }));

    let dialog = await screen.findByRole('alertdialog', { name: 'Deactivate eng-91c0?' });
    expect(within(dialog).getByRole('button', { name: 'Cancel' })).toHaveFocus();
    await user.click(within(dialog).getByRole('button', { name: 'Cancel' }));
    expect(screen.queryByRole('alertdialog')).toBeNull();
    expect(calls.some((c) => c.method === 'POST')).toBe(false);

    await user.click(within(card).getByRole('button', { name: 'Deactivate user…' }));
    dialog = await screen.findByRole('alertdialog');
    await user.click(within(dialog).getByRole('button', { name: 'Deactivate user' }));
    expect(await within(card).findByRole('status')).toHaveTextContent(
      'eng-91c0 deactivated. 1 key and 1 grant revoked.',
    );
    expect(screen.queryByRole('alertdialog')).toBeNull();
    expect(adminAudit().map((a) => a.action)).toEqual(['key_revoke', 'user_deactivate']);
  });

  it('Escape closes the dialog without sending', async () => {
    const user = userEvent.setup();
    renderApp('/admin/roles', { user: 'admin' });
    await findH1('Role grants');
    const card = screen.getByRole('region', { name: 'Revoke a role grant' });
    await user.type(
      within(card).getByLabelText('Grant id'),
      '6b0f2a7e-1c4d-4e8a-9b21-0d5c3e7f9a01',
    );
    await user.type(within(card).getByLabelText('Reason'), 'Moved team');
    await user.click(within(card).getByRole('button', { name: 'Revoke grant…' }));
    await screen.findByRole('alertdialog', { name: 'Revoke this role grant?' });
    await user.keyboard('{Escape}');
    expect(screen.queryByRole('alertdialog')).toBeNull();
    expect(calls.some((c) => c.method === 'POST')).toBe(false);
  });

  it.each([
    ['/admin/clients', 'Withdraw consent', 'Withdraw consent…', 'Withdraw consent for CL-DEMO?'],
    ['/admin/users', 'Revoke a signing key', 'Revoke key…', /Revoke key key_/],
  ] as const)('%s: %s asks first', async (path, region, button, title) => {
    const user = userEvent.setup();
    renderApp(path, { user: 'admin' });
    await findH1();
    const card = screen.getByRole('region', { name: region });
    if (region === 'Withdraw consent') {
      await user.type(within(card).getByLabelText('Client code'), 'CL-DEMO');
    } else {
      await user.type(within(card).getByLabelText('Key id'), 'key_01J9ZK2M4Q8X7T3B5N6R0VWY02');
      await user.selectOptions(within(card).getByLabelText('Reason'), 'lost_device');
    }
    await user.click(within(card).getByRole('button', { name: button }));
    const dialog = await screen.findByRole('alertdialog', { name: title });
    expect(calls.some((c) => c.method === 'POST')).toBe(false);
    await user.click(within(dialog).getAllByRole('button')[1] as HTMLElement);
    expect(await within(card).findByRole('status')).toBeInTheDocument();
  });
});

describe('axe with errors and the dialog shown', () => {
  it('field errors have no violations', async () => {
    const user = userEvent.setup();
    const { container } = renderApp('/admin/projects', { user: 'admin' });
    await findH1('Projects and systems');
    const card = screen.getByRole('region', { name: 'Create a system' });
    await user.click(within(card).getByRole('button', { name: 'Add a product repo' }));
    await user.click(within(card).getByRole('button', { name: 'Create system' }));
    expect(await axe(container, AXE)).toHaveNoViolations();
  });

  it('the confirm dialog has no violations', async () => {
    const user = userEvent.setup();
    renderApp('/admin/users', { user: 'admin' });
    await findH1('Users and keys');
    const card = screen.getByRole('region', { name: 'Deactivate a user' });
    await user.type(within(card).getByLabelText('User pseudonym'), 'eng-91c0');
    await user.type(within(card).getByLabelText('Reason'), 'Left');
    await user.click(within(card).getByRole('button', { name: 'Deactivate user…' }));
    await screen.findByRole('alertdialog');
    expect(await axe(document.body, AXE)).toHaveNoViolations();
  });
});

describe('lists (GET /v1/admin/..., Portal.Read)', () => {
  function rowOf(table: HTMLElement, text: string): HTMLElement {
    const row = within(table)
      .getAllByRole('row')
      .find((r) => r.textContent?.includes(text));
    if (!row) throw new Error(`no row with ${text}`);
    return row;
  }

  it('Clients, projects and systems show as tables, with the read token only', async () => {
    renderApp('/admin/clients', { user: 'admin' });
    await findH1('Clients and consent');
    const clients = await screen.findByRole('region', { name: 'Client list' });
    expect(rowOf(clients, 'CL-DEMO')).toHaveTextContent('Recorded');
    expect(rowOf(clients, 'CL-DEMO')).toHaveTextContent('CONSENT-0001');
    expect(rowOf(clients, 'CL-SAMPLE')).toHaveTextContent('Not recorded');
    expect(calls.filter((c) => c.path.startsWith('/v1/admin/'))).not.toHaveLength(0);
    expect(calls.every((c) => c.method === 'GET' && !c.auth.endsWith('.write'))).toBe(true);
  });

  it('Projects and systems list codes and repos', async () => {
    renderApp('/admin/projects', { user: 'admin' });
    await findH1('Projects and systems');
    const projects = await screen.findByRole('region', { name: 'Project list' });
    expect(rowOf(projects, 'PRJ-07')).toHaveTextContent('CL-DEMO');
    const systems = await screen.findByRole('region', { name: 'System list' });
    expect(rowOf(systems, 'SYS-INV')).toHaveTextContent('example-org/inventory-firmware');
  });

  it('Role grants: active and revoked, with a status filter', async () => {
    const user = userEvent.setup();
    renderApp('/admin/roles', { user: 'admin' });
    await findH1('Role grants');
    let table = await screen.findByRole('region', { name: 'Grant list' });
    expect(rowOf(table, 'eng-0b3e')).toHaveTextContent('Revoked');
    expect(rowOf(table, 'eng-77de')).toHaveTextContent('Active');
    expect(within(rowOf(table, 'eng-0b3e')).queryByRole('button')).toBeNull();
    await user.selectOptions(screen.getByLabelText('Show'), 'revoked');
    await waitFor(() =>
      expect(calls.some((c) => c.path === '/v1/admin/role-grants' && c.auth)).toBe(true),
    );
    await waitFor(() => {
      table = screen.getByRole('region', { name: 'Grant list' });
      expect(within(table).queryByText('eng-77de')).toBeNull();
    });
    expect(rowOf(table, 'eng-0b3e')).toBeInTheDocument();
  });

  it('Revoke from a row: confirm, reason required, then the list refreshes', async () => {
    const user = userEvent.setup();
    renderApp('/admin/roles', { user: 'admin' });
    await findH1('Role grants');
    const table = await screen.findByRole('region', { name: 'Grant list' });
    await user.click(
      within(rowOf(table, 'eng-77de')).getByRole('button', {
        name: 'Revoke grant Engineer for eng-77de',
      }),
    );
    const dialog = await screen.findByRole('alertdialog', { name: 'Revoke this role grant?' });
    expect(within(dialog).getByRole('button', { name: 'Cancel' })).toHaveFocus();
    await user.click(within(dialog).getByRole('button', { name: 'Revoke grant' }));
    const reason = within(dialog).getByLabelText('Reason');
    expect(reason).toHaveAttribute('aria-invalid', 'true');
    await waitFor(() => expect(reason).toHaveFocus());
    expect(calls.some((c) => c.method === 'POST')).toBe(false);
    await user.type(reason, 'Moved team');
    await user.click(within(dialog).getByRole('button', { name: 'Revoke grant' }));
    const grants = screen.getByRole('region', { name: 'All role grants' });
    expect(await within(grants).findByRole('status')).toHaveTextContent(
      'Grant 6b0f2a7e-1c4d-4e8a-9b21-0d5c3e7f9a02 revoked.',
    );
    expect(screen.queryByRole('alertdialog')).toBeNull();
    expect(calls.find((c) => c.method === 'POST')).toMatchObject({
      path: '/v1/admin/role-grants/6b0f2a7e-1c4d-4e8a-9b21-0d5c3e7f9a02/revoke',
      auth: 'Bearer tm-fixture.admin.write',
    });
    await waitFor(() =>
      expect(
        rowOf(screen.getByRole('region', { name: 'Grant list' }), 'eng-77de'),
      ).toHaveTextContent('Revoked'),
    );
    expect(adminAudit()).toContainEqual({
      action: 'role_revoke',
      target: '6b0f2a7e-1c4d-4e8a-9b21-0d5c3e7f9a02',
    });
  });

  it('Users: no deactivate for yourself; deactivate from a row asks first', async () => {
    const user = userEvent.setup();
    renderApp('/admin/users', { user: 'admin' });
    await findH1('Users and keys');
    const table = await screen.findByRole('region', { name: 'User list' });
    expect(rowOf(table, 'eng-5d3e')).toHaveTextContent('Admin');
    expect(
      within(rowOf(table, 'eng-5d3e')).queryByRole('button', { name: /Deactivate/ }),
    ).toBeNull();
    expect(rowOf(table, 'eng-7a1c')).toHaveTextContent('Tech lead');
    await user.click(
      within(rowOf(table, 'eng-77de')).getByRole('button', { name: 'Deactivate eng-77de' }),
    );
    let dialog = await screen.findByRole('alertdialog', { name: 'Deactivate eng-77de?' });
    await user.click(within(dialog).getByRole('button', { name: 'Cancel' }));
    expect(screen.queryByRole('alertdialog')).toBeNull();
    expect(calls.some((c) => c.method === 'POST')).toBe(false);
    await user.click(
      within(rowOf(table, 'eng-77de')).getByRole('button', { name: 'Deactivate eng-77de' }),
    );
    dialog = await screen.findByRole('alertdialog', { name: 'Deactivate eng-77de?' });
    await user.type(within(dialog).getByLabelText('Reason'), 'Left the company');
    await user.click(within(dialog).getByRole('button', { name: 'Deactivate user' }));
    const usersCard = screen.getByRole('region', { name: 'Users' });
    expect(await within(usersCard).findByRole('status')).toHaveTextContent(
      'eng-77de deactivated. 1 key and 1 grant revoked.',
    );
    await waitFor(() =>
      expect(
        rowOf(screen.getByRole('region', { name: 'User list' }), 'eng-77de'),
      ).toHaveTextContent('Inactive'),
    );
  });

  it('Keys of a user: status and expiry, revoke an active key from its row', async () => {
    const user = userEvent.setup();
    renderApp('/admin/users', { user: 'admin' });
    await findH1('Users and keys');
    const users = await screen.findByRole('region', { name: 'User list' });
    const show = within(rowOf(users, 'eng-4f2a')).getByRole('button', {
      name: 'Show keys of eng-4f2a',
    });
    await user.click(show);
    expect(show).toHaveAttribute('aria-pressed', 'true');
    const keys = await screen.findByRole('region', { name: 'Key list of eng-4f2a' });
    expect(rowOf(keys, 'key_01J9ZK2M4Q8X7T3B5N6R0VWY04')).toHaveTextContent('Expired');
    expect(rowOf(keys, 'key_01J9ZK2M4Q8X7T3B5N6R0VWY04')).toHaveTextContent('desk-pc');
    expect(within(rowOf(keys, 'key_01J9ZK2M4Q8X7T3B5N6R0VWY04')).queryByRole('button')).toBeNull();
    await user.click(
      within(rowOf(keys, 'key_01J9ZK2M4Q8X7T3B5N6R0VWY05')).getByRole('button', {
        name: 'Revoke key key_01J9ZK2M4Q8X7T3B5N6R0VWY05',
      }),
    );
    const dialog = await screen.findByRole('alertdialog', {
      name: 'Revoke key key_01J9ZK2M4Q8X7T3B5N6R0VWY05?',
    });
    await user.click(within(dialog).getByRole('button', { name: 'Revoke key' }));
    expect(within(dialog).getByLabelText('Reason')).toHaveAttribute('aria-invalid', 'true');
    expect(calls.some((c) => c.method === 'POST')).toBe(false);
    await user.selectOptions(within(dialog).getByLabelText('Reason'), 'lost_device');
    await user.click(within(dialog).getByRole('button', { name: 'Revoke key' }));
    const keysCard = screen.getByRole('region', { name: 'Keys of eng-4f2a' });
    expect(await within(keysCard).findByRole('status')).toHaveTextContent(
      'Key key_01J9ZK2M4Q8X7T3B5N6R0VWY05 revoked (lost_device).',
    );
    await waitFor(() =>
      expect(
        rowOf(
          screen.getByRole('region', { name: 'Key list of eng-4f2a' }),
          'key_01J9ZK2M4Q8X7T3B5N6R0VWY05',
        ),
      ).toHaveTextContent('Revoked'),
    );
  });

  it('the mock lists page with a cursor and refuse non-admins and write tokens', async () => {
    const get = (path: string, who: string) =>
      fetch(new URL(path, window.location.origin), {
        headers: { Authorization: `Bearer tm-fixture.${who}` },
      });
    const seen: string[] = [];
    let cursor: string | null = null;
    do {
      const q: string = `/v1/admin/users?limit=2${cursor ? `&cursor=${cursor}` : ''}`;
      const body = (await (await get(q, 'admin')).json()) as {
        data: { items: { pseudonym: string }[] };
        page: { limit: number; next_cursor: string | null };
      };
      expect(body.page.limit).toBe(2);
      seen.push(...body.data.items.map((u) => u.pseudonym));
      cursor = body.page.next_cursor;
    } while (cursor);
    expect(seen).toEqual([...seen].sort());
    expect(seen).toHaveLength(7);
    expect((await get('/v1/admin/role-grants', 'lead')).status).toBe(403);
    expect((await get('/v1/admin/role-grants', 'admin.write')).status).toBe(401);
    expect((await get('/v1/admin/users/eng-ffff/keys', 'admin')).status).toBe(404);
  });

  it('axe: the row dialog with a reason error has no violations', async () => {
    const user = userEvent.setup();
    renderApp('/admin/roles', { user: 'admin' });
    await findH1('Role grants');
    const table = await screen.findByRole('region', { name: 'Grant list' });
    await user.click(
      within(rowOf(table, 'eng-91c0')).getByRole('button', { name: /Revoke grant/ }),
    );
    const dialog = await screen.findByRole('alertdialog');
    await user.click(within(dialog).getByRole('button', { name: 'Revoke grant' }));
    expect(await axe(document.body, AXE)).toHaveNoViolations();
  });
});
