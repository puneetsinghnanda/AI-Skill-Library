/**
 * `npm run demo` entry: MSW mocks the read API in the browser and the fixture stands in for MSAL.
 * Only built with `vite build --mode demo`; a production build drops this module (main.tsx).
 */
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { setupWorker } from 'msw/browser';
import { createPortal, Portal } from '../app/App';
import { USERS, type DemoUserId } from '../mocks/fixtures';
import { handlers, scenario } from '../mocks/handlers';
import { DEMO_BEHIND_KEY, DEMO_EMPTY_KEY, DEMO_USER_KEY, DemoBanner } from './DemoBanner';
import { fixtureAuth } from './fixtureAuth';

function read(key: string): string | null {
  try {
    return window.sessionStorage.getItem(key);
  } catch {
    return null;
  }
}

function write(key: string, value: string) {
  try {
    window.sessionStorage.setItem(key, value);
  } catch {
    /* ignore */
  }
}

export async function startDemo(root: HTMLElement): Promise<void> {
  // ?demo_user=viewer|engineer|lead, ?demo_behind=1 and ?demo_empty=1 set the scenario (e2e uses them).
  const params = new URLSearchParams(window.location.search);
  const qUser = params.get('demo_user');
  if (qUser && qUser in USERS) write(DEMO_USER_KEY, qUser);
  if (params.has('demo_behind'))
    write(DEMO_BEHIND_KEY, params.get('demo_behind') === '1' ? '1' : '');
  if (params.has('demo_empty')) write(DEMO_EMPTY_KEY, params.get('demo_empty') === '1' ? '1' : '');
  const stored = read(DEMO_USER_KEY);
  const user: DemoUserId = stored && stored in USERS ? (stored as DemoUserId) : 'engineer';
  scenario.behind = read(DEMO_BEHIND_KEY) === '1';
  scenario.empty = read(DEMO_EMPTY_KEY) === '1';

  const worker = setupWorker(...handlers);
  await worker.start({
    onUnhandledRequest: 'bypass',
    quiet: true,
    serviceWorker: { url: '/mockServiceWorker.js' },
  });

  const deps = createPortal(
    fixtureAuth(user, {
      onSignOut: () => {
        try {
          window.sessionStorage.clear();
        } catch {
          /* ignore */
        }
        window.location.assign('/');
      },
    }),
    { banner: <DemoBanner user={user} /> },
  );
  createRoot(root).render(
    <StrictMode>
      <Portal {...deps} />
    </StrictMode>,
  );
}
