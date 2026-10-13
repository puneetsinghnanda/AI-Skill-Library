import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { scenario } from '../mocks/handlers';
import { findH1, renderApp } from '../test/renderApp';

describe('Skills (board Skills)', () => {
  it('filters by role chip with aria-pressed and keeps it in the URL', async () => {
    const user = userEvent.setup();
    const { router } = renderApp('/skills', { user: 'viewer' });
    await findH1('Skills');
    const group = screen.getByRole('group', { name: 'Filter by role' });
    const chip = await within(group).findByRole('button', { name: 'Security' });
    await user.click(chip);
    expect(chip).toHaveAttribute('aria-pressed', 'true');
    await waitFor(() => expect(router.state.location.search).toBe('?role=security'));
    expect(await screen.findByText('Threat model')).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByText('Implement')).toBeNull());
  });

  it('shows the empty state that says what to do next', async () => {
    renderApp('/skills?q=zzzz-nothing', { user: 'viewer' });
    expect(await screen.findByText('No skills match')).toBeInTheDocument();
    expect(screen.getByText('Try another word, or clear the role filter.')).toBeInTheDocument();
  });

  it('Business cards show outputs; Engineer cards show id, version and first-try', async () => {
    renderApp('/skills?role=security', { user: 'viewer' });
    expect(await screen.findByText('Output: threat-model.v1')).toBeInTheDocument();
    expect(screen.queryByText(/first-try/)).toBeNull();
  });

  it('engineers see drafts with a Draft badge and the version chip', async () => {
    renderApp('/skills?role=delivery-manager', { user: 'engineer' });
    expect(await screen.findByText('Release notes')).toBeInTheDocument();
    expect(screen.getByText('Draft')).toBeInTheDocument();
    expect(screen.getByText('estimate-review v1.0.0')).toBeInTheDocument();
  });

  it('the business view of an engineer hides drafts', async () => {
    renderApp('/skills?role=delivery-manager', { user: 'engineer', view: 'business' });
    expect(await screen.findByText('Estimate review')).toBeInTheDocument();
    expect(screen.queryByText('Release notes')).toBeNull();
  });
});

describe('Skill detail (board SkillDetail)', () => {
  it('engineer tabs follow the WAI-ARIA tabs pattern with arrow keys', async () => {
    const user = userEvent.setup();
    renderApp('/skills/threat-model', { user: 'engineer' });
    await findH1('Threat model');
    const tabs = screen.getByRole('tablist', { name: 'Skill details' });
    const first = within(tabs).getByRole('tab', { name: 'Inputs and outputs' });
    expect(first).toHaveAttribute('aria-selected', 'true');
    first.focus();
    await user.keyboard('{ArrowRight}');
    const quality = within(tabs).getByRole('tab', { name: 'Quality' });
    expect(quality).toHaveAttribute('aria-selected', 'true');
    expect(quality).toHaveFocus();
    expect(
      await screen.findByText('Top reasons a step did not pass first time'),
    ).toBeInTheDocument();
    expect(screen.getByRole('tabpanel')).toBeInTheDocument();
    await user.keyboard('{End}');
    expect(within(tabs).getByRole('tab', { name: 'Used in workflows' })).toHaveAttribute(
      'aria-selected',
      'true',
    );
    expect(await screen.findByText(/Step 6 of 11, after the G-design gate/)).toBeInTheDocument();
  });

  it('business view shows why clients care and the pods that include it', async () => {
    renderApp('/skills/threat-model', { user: 'viewer' });
    await findH1('Threat model');
    expect(screen.getByText('Why clients care')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'See the pod' })).toHaveAttribute(
      'href',
      '/pods/brownfield-change-pod',
    );
    expect(screen.queryByRole('tablist')).toBeNull();
  });

  it('an unknown skill shows the error card with the code', async () => {
    renderApp('/skills/no-such-skill', { user: 'viewer' });
    await findH1('Skill not available');
    expect(screen.getByText('E-API-04')).toBeInTheDocument();
    expect(screen.getByText(/Request id/)).toBeInTheDocument();
  });
});

describe('states', () => {
  it('Business numbers show No data yet when the API returns nulls (TC-POR-004)', async () => {
    scenario.empty = true;
    renderApp('/insights', { user: 'viewer' });
    await findH1('Impact and capability');
    expect((await screen.findAllByText('No data yet')).length).toBeGreaterThan(0);
    expect(screen.queryByText('82%')).toBeNull();
  });

  it('shows the behind banner with the last event time (TC-POR-005)', async () => {
    scenario.behind = true;
    renderApp('/', { user: 'viewer' });
    await findH1();
    expect(
      await screen.findByText(/Insights are behind; last event received at/),
    ).toBeInTheDocument();
    expect(
      screen.getAllByRole('status').some((s) => s.textContent?.includes('Insights are behind')),
    ).toBe(true);
  });

  it('no banner when insights are current', async () => {
    renderApp('/', { user: 'viewer' });
    await findH1();
    await waitFor(() => expect(screen.queryByText(/Insights are behind/)).toBeNull());
  });
});

describe('Run detail (board RunDetail)', () => {
  it('shows the check record and links the question file instead of question text (RD-3)', async () => {
    const user = userEvent.setup();
    renderApp('/runs/run_01J9ZK2M4Q8X7T3B5N6R0VWYCD', { user: 'engineer' });
    await findH1(/run_01J9ZK2M/);
    expect(
      await screen.findByRole('heading', { name: 'Check record · design' }),
    ).toBeInTheDocument();
    const link = screen.getByRole('link', { name: 'Read and answer in open-questions.md' });
    expect(link.getAttribute('href')).toMatch(
      /runs\/run_01J9ZK2M4Q8X7T3B5N6R0VWYCD\/open-questions\.md$/,
    );
    expect(screen.getByText(/Q-01/)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /View check record for impact-analysis/ }));
    expect(
      screen.getByRole('heading', { name: 'Check record · impact-analysis' }),
    ).toBeInTheDocument();
    expect(screen.getAllByText('Not started').length).toBeGreaterThan(0);
  });
});

describe('Home: Engineer (board HomeEngineer)', () => {
  it('shows tiles, my runs and waiting items without question text', async () => {
    renderApp('/', { user: 'engineer' });
    await findH1('Welcome back');
    expect(await screen.findByText('1 question · 1 approval')).toBeInTheDocument();
    expect(screen.getByRole('table', { name: 'My runs' })).toBeInTheDocument();
    expect(screen.getAllByRole('link', { name: 'Open open-questions.md' }).length).toBe(1);
    expect(await screen.findByText('Skills for your role · Developer')).toBeInTheDocument();
  });
});

describe('Pods', () => {
  it('Pod builder is the static Phase 3 notice with no API call', async () => {
    renderApp('/pods/builder', { user: 'viewer' });
    await findH1('Build a pod');
    expect(screen.getByText(/Phase 3 preview, not in Release 1/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Save pod/ })).toBeNull();
  });

  it('a pilot pod one-pager prints the internal-only label', async () => {
    renderApp('/pods/quality-security-pod/one-pager', { user: 'viewer' });
    expect(await screen.findByText('Pilot · internal only')).toBeInTheDocument();
  });

  it('engineers see active runs and the fit check for a chosen system', async () => {
    const user = userEvent.setup();
    renderApp('/pods/brownfield-change-pod', { user: 'engineer' });
    await findH1('Brownfield Change Pod');
    expect(
      await screen.findByRole('table', { name: 'Active runs of this pod' }),
    ).toBeInTheDocument();
    await user.selectOptions(screen.getByRole('combobox', { name: 'System' }), 'SYS-ORD');
    expect(await screen.findByText('Confirm locally')).toBeInTheDocument();
  });

  it('the shared capability map never shows pilot skills', async () => {
    renderApp('/insights/capability-map/share', { user: 'viewer' });
    await findH1('Capability map');
    expect(
      await screen.findByRole('table', { name: /Production skills by role/ }),
    ).toBeInTheDocument();
    expect(screen.queryByText(/pilot/i)).toBeNull();
  });
});
