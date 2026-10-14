/**
 * TM_TEST_AUTH_FIXTURE
 *
 * Test-only token-cache fixture (TST-01 §2.5, TC-POR-010). It stands in for MSAL in Vitest, in
 * Playwright and in the explicit `npm run demo` build, which uses mocked data. It is never part of
 * a production build: scripts/check-bundle.mjs fails the build if the marker above appears in dist/.
 */
import type { ReactNode } from 'react';
import type { AuthPort } from '../auth/port';
import { FIXTURE_TOKEN_PREFIX, FIXTURE_WRITE_SUFFIX } from '../mocks/handlers';
import type { DemoUserId } from '../mocks/fixtures';

export const TEST_AUTH_MARKER = 'TM_TEST_AUTH_FIXTURE';

function Passthrough({ children }: { children: ReactNode }) {
  return <>{children}</>;
}

export function fixtureAuth(user: DemoUserId, hooks: { onSignOut?: () => void } = {}): AuthPort {
  return {
    async getToken(options) {
      // The write token carries a `.write` suffix so the mocks can check the Portal.Write scope.
      return `${FIXTURE_TOKEN_PREFIX}${user}${options?.write ? FIXTURE_WRITE_SUFFIX : ''}`;
    },
    async signIn() {
      /* nothing to do: the fixture is always signed in */
    },
    async signOut() {
      hooks.onSignOut?.();
    },
    Gate: Passthrough,
  };
}
