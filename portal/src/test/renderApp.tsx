import { render, screen } from '@testing-library/react';
import { QueryClient } from '@tanstack/react-query';
import { createMemoryRouter } from 'react-router-dom';
import { createPortal, Portal, ROUTER_FUTURE } from '../app/App';
import { VIEW_KEY } from '../app/ViewContext';
import type { ViewName } from '../api/types';
import { fixtureAuth } from '../demo/fixtureAuth';
import type { DemoUserId } from '../mocks/fixtures';

export interface RenderOptions {
  user?: DemoUserId;
  view?: ViewName;
  onSignOut?: () => void;
}

/** Renders the whole portal at `path` with the test token-cache fixture and MSW (no network). */
export function renderApp(path: string, opts: RenderOptions = {}) {
  if (opts.view) window.localStorage.setItem(VIEW_KEY, opts.view);
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } },
  });
  const deps = createPortal(fixtureAuth(opts.user ?? 'engineer', { onSignOut: opts.onSignOut }), {
    queryClient,
    createRouter: (routes) =>
      createMemoryRouter(routes, { initialEntries: [path], future: ROUTER_FUTURE }),
  });
  const utils = render(<Portal {...deps} />);
  return { ...utils, router: deps.router, queryClient };
}

/** Waits for the screen's h1 (one per screen). */
export async function findH1(name?: string | RegExp) {
  return screen.findByRole('heading', { level: 1, ...(name ? { name } : {}) }, { timeout: 5000 });
}

/** Text patterns a Business view must never show (TC-POR-002; SDD-09 §6 business safety scan). */
export const BUSINESS_FORBIDDEN: RegExp[] = [
  /run_[0-9A-HJKMNP-TV-Z]{4}/,
  /\beng-[0-9a-f]{4}\b/,
  /\bSYS-[A-Z0-9]+/,
  /\bPRJ-[A-Z0-9]+/,
  /\bCL-[A-Z0-9]+/,
  /\b(ORD|TKT|INV)-\d+\b/,
  /Avery Example|Jordan Sample|Casey Placeholder|Riley Fixture|Morgan Demo/,
];
