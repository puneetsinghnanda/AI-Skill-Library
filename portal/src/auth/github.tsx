/**
 * GitHub sign-in, interim for the test phase (ADR 0006, SDD-09 §3.4.1). Backend-for-frontend: the
 * insights service runs the OAuth code flow (`/auth/github/login`, `/auth/github/callback`) and
 * keeps the GitHub token encrypted inside an HttpOnly session cookie. The SPA never sees a token:
 * API calls use `credentials: 'include'`, writes add `X-Requested-With: truminds-portal`.
 *
 * Used only when the build sets VITE_IDENTITY_PROVIDER=github. Entra (auth/msal.tsx) stays the
 * production path.
 */
import { useEffect, useState, type ReactNode } from 'react';
import { CSRF_HEADER } from '../api/client';
import type { AuthPort } from './port';

export interface GitHubPortDeps {
  /** Insights service base; empty means same origin. */
  apiBaseUrl: string;
  fetchImpl?: typeof fetch;
  navigate?: (url: string) => void;
  currentPath?: () => string;
}

function join(base: string, path: string): string {
  return `${base.replace(/\/+$/, '')}${path}`;
}

/** Only same-origin portal paths go to `return_to` (the service checks again). */
export function returnPath(path: string): string {
  if (!path.startsWith('/') || path.startsWith('//') || path.startsWith('/auth/')) return '/';
  return path;
}

export function signInUrl(apiBaseUrl: string, path: string): string {
  return join(apiBaseUrl, `/auth/github/login?return_to=${encodeURIComponent(returnPath(path))}`);
}

type SessionState = 'checking' | 'signed-in' | 'signed-out';

export function githubAuthPort(deps: GitHubPortDeps): AuthPort {
  const doFetch = deps.fetchImpl ?? ((...a: Parameters<typeof fetch>) => globalThis.fetch(...a));
  const navigate = deps.navigate ?? ((url: string) => window.location.assign(url));
  const here =
    deps.currentPath ??
    (() => `${window.location.pathname}${window.location.search}${window.location.hash}`);

  function Gate({ children }: { children: ReactNode }) {
    const [state, setState] = useState<SessionState>('checking');
    useEffect(() => {
      let live = true;
      doFetch(join(deps.apiBaseUrl, '/v1/me'), {
        headers: { Accept: 'application/json' },
        credentials: 'include',
      })
        .then((r) => {
          if (live) setState(r.status === 401 ? 'signed-out' : 'signed-in');
        })
        .catch(() => {
          // Network trouble: let the shell show its error state with a retry.
          if (live) setState('signed-in');
        });
      return () => {
        live = false;
      };
    }, []);
    if (state === 'checking') {
      return (
        <main id="main" className="tm-wrap pt-40" aria-busy="true">
          <p role="status">Checking your sign-in…</p>
        </main>
      );
    }
    if (state === 'signed-out') {
      return (
        <main id="main" className="tm-wrap pt-40">
          <h1 className="page-h1">Sign in to the AI Skill Library</h1>
          <p className="tm-sub">
            This test environment uses GitHub sign-in. An admin must grant you a role after your
            first sign-in.
          </p>
          <a className="tm-btn btn-primary mt-16" href={signInUrl(deps.apiBaseUrl, here())}>
            Sign in with GitHub
          </a>
        </main>
      );
    }
    return <>{children}</>;
  }

  return {
    credentials: 'cookie',
    getToken() {
      // Never called in cookie mode (api/client.ts); there is no token in the browser.
      return Promise.reject(new Error('GitHub sign-in uses the session cookie, not a token'));
    },
    signIn() {
      navigate(signInUrl(deps.apiBaseUrl, here()));
      return Promise.resolve();
    },
    async signOut() {
      try {
        await doFetch(join(deps.apiBaseUrl, '/auth/logout'), {
          method: 'POST',
          headers: { ...CSRF_HEADER },
          credentials: 'include',
        });
      } finally {
        navigate('/');
      }
    },
    Gate,
  };
}
