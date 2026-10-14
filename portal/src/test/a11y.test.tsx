/** WCAG 2.2 AA checks with vitest-axe on every screen in both views (TC-POR-006, unit layer). */
import { waitFor } from '@testing-library/react';
import { axe } from 'vitest-axe';
import { describe, expect, it } from 'vitest';
import type { DemoUserId } from '../mocks/fixtures';
import { findH1, renderApp } from './renderApp';

const CASES: [string, DemoUserId, 'business' | 'engineer'][] = [
  ['/', 'viewer', 'business'],
  ['/', 'engineer', 'engineer'],
  ['/how-it-works', 'viewer', 'business'],
  ['/how-it-works', 'engineer', 'engineer'],
  ['/skills', 'viewer', 'business'],
  ['/skills', 'engineer', 'engineer'],
  ['/skills/threat-model', 'viewer', 'business'],
  ['/skills/threat-model', 'engineer', 'engineer'],
  ['/get-started', 'viewer', 'business'],
  ['/get-started', 'engineer', 'engineer'],
  ['/pods', 'viewer', 'business'],
  ['/pods', 'engineer', 'engineer'],
  ['/pods/brownfield-change-pod', 'viewer', 'business'],
  ['/pods/brownfield-change-pod', 'engineer', 'engineer'],
  ['/pods/builder', 'viewer', 'business'],
  ['/pods/brownfield-change-pod/one-pager', 'viewer', 'business'],
  ['/insights', 'viewer', 'business'],
  ['/insights', 'lead', 'engineer'],
  ['/insights/engineering/skills', 'lead', 'engineer'],
  ['/insights/engineering/usage', 'lead', 'engineer'],
  ['/insights/engineering/health', 'lead', 'engineer'],
  ['/insights/capability-map/share', 'viewer', 'business'],
  ['/insights/skills/design/improvement', 'lead', 'engineer'],
  ['/runs/run_01J9ZK2M4Q8X7T3B5N6R0VWYCD', 'engineer', 'engineer'],
  ['/nowhere', 'viewer', 'business'],
  ['/admin', 'admin', 'engineer'],
  ['/admin/clients', 'admin', 'engineer'],
  ['/admin/projects', 'admin', 'engineer'],
  ['/admin/roles', 'admin', 'engineer'],
  ['/admin/users', 'admin', 'engineer'],
];

describe('axe', () => {
  it.each(CASES)('%s as %s (%s view) has no violations', async (path, user, view) => {
    const { container } = renderApp(path, { user, view });
    await findH1();
    await waitFor(() => expect(container.querySelectorAll('[aria-busy="true"]').length).toBe(0), {
      timeout: 5000,
    });
    const results = await axe(container, {
      rules: {
        // jsdom has no layout engine; contrast is checked in Playwright and by `npm run check:tokens`.
        'color-contrast': { enabled: false },
      },
    });
    expect(results).toHaveNoViolations();
  });
});
