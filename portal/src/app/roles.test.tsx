/** Role visibility and persona rules (Doc 4 §2.0, SDD-09 §3.6, §5.3; TC-POR-001..003). */
import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { BUSINESS_FORBIDDEN, findH1, renderApp } from '../test/renderApp';
import { VIEW_KEY } from './ViewContext';

describe('persona switch', () => {
  it('is hidden for a user who only holds the business (viewer) role', async () => {
    renderApp('/', { user: 'viewer' });
    await findH1(/Reusable AI skills/);
    expect(screen.queryByRole('group', { name: 'View as' })).toBeNull();
  });

  it('is shown to users with an engineer-family role, who also get the business view', async () => {
    const user = userEvent.setup();
    renderApp('/', { user: 'engineer' });
    await findH1('Welcome back');
    const group = screen.getByRole('group', { name: 'View as' });
    const biz = within(group).getByRole('button', { name: 'Business' });
    expect(within(group).getByRole('button', { name: 'Engineer' })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
    await user.click(biz);
    await findH1(/Reusable AI skills/);
    expect(biz).toHaveAttribute('aria-pressed', 'true');
    expect(window.localStorage.getItem(VIEW_KEY)).toBe('business');
  });

  it('ignores a stored engineer view for a viewer (the server decides access)', async () => {
    renderApp('/', { user: 'viewer', view: 'engineer' });
    await findH1(/Reusable AI skills/);
    expect(screen.queryByText('Welcome back')).toBeNull();
  });
});

describe('engineer-only screens', () => {
  it('Run detail sends a Business view to Insights (TC-POR-003)', async () => {
    const { router } = renderApp('/runs/run_01J9ZK2M4Q8X7T3B5N6R0VWYCD', { user: 'viewer' });
    await findH1('Impact and capability');
    expect(router.state.location.pathname).toBe('/insights');
  });

  it('Engineering monitoring sends a Business view to Insights', async () => {
    const { router } = renderApp('/insights/engineering/usage', { user: 'lead', view: 'business' });
    await findH1('Impact and capability');
    expect(router.state.location.pathname).toBe('/insights');
  });

  it('an engineer sees the run with its next action and command', async () => {
    renderApp('/runs/run_01J9ZK2M4Q8X7T3B5N6R0VWYCD', { user: 'engineer' });
    await findH1(/run_01J9ZK2M4Q8X7T3B5N6R0VWYCD/);
    expect(
      await screen.findByText('Answer open-questions.md, then resume in Claude Code'),
    ).toBeInTheDocument();
    expect(
      screen.getAllByText('/truminds:resume run_01J9ZK2M4Q8X7T3B5N6R0VWYCD').length,
    ).toBeGreaterThan(0);
  });

  it('a run outside the caller scope is Not found, never revealed', async () => {
    renderApp('/runs/run_01J8XX5Y6Z7A8B9C0D1E2F3GX5', { user: 'engineer' });
    await findH1('Run not available');
    expect(screen.getByText(/outside your scope/)).toBeInTheDocument();
    expect(screen.getByText('E-API-04')).toBeInTheDocument();
  });
});

describe('names (RD-1, SDD-09 §5.3)', () => {
  it('engineers see pseudonyms and no Show names toggle', async () => {
    renderApp('/insights/engineering/runs', { user: 'engineer' });
    await findH1('Monitoring');
    expect((await screen.findAllByText('eng-4f2a')).length).toBeGreaterThan(0);
    expect(screen.queryByLabelText(/Show names/)).toBeNull();
    expect(screen.queryByText('Avery Example')).toBeNull();
  });

  it('an engineering lead may opt in; names are off by default', async () => {
    const user = userEvent.setup();
    renderApp('/insights/engineering/runs', { user: 'lead' });
    await findH1('Monitoring');
    const toggle = await screen.findByLabelText(/Show names/);
    expect(toggle).not.toBeChecked();
    expect(screen.queryByText('Avery Example')).toBeNull();
    await user.click(toggle);
    expect((await screen.findAllByText('Avery Example')).length).toBeGreaterThan(0);
  });

  it('the Usage note words the RD-1 default', async () => {
    renderApp('/insights/engineering/usage', { user: 'engineer' });
    expect(
      await screen.findByText(/Names are visible only to engineering leads and admins/),
    ).toBeInTheDocument();
  });
});

describe('business persona never sees run ids, tickets, systems or names (TC-POR-002)', () => {
  const paths = [
    '/',
    '/insights',
    '/skills',
    '/skills/threat-model',
    '/pods',
    '/pods/brownfield-change-pod',
    '/how-it-works',
    '/get-started',
    '/insights/capability-map/share',
    '/pods/brownfield-change-pod/one-pager',
  ];
  it.each(paths)('%s in the Business view (as an engineering lead)', async (path) => {
    renderApp(path, { user: 'lead', view: 'business' });
    await findH1();
    await waitFor(() => expect(document.querySelectorAll('[aria-busy="true"]').length).toBe(0), {
      timeout: 5000,
    });
    const text = document.body.textContent ?? '';
    for (const re of BUSINESS_FORBIDDEN) expect(text).not.toMatch(re);
  });
});

describe('top bar (TC-POR-001)', () => {
  it.each([
    ['/skills/threat-model', 'Skills'],
    ['/pods/builder', 'Pods'],
    ['/pods/brownfield-change-pod', 'Pods'],
    ['/runs/run_01J9ZK2M4Q8X7T3B5N6R0VWYCD', 'Insights'],
    ['/get-started', 'Get started'],
    ['/', 'Home'],
  ])('%s highlights %s', async (path, label) => {
    renderApp(path, { user: 'engineer' });
    await findH1();
    const nav = screen.getByRole('navigation', { name: 'Main' });
    expect(within(nav).getByRole('link', { name: label })).toHaveAttribute('aria-current', 'page');
    expect(
      within(nav)
        .getAllByRole('link')
        .filter((a) => a.getAttribute('aria-current') === 'page'),
    ).toHaveLength(1);
  });

  it('shows the role label and initials, never the full own name', async () => {
    renderApp('/', { user: 'engineer' });
    await findH1();
    expect(screen.getByText('Engineer · Tech lead')).toBeInTheDocument();
    expect(screen.getByText('AE')).toBeInTheDocument();
  });

  it('search suggests skills and Enter opens the catalogue with q', async () => {
    const user = userEvent.setup();
    const { router } = renderApp('/', { user: 'viewer' });
    await findH1();
    const box = screen.getByRole('searchbox', { name: 'Search skills, roles, pods' });
    await user.type(box, 'threat');
    expect(await screen.findByRole('link', { name: /Threat model/ })).toBeInTheDocument();
    await user.type(box, '{Enter}');
    await waitFor(() => expect(router.state.location.pathname).toBe('/skills'));
    expect(router.state.location.search).toBe('?q=threat');
  });

  it('a signed-in user with no grant sees only the no-access page', async () => {
    const { server } = await import('../test/server');
    const { http, HttpResponse } = await import('msw');
    server.use(
      http.get('/v1/me', () =>
        HttpResponse.json({
          data: {
            pseudonym: 'usr-0000',
            display_name: null,
            role_label: 'Viewer',
            roles: [],
            agent_role: null,
            default_view: 'business',
            can_switch_view: false,
            can_reveal_names: false,
            scope: { projects: [] },
            app_roles: [],
          },
          meta: { generated_at: '2026-10-13T00:00:00Z' },
        }),
      ),
    );
    renderApp('/', { user: 'viewer' });
    expect(await findH1('You do not have access yet. Ask an admin.')).toBeInTheDocument();
    expect(screen.queryByRole('navigation', { name: 'Main' })).toBeNull();
  });
});
